from __future__ import print_function
"""Blender -> rank-zero RPC -> two-rank simulation -> material animation."""
import json
from pathlib import Path
import tempfile
from textwrap import dedent
import time
import unittest

from blenderneuron.commnode import CommNode
from tests import BackgroundBlender as Blender, BlenderTestCase, NEURON


class MPINEURON(NEURON):
    executable = 'mpiexec'


class TestMPIBlenderSpikes(BlenderTestCase):
    def test_cross_rank_spike_in_blender_animation(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ('--allow-run-as-root -n 2 nrniv -mpi -python '
                    'tests/mpi_blender_spike_worker.py ' + directory)
            with MPINEURON(cmd_args=args) as neuron:
                deadline = time.monotonic() + 30
                while not (Path(directory) / 'ready').exists():
                    self.assertIsNone(neuron.process.poll(), 'MPI worker exited during startup')
                    self.assertLess(time.monotonic(), deadline, 'MPI coordinator startup timed out')
                    time.sleep(.05)
                with Blender(), CommNode('Control-Blender') as control:
                    result = control.client.run_command(dedent('''
                        import numpy as np
                        bpy.ops.blenderneuron.get_cell_list_from_neuron()
                        ui = bpy.context.scene.BlenderNEURON.groups[0]
                        group = ui.node_group
                        assert sorted(group.roots) == ['Cell[0].soma', 'Cell[1].soma']
                        ui.record_activity = True
                        ui.recording_period = 0.1
                        ui.record_variable = 'v'
                        ui.interaction_granularity = 'Cell'
                        settings = bpy.context.scene.BlenderNEURON.simulator_settings
                        settings.frames_per_ms = 10
                        bpy.ops.blenderneuron.init_and_run_neuron()
                        reports = {}
                        for level in ('Cell', 'Section', '3D Segment'):
                            ui.recording_granularity = level
                            bpy.ops.blenderneuron.import_groups()
                            assert len(group.roots) == 2
                            cells = []
                            for name, root in sorted(group.roots.items()):
                                traces = (list(root.segment_activity.values())
                                          if level == '3D Segment' else [root.activity])
                                assert len(traces) == (2 if level == '3D Segment' else 1)
                                summaries = []
                                for activity in traces:
                                    assert len(activity.times) == len(activity.values) > 10
                                    times = np.asarray(activity.times)
                                    values = np.asarray(activity.values)
                                    peak = int(np.argmax(values))
                                    crossings = np.flatnonzero((values[:-1] < 0) & (values[1:] >= 0))
                                    assert len(crossings) == 1, (name, level, crossings)
                                    summaries.append({'peak_ms': float(times[peak]),
                                                      'peak_mV': float(values[peak]),
                                                      'spike_ms': float(times[crossings[0] + 1])})
                                cells.append({'name': name, 'traces': summaries})
                            # Inspect the actual material F-curves and scrub the target cell.
                            target_name = 'Cell[1].soma'
                            material_names = ([target_name + '[0]', target_name + '[1]']
                                              if level == '3D Segment' else [target_name])
                            materials = []
                            for material_name in material_names:
                                mat = group.view.materials[material_name]
                                action = mat.animation_data.action
                                if hasattr(action, 'fcurve_ensure_for_datablock'):
                                    curve = action.fcurve_ensure_for_datablock(mat, '["recorded_value"]')
                                else:
                                    curve = action.fcurves.find('["recorded_value"]')
                                peak_point = max(curve.keyframe_points, key=lambda p: p.co.y)
                                bpy.context.scene.frame_set(0)
                                resting = float(mat['recorded_value'])
                                resting_strength = float(mat.node_tree.nodes['Emission'].inputs['Strength'].default_value)
                                bpy.context.scene.frame_set(int(round(peak_point.co.x)))
                                animated = float(mat['recorded_value'])
                                strength = float(mat.node_tree.nodes['Emission'].inputs['Strength'].default_value)
                                assert resting < -60 and animated > 20
                                assert strength > resting_strength
                                materials.append({'name': material_name, 'rest_mV': resting,
                                                  'animated_peak_mV': animated,
                                                  'peak_frame': float(peak_point.co.x),
                                                  'rest_strength': resting_strength, 'peak_strength': strength})
                            reports[level] = {'cells': cells, 'materials': materials}
                        return_value = reports
                    '''))
                    for level, report in result.items():
                        source, target = report['cells']
                        for trace in target['traces']:
                            self.assertGreater(trace['peak_mV'], 20, level)
                            self.assertGreater(trace['spike_ms'], source['traces'][0]['spike_ms'] + 2, level)
                    print('MPI_BLENDER_ANIMATION_RESULT=' + json.dumps(result, sort_keys=True), flush=True)
                (Path(directory) / 'stop').touch()
                self.assertEqual(neuron.process.wait(timeout=15), 0)
                records = [json.loads((Path(directory) / ('rank-%d.json' % rank)).read_text())
                           for rank in range(2)]
                self.assertTrue(records[0]['server'])
                self.assertFalse(records[1]['server'])
                for record in records:
                    self.assertEqual(len(record['spikes_ms']), 1)
                    self.assertAlmostEqual(record['time_ms'], 25)
                self.assertAlmostEqual(records[0]['spikes_ms'][0], 6.2, places=6)
                self.assertAlmostEqual(records[1]['spikes_ms'][0], 8.625, places=6)


if __name__ == '__main__':
    unittest.main()
