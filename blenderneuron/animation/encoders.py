import abc
import numpy as np
from .frames import KeyFrames

class Encoder(abc.ABC):
    @abc.abstractmethod
    def encode(self, signal, time=None):
        pass


class NormEncoder(Encoder):
    def encode(self, signal, time=None):
        signal = np.array(signal, dtype=float)
        signal -= min(signal)
        m = max(signal)
        if m != 0:
            signal /= m
        return KeyFrames(signal, time)


class RangeEncoder(NormEncoder):
    def __init__(self, min, max):
        self._min = min
        self._max = max

    def encode(self, signal, time=None):
        kf = super().encode(signal, time)
        # Modify the range on the normalized signal
        kf.signal = kf.signal * (self._max - self._min) - self._min
        return kf


class RDPEncoder(Encoder):
    def __init__(self, epsilon=0.0):
        self._epsilon = epsilon

    def encode(self, signal, time):
        if len(signal) == 0:
            return KeyFrames(np.zeros(0), np.zeros(0))
        # Make a matrix where times and values are columns
        formatted = np.column_stack((time, signal))
        # Run simplification algorithm
        simplified = _rdp(formatted, epsilon).T
        # Split the result matrix back to individual times and values columns
        time, signal = simplified[0:2]
        return KeyFrames(signal, time)

# Line simplification algorithm using Numpy from:
# https://github.com/fhirschmann/rdp/issues/7

def _line_dists(points, start, end):
    if np.all(start == end):
        return np.linalg.norm(points - start, axis=1)

    vec = end - start
    cross = np.cross(vec, start - points)
    return np.divide(abs(cross), np.linalg.norm(vec))


def _rdp(M, epsilon=0):
    M = np.array(M)
    start, end = M[0], M[-1]
    dists = _line_dists(M, start, end)

    index = np.argmax(dists)
    dmax = dists[index]

    if dmax > epsilon:
        result1 = _rdp(M[:index + 1], epsilon)
        result2 = _rdp(M[index:], epsilon)

        result = np.vstack((result1[:-1], result2))
    else:
        result = np.array([start, end])

    return result

# End line simplification
