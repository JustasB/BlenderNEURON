import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.rdp_support import load_utils
from tests import rdp_reference
from blenderneuron.activity import Activity
import blenderneuron.activity as activity_module

utils = load_utils()


class TestRDP(unittest.TestCase):
    def compare(self, points, epsilon):
        points = np.asarray(points)
        original = points.copy()
        with np.errstate(all='ignore'):
            expected = rdp_reference.rdp(points, epsilon)
            actual = utils.rdp(points, epsilon)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(points, original)
        self.assertEqual(actual.dtype, expected.dtype)
        self.assertEqual(actual.shape, expected.shape)
        np.testing.assert_array_equal(actual[[0, -1]], points[[0, -1]])

    def test_examples(self):
        examples = [
            [[0, 0]], [[0, 0], [1, 1]],
            [[0, 0], [1, 1], [2, 2], [3, 3]],
            [[0, 0], [1, 3], [2, -2], [3, 0]],
            [[0, 0], [0, 0], [1, 1], [1, 1]],
            [[0, 0], [1, 3], [2, -2], [0, 0]],
            [[0, -65], [.1, -65], [1.3, -65], [7, -65]],
            [[0, -65], [.1, -64], [.4, 30], [.7, -20], [1.2, -75], [5, -65]],
        ]
        for dtype in (np.float32, np.float64, np.int64):
            for points in examples:
                for epsilon in (-1, 0, .1, 1, 100):
                    with self.subTest(points=points, dtype=dtype, epsilon=epsilon):
                        self.compare(np.asarray(points, dtype=dtype), epsilon)

    def test_random_and_extreme_scales(self):
        rng = np.random.RandomState(43)
        for scale in (1e-150, 1e-12, 1, 1e12, 1e150):
            for _ in range(15):
                points = np.column_stack((np.cumsum(rng.uniform(0, 2, 100)), rng.normal(size=100))) * scale
                for epsilon in (0, .1 * scale, scale):
                    self.compare(points, epsilon)

    def test_distance_and_threshold(self):
        rng = np.random.RandomState(9)
        for dimension in (2, 3):
            for dtype in (np.float32, np.float64, np.int64):
                points = (rng.normal(size=(30, dimension)) * 100).astype(dtype)
                for end in (points[-1], points[0]):
                    np.testing.assert_array_equal(
                        utils.line_dists(points, points[0], end),
                        rdp_reference.line_dists(points, points[0], end))
        points = np.array([[0., 0.], [1., 1.], [2., 0.]])
        for epsilon in (np.nextafter(1., 0.), 1., np.nextafter(1., 2.)):
            self.compare(points, epsilon)

    def test_iterative_degenerate_long_trace(self):
        # Negative epsilon splits at the first point even with all distances zero:
        # a recursive implementation would need more than 2,000 stack frames.
        self.compare(np.column_stack((np.arange(2200), np.zeros(2200))), -1)

    def test_empty_compatibility(self):
        with self.assertRaises(IndexError):
            utils.rdp(np.empty((0, 2)))

    def test_activity_alignment(self):
        times = [0., .1, .4, .7, 1.2, 5.]
        values = [-65., -64., 30., -20., -75., -65.]
        expected = rdp_reference.rdp(np.column_stack((times, values)), .1)
        activity = Activity().from_dict(dict(times=times, values=values))
        with patch.multiple(activity_module, np=np, rdp=utils.rdp, numpy_available=True, create=True):
            activity.simplify(.1)
            np.testing.assert_array_equal(activity.times, expected[:, 0])
            np.testing.assert_array_equal(activity.values, expected[:, 1])
            empty = Activity()
            empty.simplify()
            self.assertEqual(empty.times, [])
        self.assertEqual(times, [0., .1, .4, .7, 1.2, 5.])
        self.assertEqual(values, [-65., -64., 30., -20., -75., -65.])


if __name__ == '__main__':
    unittest.main()
