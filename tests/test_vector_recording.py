"""Native recorder equivalence and ownership regressions; run inside Docker."""
import gc
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import patch

from neuron import h

from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.neuronsection import NeuronSection
from blenderneuron.nrn.recording import VectorRecorder, get_recording_value


class TestVectorRecording(unittest.TestCase):
    def setUp(self):
        h.load_file('stdrun.hoc')
        h.CVode().active(0)
        h.CVode().use_local_dt(0)
        h.dt = .025
        self.sections = [h.Section(name='vector_soma'), h.Section(name='vector_dend')]
        self.sections[1].connect(self.sections[0](1))
        for sec in self.sections:
            sec.nseg = 3
            for x in range(0, 101, 10):
                h.pt3dadd(x, 0, 0, 2, sec=sec)
            sec.insert('hh')
            sec.insert('pas')
        self.clamp = h.IClamp(self.sections[0](.5))
        self.clamp.delay, self.clamp.dur, self.clamp.amp = .15, .2, .5
        self.groups = []

    def tearDown(self):
        for group in self.groups:
            group.close()
        h.CVode().active(0)
        h.CVode().use_local_dt(0)
        for sec in reversed(self.sections):
            h.delete_section(sec=sec)

    def group(self, level='3D Segment', variable='v', start=0, end=0):
        group = NeuronRootGroup()
        self.groups.append(group)
        node = SimpleNamespace(rank_section_name=lambda name: name,
                               section_index={sec.name(): sec for sec in self.sections})
        group.from_skeletal_blender_group(dict(
            name='vectors', roots=[{'name': self.sections[0].name()}], record_activity=True,
            record_variable=variable, recording_granularity=level, recording_period=.1,
            recording_time_start=start, recording_time_end=end), node)
        return group

    def targets(self, group):
        stack = list(reversed(list(group.roots.values())))
        while stack:
            node = stack.pop()
            if group.recording_granularity == '3D Segment':
                for i, x in enumerate(node._segment_midpoints):
                    yield node.nrn_section(x), node.segment_activity[i]
            else:
                yield node.nrn_section(.5), node.activity
            if group.recording_granularity != 'Cell':
                stack.extend(reversed(node.children))

    def test_matches_callback_for_voltage_currents_and_gating(self):
        for solver in (0, 1):
            h.CVode().active(solver)
            h.CVode().atol(1e-7)
            for level in ('Cell', 'Section', '3D Segment'):
                for variable in ('v', 'ina', 'pas.i', 'hh.m'):
                    with self.subTest(solver=solver, level=level, variable=variable):
                        group = self.group(level, variable, .013, .45)
                        expected = []
                        stim = h.NetStim()
                        stim.start, stim.interval, stim.number, stim.noise = .013, .1, 5, 0
                        connection = h.NetCon(stim, None)
                        connection.record(lambda: expected.append([
                            get_recording_value(seg, variable) for seg, _ in self.targets(group)]))
                        h.finitialize(-60)
                        h.continuerun(.6)
                        self.assertEqual(len(expected), 5)
                        self.assertEqual(len(group.activity.times), 5)
                        for i, (seg, activity) in enumerate(self.targets(group)):
                            self.assertEqual(len(activity.values), 5)
                            for j, value in enumerate(activity.values):
                                self.assertAlmostEqual(value, expected[j][i], places=7)
                        group.close()
                        connection.record('')
                        connection = stim = None

    def test_unknown_stop_and_continuation_across_schedule_extensions(self):
        with patch.object(VectorRecorder, 'BLOCK_SIZE', 4):
            group = self.group(start=.013)
            h.tstop = .01  # Neither the recording plan nor continuerun uses this as a bound.
            h.finitialize(-65)
            h.continuerun(.23)
            before = group.to_dict(True, True, True)
            h.continuerun(.83)
            times = list(group.activity.times)
            self.assertEqual(len(times), 9)
            for i, time in enumerate(times):
                self.assertAlmostEqual(time, .013 + .1 * i)
            self.assertEqual(before['activity']['times'], times[:3])
            root = next(iter(group.roots.values()))
            self.assertEqual(len(root.segment_activity[0].values), 9)
            self.assertIs(root.segment_activity[0].values.vector, root.segment_activity[1].values.vector)
            self.assertEqual(len(group._recorder.vectors), 6)
            self.assertFalse(hasattr(root.segment_activity[0].values, 'append'))
            self.assertFalse(hasattr(group.activity.times, 'append'))
            self.assertLessEqual(len(group._recorder.schedule), 9 + 4)
            self.assertEqual(list(root.segment_activity[0].values)[-1], root.segment_activity[0].values[-1])
            self.assertEqual(root.segment_activity[0].values[:2], list(root.segment_activity[0].values)[:2])

    def test_rebuild_for_granularity_variable_geometry_and_disabled_recording(self):
        group = self.group()
        root = next(iter(group.roots.values()))
        previous = None
        previous_vectors = []
        for level, variable in (('3D Segment', 'v'), ('Cell', 'pas.i'),
                                ('Section', 'hh.m'), ('3D Segment', 'ina')):
            settings = {key: getattr(group, key) for key in (
                'record_activity', 'record_variable', 'recording_granularity',
                'recording_period', 'recording_time_start', 'recording_time_end')}
            settings.update(recording_granularity=level, record_variable=variable)
            group.save_recording_params(settings)
            self.sections[0].nseg += 2
            h.finitialize(-60)
            if previous is not None:
                self.assertFalse(previous.active)
            lengths = [len(vector) for vector in previous_vectors]
            h.continuerun(.23)
            self.assertEqual([len(vector) for vector in previous_vectors], lengths)
            self.assertEqual(list(group.activity.times), [0, .1, .2])
            if level == 'Cell':
                self.assertEqual(len(group._recorder.vectors), 1)
                self.assertEqual(root.segment_activity, {})
                self.assertEqual(root.children[0].activity.values, [])
            elif level == 'Section':
                self.assertEqual(len(group._recorder.vectors), 2)
            previous = group._recorder
            previous_vectors = list(previous.vectors)
        group.record_activity = False
        h.finitialize(-60)
        h.continuerun(.23)
        self.assertIsNone(group._recorder)
        self.assertEqual(group.activity.times, [])
        self.assertEqual(root.segment_activity, {})

    def test_inclusive_end_and_window_outside_run(self):
        group = self.group('Cell', start=2, end=20)
        h.finitialize(-60)
        self.assertEqual(len(group.activity.times), 0)
        h.continuerun(21)
        self.assertEqual(len(group.activity.times), 181)
        self.assertEqual(group.activity.times[-1], 20)
        for time, expected in zip(group.activity.times[-3:], (19.8, 19.9, 20)):
            self.assertAlmostEqual(time, expected)
        count = len(group.activity.times)
        h.continuerun(22)
        self.assertEqual(len(group.activity.times), count)

    def test_group_deletion_detaches_vectors_and_pending_callbacks(self):
        with patch.object(VectorRecorder, 'BLOCK_SIZE', 4):
            group = self.group()
            h.finitialize(-65)
            h.continuerun(.12)
            vectors = list(group._recorder.vectors)
            counts = [len(vector) for vector in vectors]
            group_ref = weakref.ref(group)
            self.groups.clear()
            del group
            gc.collect()
            self.assertIsNone(group_ref())
            h.continuerun(1)
            self.assertTrue(all(len(vector) <= count + 1 for vector, count in zip(vectors, counts)))
            drained = [len(vector) for vector in vectors]
            h.continuerun(2)
            self.assertEqual([len(vector) for vector in vectors], drained)

    def test_local_variable_timestep_schedule(self):
        h.CVode().use_local_dt(1)
        h.CVode().active(1)
        with patch.object(VectorRecorder, 'BLOCK_SIZE', 4):
            group = self.group('Section', 'pas.i', .013, .85)
            # A second independent cell advances on a different local clock.
            other = h.Section(name='independent_cell')
            self.sections.append(other)
            h.pt3dadd(0, 0, 0, 2, sec=other)
            h.pt3dadd(20, 0, 0, 2, sec=other)
            other.insert('pas')
            root = NeuronSection()
            root.from_nrn_section(other, group)
            group.roots[root.name] = root
            h.finitialize(-60)
            h.continuerun(.83)
            self.assertEqual(len(group.activity.times), 9)
            for seg, activity in self.targets(group):
                self.assertEqual(len(activity.values), 9)
            old_vectors = list(group._recorder.vectors)
            group.close()
            counts = [len(vector) for vector in old_vectors]
            h.continuerun(1)
            self.assertTrue(all(len(vector) <= count + 1 for vector, count in zip(old_vectors, counts)))


if __name__ == '__main__':
    unittest.main()
