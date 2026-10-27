"""Real NEURON coverage of direct and dotted recording names (run in Docker)."""
import unittest
from types import SimpleNamespace

from neuron import h

from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.offline import SimulationExport


class TestRecordingVariables(unittest.TestCase):
    def setUp(self):
        h.load_file('stdrun.hoc')
        h.CVode().active(0)
        self.sections = [h.Section(name='recording_soma'), h.Section(name='recording_dend')]
        self.sections[1].connect(self.sections[0](1))
        for sec in self.sections:
            sec.nseg = 3
            for x in (0, 20, 60, 100):
                h.pt3dadd(x, 0, 0, 2, sec=sec)
            sec.insert('pas')
            sec.insert('hh')
        self.groups = []

    def tearDown(self):
        for group in self.groups:
            group.close()
        for sec in reversed(self.sections):
            h.delete_section(sec=sec)

    def group(self, level, variable):
        group = NeuronRootGroup()
        self.groups.append(group)
        node = SimpleNamespace(rank_section_name=lambda name: name,
                               section_index={sec.name(): sec for sec in self.sections})
        group.from_skeletal_blender_group(dict(
            name='variables', roots=[{'name': self.sections[0].name()}],
            record_activity=True, record_variable=variable, recording_granularity=level,
            recording_period=.1, recording_time_start=0, recording_time_end=0), node)
        return group

    def test_live_values_at_every_granularity(self):
        readers = {'v': lambda seg: seg.v, 'i_pas': lambda seg: seg.i_pas,
                   'pas.i': lambda seg: seg.pas.i, 'hh.m': lambda seg: seg.hh.m}
        for level in ('Cell', 'Section', '3D Segment'):
            for variable, read in readers.items():
                with self.subTest(level=level, variable=variable):
                    group = self.group(level, variable)
                    root = next(iter(group.roots.values()))
                    nodes = [root, root.children[0]]
                    h.finitialize(-65)
                    group.prepare_activity()
                    for sample in range(2):
                        for i, sec in enumerate(self.sections):
                            for seg in sec:
                                seg.v = -60 + 10 * sample + 5 * i + seg.x
                                seg.hh.m = .1 + .1 * sample + .01 * i + .01 * seg.x
                        h.fcurrent()
                        group.collect()
                        if level in ('Cell', 'Section'):
                            for node in nodes[:1] if level == 'Cell' else nodes:
                                self.assertAlmostEqual(node.activity.values[-1], read(node.nrn_section(.5)))
                            if level == 'Cell':
                                self.assertEqual(nodes[1].activity.values, [])
                        else:
                            for node in nodes:
                                self.assertEqual(len(node.segment_activity), 3)
                                for i, x in enumerate(node._segment_midpoints):
                                    self.assertAlmostEqual(node.segment_activity[i].values[-1], read(node.nrn_section(x)))
                    self.assertEqual(len(group.activity.times), 2)
                    group.close()

    def test_offline_dotted_current_survives_simulation_and_export(self):
        export = SimulationExport()
        export.add_group('dotted', [self.sections[0]], recording_granularity='3D Segment',
                         record_variable='pas.i', recording_period=.1)
        export.add_group('empty rank', [], record_variable='pas.i')
        export.prepare()
        self.groups.extend(export.groups.values())
        h.dt = .025
        h.finitialize(-50)
        h.continuerun(.2)
        result = export._local_results()[0]
        self.assertEqual(result['record_variable'], 'pas.i')
        self.assertEqual(len(result['activity']['times']), 3)
        nodes = [result['roots'][0], result['roots'][0]['children'][0]]
        for node in nodes:
            self.assertEqual(len(node['segment_activity']), 3)
            for activity in node['segment_activity'].values():
                self.assertEqual(len(activity['values']), 3)
                self.assertTrue(all(isinstance(value, float) for value in activity['values']))

    def test_invalid_paths_and_expressions_have_contextual_errors(self):
        for variable in ('missing.i', 'pas.missing', 'pas..i', 'ina + ik'):
            with self.subTest(variable=variable):
                export = SimulationExport().add_group('invalid', [self.sections[0]], record_variable=variable)
                with self.assertRaisesRegex(ValueError, 'Group.*invalid.*missing variable'):
                    export.prepare()
        # A disabled collector must not try to resolve even an invalid path.
        disabled = SimulationExport().add_group('disabled', [self.sections[0]],
                                                record_variable='missing.i', record_activity=False).prepare()
        self.assertFalse(hasattr(disabled.groups['disabled'], 'collector_con'))


if __name__ == '__main__':
    unittest.main()
