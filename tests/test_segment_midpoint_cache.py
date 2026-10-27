from __future__ import division
"""Geometry-cache equivalence and lifecycle regressions (run inside Docker)."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from neuron import h

from blenderneuron.activity import Activity
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.neuronsection import NeuronSection


def reference_collect(root):
    """Original uncached collector, retained only as a correctness oracle."""
    stack = [root]
    while stack:
        node = stack.pop()
        sec = node.nrn_section
        for i in range(1, int(h.n3d(sec=sec))):
            x = (h.arc3d(i - 1, sec=sec) + h.arc3d(i, sec=sec)) / (2.0 * sec.L)
            x = min(max(x, 0.0), 1.0)
            node.segment_activity.setdefault(i - 1, Activity()).values.append(
                getattr(sec(x), node.group.record_variable))
        stack.extend(reversed(node.children))


class TestSegmentMidpointCache(unittest.TestCase):
    def setUp(self):
        self.sections = []
        self.groups = []

    def tearDown(self):
        for group in self.groups:
            group.close()
        for sec in reversed(self.sections):
            h.delete_section(sec=sec)

    def section(self, points=(0, 20, 100)):
        sec = h.Section()
        self.sections.append(sec)
        sec.nseg = 9
        if points is not None:
            for x in points:
                h.pt3dadd(x, 0, 0, 2, sec=sec)
        return sec

    def group(self, sec):
        group = NeuronRootGroup()
        node = SimpleNamespace(rank_section_name=lambda name: name,
                               section_index={sec.name(): sec})
        group.from_skeletal_blender_group(dict(
            name='cache test', roots=[{'name': sec.name()}],
            record_activity=True, record_variable='v',
            recording_granularity='3D Segment', recording_period=1,
            recording_time_start=0, recording_time_end=0), node)
        self.groups.append(group)
        return group, next(iter(group.roots.values()))

    def test_geometry_construction_and_define_shape(self):
        for points in ((0, 100), (0, 10, 40, 100), None):
            with self.subTest(points=points):
                sec = self.section(points)
                group, root = self.group(sec)
                self.assertGreater(int(h.n3d(sec=sec)), 1)
                root.rebuild_segment_midpoints_recursive()
                expected = tuple(min(max((h.arc3d(i - 1, sec=sec) + h.arc3d(i, sec=sec)) /
                                         (2.0 * sec.L), 0.0), 1.0)
                                 for i in range(1, int(h.n3d(sec=sec))))
                self.assertEqual(root._segment_midpoints, expected)
                self.assertIsInstance(root._segment_midpoints, tuple)

    def test_clamping_and_no_usable_segments(self):
        for arcs, expected in (([-20, 0, 40], (0.0, 1.0)), ([], ()), ([0], ())):
            with self.subTest(arcs=arcs):
                root = NeuronSection()
                root.nrn_section = SimpleNamespace(L=10)
                fake_h = SimpleNamespace(n3d=Mock(return_value=len(arcs)),
                                         arc3d=Mock(side_effect=lambda i, **kw: arcs[i]))
                with patch('blenderneuron.nrn.neuronsection.h', fake_h):
                    root.rebuild_segment_midpoints_recursive()
                self.assertEqual(root._segment_midpoints, expected)

    def test_lazy_cache_reuses_geometry_but_reads_live_values(self):
        group, root = self.group(self.section())
        proxy = Mock(wraps=h)
        with patch('blenderneuron.nrn.neuronsection.h', proxy):
            root.collect_segments_recursive()
            calls = (proxy.n3d.call_count, proxy.arc3d.call_count)
            self.assertGreater(calls[0], 0)
            self.assertGreater(calls[1], 0)
            for value in (-60, -40, 10):
                for seg in root.nrn_section:
                    seg.v = value
                root.collect_segments_recursive()
            self.assertEqual((proxy.n3d.call_count, proxy.arc3d.call_count), calls)
            self.assertEqual(root.segment_activity[0].values[-3:], [-60, -40, 10])
            group.prepare_activity()
            self.assertEqual(proxy.n3d.call_count, 2 * calls[0])
            self.assertEqual(proxy.arc3d.call_count, 2 * calls[1])

    def test_branched_reference_values_variables_and_serialization(self):
        sec = self.section()
        left, right, leaf = self.section((0, 30, 100)), self.section(), self.section()
        left.connect(sec(1))
        right.connect(sec(1))
        leaf.connect(left(1))
        group, root = self.group(sec)
        reference = NeuronSection()
        reference.from_nrn_section(sec, group)
        for variable in ('v', 'diam'):
            group.record_variable = variable
            group.prepare_activity()
            reference.clear_segment_activity()
            for sample in range(5):
                for index, section in enumerate(self.sections):
                    for segment in section:
                        segment.v = -70 + sample + index + segment.x
                root.collect_segments_recursive()
                reference_collect(reference)
            pairs = [(root, reference)]
            while pairs:
                cached, uncached = pairs.pop()
                self.assertEqual(list(cached.segment_activity), list(uncached.segment_activity))
                for key in cached.segment_activity:
                    self.assertEqual(cached.segment_activity[key].values,
                                     uncached.segment_activity[key].values)
                pairs.extend(zip(cached.children, uncached.children))
            self.assertEqual(root.to_dict(), reference.to_dict())
            payload = root.to_dict()
            stack = [payload]
            while stack:
                item = stack.pop()
                self.assertNotIn('_segment_midpoints', item)
                self.assertEqual(sorted(item['segment_activity']), ['0', '1'])
                self.assertEqual([len(trace['values']) for trace in item['segment_activity'].values()], [5, 5])
                stack.extend(item['children'])

    def test_repeated_run_and_direct_neuron_geometry_mutation(self):
        h.load_file('stdrun.hoc')
        sec = self.section()
        group, root = self.group(sec)
        proxy = Mock(wraps=h)
        previous = None
        self.addCleanup(setattr, h, 'tstop', h.tstop)
        self.addCleanup(setattr, h, 'v_init', h.v_init)
        h.tstop = 2.1
        h.v_init = -65
        with patch('blenderneuron.nrn.neuronsection.h', proxy):
            for index, points in enumerate(((0, 20, 100), (0, 80, 100), (0, 80, 100))):
                h.pt3dclear(sec=sec)
                for x in points:
                    h.pt3dadd(x, 0, 0, 2, sec=sec)
                # Sentinels prove initialization clears old traces before
                # the native recorder's time-zero sample is collected.
                group.activity.times = [-999]
                root.segment_activity.setdefault(0, Activity()).values = [999]
                h.run()
                self.assertEqual(root._segment_midpoints, ((points[0] + points[1]) / 200,
                                                          (points[1] + points[2]) / 200))
                self.assertEqual(group.activity.times, [0.0, 1.0, 2.0])
                self.assertEqual(root.segment_activity[0].values, [-65] * 3)
                self.assertEqual(proxy.n3d.call_count, index + 1)
                if index == 2:
                    self.assertEqual(root.to_dict(), previous)
                previous = root.to_dict()

    def test_blender_update_invalidates_and_rebuilds(self):
        group, root = self.group(self.section())
        root.collect_segments_recursive()
        old = root._segment_midpoints
        data = root.to_dict()
        data['coords'] = [0, 0, 0, 80, 0, 0, 100, 0, 0]
        root.update_coords_and_radii(data)
        self.assertIsNone(root._segment_midpoints)
        root.collect_segments_recursive()
        self.assertNotEqual(root._segment_midpoints, old)
        group.prepare_activity()
        for segment in root.nrn_section:
            segment.v = segment.x * 100
        root.collect_segments_recursive()
        reference = NeuronSection()
        reference.from_nrn_section(root.nrn_section, group)
        reference_collect(reference)
        self.assertEqual(root.to_dict(), reference.to_dict())
        root.from_nrn_section(root.nrn_section, group)
        self.assertIsNone(root._segment_midpoints)

    def test_disabled_and_other_granularities_do_not_build_cache(self):
        group, root = self.group(self.section())
        with patch.object(root, 'rebuild_segment_midpoints_recursive') as rebuild:
            for enabled, granularity in ((False, '3D Segment'), (True, 'Cell'), (True, 'Section')):
                group.record_activity = enabled
                group.recording_granularity = granularity
                root.activity.values.append(5)
                group.prepare_activity()
                self.assertEqual(root.activity.values, [])
            rebuild.assert_not_called()
        for granularity in ('Cell', 'Section'):
            group.recording_granularity = granularity
            group.collect()
        self.assertEqual(len(root.activity.values), 2)
        self.assertIsNone(root._segment_midpoints)

    def test_deep_branched_tree_uses_iterative_traversal(self):
        group, root = self.group(self.section())
        current = root
        nodes = [root]
        for index in range(sys.getrecursionlimit() + 20):
            child = NeuronSection()
            child.nrn_section, child.group = root.nrn_section, group
            current.children.append(child)
            nodes.append(child)
            if index % 100 == 0:
                sibling = NeuronSection()
                sibling.nrn_section, sibling.group = root.nrn_section, group
                current.children.append(sibling)
                nodes.append(sibling)
            current = child
        group.prepare_activity()
        for sample in range(3):
            for seg in root.nrn_section:
                seg.v = -60 + sample
            root.collect_segments_recursive()
        for node in nodes:
            self.assertEqual(node._segment_midpoints, root._segment_midpoints)
            self.assertEqual(list(node.segment_activity), [0, 1])
            for activity in node.segment_activity.values():
                self.assertEqual(activity.values, [-60, -59, -58])
        root.to_dict()  # Serialization must be iterative too.
        group.prepare_activity()
        self.assertTrue(all(not node.segment_activity for node in nodes))


if __name__ == '__main__':
    unittest.main()
