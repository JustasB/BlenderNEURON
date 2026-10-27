"""Offline round trips use real simulation results and a fresh, disconnected Blender."""
import copy
import configparser
import gzip
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from blenderneuron.results import read_snapshot, validate_snapshot, validate_display, write_snapshot
from blenderneuron.utils import serialize
from tests import BackgroundBlender, BlenderTestCase
from blenderneuron.commnode import CommNode


class TestOffline(BlenderTestCase):
    def producer(self, directory, level='Cell', mpi=False, success=True):
        path = str(Path(directory) / 'simulation.bnresults')
        cmd = ([sys.executable] if not mpi else
               ['mpiexec', '--allow-run-as-root', '-n', '2', 'nrniv', '-mpi', '-python'])
        env = dict(os.environ, BLENDERNEURON_CONFIG_DIR=str(Path(directory) / 'settings'),
                   OMPI_ALLOW_RUN_AS_ROOT='1', OMPI_ALLOW_RUN_AS_ROOT_CONFIRM='1')
        result = subprocess.run(cmd + ['tests/offline_export_worker.py', path, level],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=60)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse(Path(path).exists())
        return path, result.stdout

    def tutorial_round_trip(self, mpi):
        repo = Path(__file__).resolve().parents[1]
        tutorial = repo / 'tutorials' / 'offline_simulation.py'
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ,
                       BLENDERNEURON_CONFIG_DIR=str(Path(directory) / 'settings'),
                       OMPI_ALLOW_RUN_AS_ROOT='1', OMPI_ALLOW_RUN_AS_ROOT_CONFIRM='1')
            env['PYTHONPATH'] = os.pathsep.join(filter(None, [str(repo), env.get('PYTHONPATH')]))
            # The tutorial writes into its working directory; keep coverage in the repo.
            if env.get('COVERAGE_PROCESS_START'):
                config = configparser.ConfigParser()
                config.read(env['COVERAGE_PROCESS_START'])
                config['run']['source'] = str(repo / 'blenderneuron')
                config['run']['omit'] = '\n'.join(
                    str(repo / pattern.strip())
                    for pattern in config['run']['omit'].splitlines() if pattern.strip())
                config_path = Path(directory) / 'coverage.ini'
                with config_path.open('w') as config_file:
                    config.write(config_file)
                env['COVERAGE_PROCESS_START'] = str(config_path)
                env['COVERAGE_FILE'] = str(repo / '.coverage')
            command = (['mpiexec', '--allow-run-as-root', '-n', '2',
                        'nrniv', '-mpi', '-python'] if mpi else [sys.executable])
            result = subprocess.run(command + [str(tutorial)], cwd=directory, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout)
            path = str(Path(directory) / 'simulation.bnresults')
            snapshot = read_snapshot(path)
            self.assertEqual(len(snapshot['groups']), 1)
            roots = snapshot['groups'][0]['roots']
            self.assertEqual(len(roots), 2 if mpi else 1)
            self.assertGreater(len(snapshot['groups'][0]['activity']['times']), 50)
            if mpi:
                self.assertEqual({root['name'].split('::')[0] for root in roots},
                                 {'rank0', 'rank1'})
            with BackgroundBlender():
                control = CommNode('Control-Blender')
                script = '''
import bpy
node = bpy.types.Object.BlenderNEURON_node
assert node.client is None
assert bpy.ops.blenderneuron.import_simulation_results(filepath=PATH) == {'FINISHED'}
assert node.offline_results and node.client is None
assert set(node.groups) == {'Network'}
group = node.groups['Network']
assert group.recording_granularity == 'Section'
assert len(group.roots) == COUNT
assert group.view is not None
for root in group.roots.values():
    assert len(root.coords) > 0
    assert len(root.activity.times) == len(root.activity.values) > 2  # Display traces are simplified.
    assert abs(root.activity.times[0]) < 1e-6
    assert root.activity.times[-1] >= 9.9 - 1e-6, root.activity.times
    assert max(root.activity.values) > 0, root.activity.values  # Stimulus evokes a spike.
    mat = group.view.materials[root.name]
    action = mat.animation_data.action
    if hasattr(action, 'fcurve_ensure_for_datablock'):
        curve = action.fcurve_ensure_for_datablock(mat, '["recorded_value"]')
    else:
        curve = action.fcurves.find('["recorded_value"]')
    assert len(curve.keyframe_points) > 0
    bpy.context.scene.frame_set(0)
    assert mat['recorded_value'] < -60
    peak = max(curve.keyframe_points, key=lambda point: point.co.y)
    bpy.context.scene.frame_set(int(round(peak.co.x)))
    assert mat['recorded_value'] > 0
return_value = True
'''.replace('PATH', repr(path)).replace('COUNT', str(2 if mpi else 1))
                self.assertTrue(control.client.run_command(script))

    def test_tutorial_single_process_import(self):
        self.tutorial_round_trip(mpi=False)

    def test_tutorial_mpi_import(self):
        self.tutorial_round_trip(mpi=True)

    def test_single_process_all_recording_levels(self):
        for level in ('Cell', 'Section', '3D Segment'):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as directory:
                path, _ = self.producer(directory, level)
                group = read_snapshot(path)['groups'][0]
                self.assertTrue(group['activity']['times'])
                self.assertTrue(all(0.1 <= t <= 0.8 for t in group['activity']['times']))
                root = group['roots'][0]
                if level == 'Section':
                    self.assertTrue(root['children'][0]['activity']['values'])
                elif level == '3D Segment':
                    self.assertEqual(len(root['segment_activity']), 2)
                else:
                    self.assertGreater(len(set(root['activity']['values'])), 1)

    def test_mpi_round_trip_and_empty_ranks(self):
        for mode in ('Cell', 'Section', '3D Segment', 'empty', 'groups', 'mixed', 'morphology-Cell'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path, _ = self.producer(directory, mode, mpi=True)
                groups = read_snapshot(path)['groups']
                if mode in ('groups', 'mixed'):
                    self.assertEqual({g['name'] for g in groups}, {'Network', 'Rank0 cells', 'Rank1 cells'})
                roots = groups[0]['roots']
                self.assertTrue(roots[0]['name'].startswith('rank0::'))
                if mode != 'empty':
                    self.assertTrue(roots[1]['name'].startswith('rank1::'))

    def test_mpi_failures_reach_every_rank(self):
        for mode, message in (('missing', 'missing variable'),
                              ('settings', 'Inconsistent settings'),
                              ('times', 'Inconsistent sample times'),
                              ('write', 'Could not save simulation results')):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                _, output = self.producer(directory, mode, mpi=True, success=False)
                self.assertIn(message, output)

    def test_validation_and_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.producer(directory)
            snapshot = read_snapshot(path)
            self.assertEqual(snapshot['units']['time'], 'ms')
            mutations = [
                lambda s: s.update(version=99),
                lambda s: s.update(groups=[]),
                lambda s: s['groups'].append(copy.deepcopy(s['groups'][0])),
                lambda s: s['groups'][0].update(record_activity='invalid'),
                lambda s: s['groups'][0].pop('record_variable'),
                lambda s: s['groups'][0]['activity'].update(times=[]),
                lambda s: s['groups'][0].update(roots=[]),
                lambda s: s['groups'][0]['roots'][0]['activity'].update(values=[]),
                lambda s: s['groups'][0]['roots'][0].update(coords=[]),
                lambda s: s['groups'][0]['roots'].append(copy.deepcopy(s['groups'][0]['roots'][0])),
            ]
            for mutate in mutations:
                broken = copy.deepcopy(snapshot)
                mutate(broken)
                with self.assertRaises(ValueError):
                    validate_snapshot(broken)
            before = Path(path).read_bytes()
            with patch('blenderneuron.results.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    write_snapshot(path, snapshot['groups'])
            self.assertEqual(Path(path).read_bytes(), before)
            self.assertEqual(list(Path(directory).glob('.simulation*')), [])
            for payload in (b'bad gzip', gzip.compress(b'{}'), gzip.compress(serialize({'format': 'bad'}).encode())):
                Path(path).write_bytes(payload)
                with self.assertRaises(ValueError):
                    read_snapshot(path)

    def test_morphology_only_without_initialization_or_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for level in ('Cell', 'Section', '3D Segment'):
                path, _ = self.producer(directory, 'morphology-' + level)
                renamed = str(Path(directory) / (level + '.bnresults'))
                Path(path).rename(renamed)
                paths.append(renamed)
                data = read_snapshot(renamed)['groups'][0]
                self.assertFalse(data['record_activity'])
                self.assertNotIn('activity', data)
                stack = list(data['roots'])
                while stack:
                    section = stack.pop()
                    self.assertEqual(section['point_count'], 3)
                    self.assertNotIn('activity', section)
                    self.assertNotIn('segment_activity', section)
                    stack.extend(section['children'])
            mpi_path, _ = self.producer(directory, 'morphology-Section', mpi=True)
            paths.append(mpi_path)
            with BackgroundBlender():
                control = CommNode('Control-Blender')
                self.assertTrue(control.client.run_command("""
import bpy
from blenderneuron.results import read_snapshot
from blenderneuron.blender.dataset import save_offline_state, restore_offline_state, clear_dataset
node = bpy.types.Object.BlenderNEURON_node
for path in PATHS:
    assert bpy.ops.blenderneuron.import_simulation_results(filepath=path) == {'FINISHED'}
    group = node.groups['Network']
    assert not group.record_activity
    source = read_snapshot(path)['groups'][0]
    assert group.view is not None and len(group.roots) == len(source['roots'])
    for root_data in source['roots']:
        root = group.roots[root_data['name']]
        assert root.coords == root_data['coords']
        assert root.radii == root_data['radii']
        assert len(root.children) == len(root_data['children']) == 1
    assert all(len(container.curve.splines) > 0 for container in group.view.containers.values())
    for mat in group.view.materials.values():
        assert mat.animation_data is None
        assert mat.node_tree.animation_data is None
        assert 'recorded_value' not in mat
    save_offline_state()
    clear_dataset(node)  # Restore into fresh runtime state, as on reopening.
    restore_offline_state(node)
    assert not node.groups['Network'].record_activity
    assert node.groups['Network'].view is not None
return_value = True
""".replace('PATHS', repr(paths))))

    def test_event_recording_matches_live_and_resets_between_runs(self):
        from neuron import h
        from types import SimpleNamespace
        from blenderneuron.nrn.offline import SimulationExport
        from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup

        h.load_file('stdrun.hoc')
        root = h.Section(name='event_recording_soma')
        dend = h.Section(name='event_recording_dend')
        dend.connect(root(1))
        for sec in (root, dend):
            sec.insert('pas')
            for x in (0, 10, 20):
                h.pt3dadd(x, 0, 0, 2, sec=sec)
        stimulus = h.IClamp(root(0.5))
        stimulus.delay, stimulus.dur, stimulus.amp = 0, 1, 0.05
        node = SimpleNamespace(section_index={sec.name(): sec for sec in (root, dend)},
                               rank_section_name=lambda name: name)
        pc = h.ParallelContext()
        old_dt, old_tstop = h.dt, h.tstop
        try:
            for level in ('Cell', 'Section', '3D Segment'):
                with self.subTest(level=level):
                    export = SimulationExport().add_group(
                        'Events', [root], recording_granularity=level,
                        recording_time_start=0.125, recording_time_end=0.875,
                        recording_period=0.25).prepare()
                    with tempfile.TemporaryDirectory() as directory:
                        path = str(Path(directory) / 'before_run.bnresults')
                        export.save(path)
                        self.assertFalse(read_snapshot(path)['groups'][0]['record_activity'])
                    live = NeuronRootGroup()
                    live.from_skeletal_blender_group(export.groups['Events'].to_dict(), node)
                    for solver in ('run', 'psolve'):
                        h.dt, h.tstop = 0.03125, 1
                        if solver == 'run':
                            h.run()
                        else:
                            pc.set_maxstep(10)
                            h.finitialize(-65)
                            pc.psolve(1)
                        with tempfile.TemporaryDirectory() as directory:
                            path = str(Path(directory) / 'after_run.bnresults')
                            export.save(path)
                            self.assertTrue(read_snapshot(path)['groups'][0]['record_activity'])
                        actual = export._local_results()[0]
                        expected = live.to_dict(True, True, True)
                        for key in ('variable_units', 'display'):
                            actual.pop(key)
                        self.assertEqual(actual, expected)
                        times = actual['activity']['times']
                        self.assertEqual(len(times), 4)  # No accumulation across runs.
                        for actual_time, expected_time in zip(times, (0.125, 0.375, 0.625, 0.875)):
                            self.assertAlmostEqual(actual_time, expected_time)
        finally:
            h.dt, h.tstop = old_dt, old_tstop

    def test_configuration_and_lifecycle_errors(self):
        from neuron import h
        from blenderneuron.nrn.offline import SimulationExport
        root = h.Section(name='offline_soma')
        dend = h.Section(name='offline_dend')
        dend.connect(root(1))
        h.define_shape()
        with self.assertRaises(RuntimeError):
            SimulationExport().save('/unused')
        with self.assertRaises(ValueError):
            SimulationExport().prepare()
        export = SimulationExport()
        export.add_group('A', [root])
        with self.assertRaises(ValueError):
            export.add_group('A', [])
        export.prepare()
        with self.assertRaises(RuntimeError):
            export.prepare()
        with self.assertRaises(RuntimeError):
            export.add_group('B', [])
        with tempfile.TemporaryDirectory() as directory:
            # Saving an unrun model automatically produces morphology only.
            path = str(Path(directory) / 'unrun.bnresults')
            export.save(path)
            self.assertFalse(read_snapshot(path)['groups'][0]['record_activity'])
        # Explicitly disabled recording does not require the variable to exist.
        disabled = SimulationExport().add_group(
            'Morphology', [root], record_activity=False, record_variable='missing_variable').prepare()
        self.assertFalse(hasattr(disabled.groups['Morphology'], 'collector_stim'))
        self.assertFalse(disabled._local_results()[0]['record_activity'])
        for settings in ({'recording_period': 0}, {'recording_time_start': -1},
                         {'recording_time_end': 1, 'recording_time_start': 2},
                         {'recording_granularity': 'unknown'}, {'record_variable': ''},
                         {'variable_units': 3}, {'display': {'unknown': 1}},
                         {'record_activity': 'invalid'}):
            with self.assertRaises(ValueError):
                SimulationExport().add_group('A', [root], **settings).prepare()
        with self.assertRaisesRegex(ValueError, 'root sections'):
            SimulationExport().add_group('A', [dend]).prepare()
        export = SimulationExport().add_group('A', [root]).add_group('B', [root])
        with self.assertRaisesRegex(ValueError, 'multiple groups'):
            export.prepare()

    def test_display_validation(self):
        for settings in (None, {'unknown': 1}, {'default_color': [1]},
                         {'animate_color': 4}, {'interaction_granularity': 'invalid'},
                         {'circular_subdivisions': 1}, {'default_brightness': -1},
                         {'animation_range_high': float('nan')}):
            with self.assertRaises(ValueError):
                validate_display(settings)
        validate_display({'animate_color': False, 'segment_subdivisions': 0,
                          'animation_range_low': -100, 'default_color': [0, 0, 1, 1]})

    def test_import_without_neuron_preserves_display_and_replaces_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.producer(directory, '3D Segment', mpi=True)
            snapshot = read_snapshot(path)
            # A second snapshot omits overrides, then a third explicitly changes color.
            snapshot['groups'][0]['display'] = {}
            other = str(Path(directory) / 'other.bnresults')
            write_snapshot(other, snapshot['groups'])
            snapshot['groups'][0]['display'] = {'default_color': [1, 0.5, 0, 1]}
            override = str(Path(directory) / 'override.bnresults')
            write_snapshot(override, snapshot['groups'])
            snapshot['groups'][0]['name'] = 'Replacement'
            snapshot['groups'][0]['display'] = {}
            replacement = str(Path(directory) / 'replacement.bnresults')
            write_snapshot(replacement, snapshot['groups'])
            with BackgroundBlender():
                control = CommNode('Control-Blender')
                script = '''
import bpy
from blenderneuron.blender.offline import import_simulation_results
from blenderneuron.blender.operators.rootgroup import ExportGroupsOperator
node = bpy.types.Object.BlenderNEURON_node
assert node.client is None
assert bpy.ops.blenderneuron.import_simulation_results(filepath=PATH) == {'FINISHED'}
group = node.groups['Network']
assert group.recording_granularity == '3D Segment'
assert len(group.roots) == 2
assert group.view is not None
assert all(len(root.segment_activity[0].times) > 0 for root in group.roots.values())
assert not ExportGroupsOperator.poll(bpy.context)
old_objects = list(bpy.data.objects)
group.default_color = [0, 1, 0, 1]
group.interaction_granularity = 'Section'
import_simulation_results(node, OTHER)
assert list(group.default_color) == [0, 1, 0, 1]
assert group.interaction_granularity == 'Section'
assert len(group.roots) == 2
assert len(bpy.data.objects) == len(old_objects) + 2  # section view instead of cell view
import_simulation_results(node, OVERRIDE)
assert list(group.default_color) == [1, 0.5, 0, 1]
assert node.client is None
before = len(bpy.data.objects)
try:
    import_simulation_results(node, '/does/not/exist.bnresults')
except ValueError:
    pass
else:
    raise AssertionError('Invalid file was accepted')
assert len(bpy.data.objects) == before
import_simulation_results(node, REPLACEMENT)
assert set(node.groups) == {'Replacement'}
assert len(node.root_index) == 2
assert len(bpy.context.scene.BlenderNEURON.groups) == 1
assert node.groups['Replacement'].interaction_granularity == 'Cell'
assert len(bpy.data.objects) == len(old_objects)
bpy.context.scene.BlenderNEURON.simulator_settings.frames_per_ms = 20
return_value = True
'''.replace('PATH', repr(path)).replace('OTHER', repr(other)).replace('OVERRIDE', repr(override)).replace('REPLACEMENT', repr(replacement))
                self.assertTrue(control.client.run_command(script))


if __name__ == '__main__':
    unittest.main()
