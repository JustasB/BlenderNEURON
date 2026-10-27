import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.rdp_support import load_utils
from blenderneuron.activity import Activity
import blenderneuron.activity as activity_module

utils = load_utils()


class TestRDP(unittest.TestCase):
    def check_expected(self, points, epsilon, indices):
        points = np.asarray(points)
        original = points.copy()
        expected = points[indices]
        with np.errstate(all='ignore'):
            actual = utils.rdp(points, epsilon)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(points, original)
        self.assertEqual(actual.dtype, expected.dtype)
        self.assertEqual(actual.shape, expected.shape)
        np.testing.assert_array_equal(actual[[0, -1]], points[[0, -1]])

    def test_examples(self):
        # Explicit retained indices, not outputs computed by another RDP.
        # A singleton retains both endpoint entries for compatibility.
        examples = [
            ([[0, 0]], .1, [0, 0]),
            ([[0, 0], [1, 1]], .1, [0, 1]),
            ([[0, 0], [1, 1], [2, 2], [3, 3]], 0, [0, 3]),
            ([[0, 0], [1, 1], [2, 2], [3, 3]], -1, [0, 1, 2, 3]),
            ([[0, 0], [1, 3], [2, -2], [3, 0]], .1, [0, 1, 2, 3]),
            ([[0, 0], [1, 3], [2, -2], [3, 0]], 100, [0, 3]),
            ([[0, 0], [0, 0], [1, 1], [1, 1]], 0, [0, 3]),
            ([[0, 0], [1, 3], [2, -2], [0, 0]], .1, [0, 1, 2, 3]),
            ([[0, 0], [0, 0], [0, 0]], 0, [0, 2]),
            ([[0, 0], [0, 1], [0, 2]], 0, [0, 2]),
            # Equal distances: the first maximum is selected deterministically.
            ([[0, 0], [1, 1], [2, 1], [3, 0]], .75, [0, 1, 3]),
        ]
        for dtype in (np.float32, np.float64, np.int64):
            for points, epsilon, indices in examples:
                with self.subTest(points=points, dtype=dtype, epsilon=epsilon):
                    self.check_expected(np.asarray(points, dtype=dtype), epsilon, indices)

    def test_random_and_extreme_scales(self):
        rng = np.random.RandomState(43)
        for scale in (1e-150, 1e-12, 1, 1e12, 1e150):
            triangle = np.array([[0., 0.], [1., 1.], [2., 0.]]) * scale
            self.check_expected(triangle, .5 * scale, [0, 1, 2])
            self.check_expected(triangle, 2 * scale, [0, 2])
            for _ in range(15):
                points = np.column_stack((np.cumsum(rng.uniform(0, 2, 100)), rng.normal(size=100))) * scale
                for epsilon in (0, .1 * scale, scale):
                    original = points.copy()
                    actual = utils.rdp(points, epsilon)
                    np.testing.assert_array_equal(points, original)
                    self.assertEqual(actual.dtype, points.dtype)
                    np.testing.assert_array_equal(actual[[0, -1]], points[[0, -1]])
                    # Increasing time makes each retained point's index unique.
                    indices = np.searchsorted(points[:, 0], actual[:, 0])
                    self.assertTrue(np.all(np.diff(indices) > 0))
                    np.testing.assert_array_equal(actual, points[indices])
                    # Independent geometric invariant: every discarded point
                    # lies within epsilon of its retained span's infinite line.
                    # Normalize first to keep the error check well-conditioned.
                    normalized = points / scale
                    for left, right in zip(indices[:-1], indices[1:]):
                        delta = normalized[right] - normalized[left]
                        offset = normalized[left:right + 1] - normalized[left]
                        distances = abs(delta[0] * offset[:, 1] - delta[1] * offset[:, 0]) / np.hypot(*delta)
                        self.assertLessEqual(distances.max(), epsilon / scale + 1e-12)

    def test_distance_and_threshold(self):
        for dtype in (np.float32, np.float64, np.int64):
            points = np.array([[0, 0], [3, 4], [6, 0]], dtype=dtype)
            np.testing.assert_array_equal(utils.line_dists(points, points[0], points[-1]), [0, 4, 0])
            np.testing.assert_array_equal(utils.line_dists(points, points[0], points[0]), [0, 5, 6])
            # Exercise the generic 3D fallback and coincident-endpoint branch.
            points3 = np.array([[0, 0, 0], [0, 3, 4], [5, 0, 0]], dtype=dtype)
            np.testing.assert_array_equal(utils.line_dists(points3, points3[0], points3[-1]),
                                          [[0, 0, 0], [0, 4, 3], [0, 0, 0]])
            np.testing.assert_array_equal(utils.line_dists(points3, points3[0], points3[0]), [0, 5, 5])
        points = np.array([[0., 0.], [1., 1.], [2., 0.]])
        self.check_expected(points, np.nextafter(1., 0.), [0, 1, 2])
        self.check_expected(points, 1., [0, 2])
        self.check_expected(points, np.nextafter(1., 2.), [0, 2])

    def test_iterative_degenerate_long_trace(self):
        # Negative epsilon splits at the first point even with all distances zero:
        # a recursive implementation would need more than 2,000 stack frames.
        self.check_expected(np.column_stack((np.arange(2200), np.zeros(2200))), -1, list(range(2200)))

    def test_empty_compatibility(self):
        with self.assertRaises(IndexError):
            utils.rdp(np.empty((0, 2)))

    def test_list_and_noncontiguous_inputs(self):
        points = [[0, 0], [1, 1], [2, 2]]
        np.testing.assert_array_equal(utils.rdp(points, 0), [[0, 0], [2, 2]])
        self.assertEqual(points, [[0, 0], [1, 1], [2, 2]])
        view = np.column_stack((np.arange(10), np.arange(10)))[::2]
        self.assertFalse(view.flags.c_contiguous)
        self.check_expected(view, 0, [0, 4])

    def test_activity_alignment(self):
        times = [0., .5, 1., 1.5, 2., 2.5, 3., 3.5, 4.]
        values = [-65., -65., -65., -15., 35., -15., -65., -65., -65.]
        original_times, original_values = list(times), list(values)
        expected = np.array([[0., -65.], [1., -65.], [2., 35.], [3., -65.], [4., -65.]])
        activity = Activity().from_dict(dict(times=times, values=values))
        with patch.multiple(activity_module, np=np, rdp=utils.rdp, numpy_available=True, create=True):
            activity.simplify(.1)
            np.testing.assert_array_equal(activity.times, expected[:, 0])
            np.testing.assert_array_equal(activity.values, expected[:, 1])
            empty = Activity()
            empty.simplify()
            self.assertEqual(empty.times, [])
        self.assertEqual(times, original_times)
        self.assertEqual(values, original_values)


if __name__ == '__main__':
    unittest.main()
