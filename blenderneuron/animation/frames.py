import numpy as np

class TimeInfoError(Exception):
    pass


class KeyFrames:
    def __init__(self, signal, time):
        self._signal = signal
        self._time = time

    def get_frames(self, time_window):
        yield from zip(self._signal, time_window.get_frame_iterator(self._time))

    @property
    def signal(self):
        return self._signal.copy()

    @signal.setter
    def signal(self, value):
        if len(value) != len(self._signal):
            raise ValueError("Can only assign KeyFrame signals when number of frames is the same.")
        self._signal = np.array(value)


class TimeWindow:
    def __init__(self, t_start, t_stop, fps, f_start=0):
        self._t0 = t_start
        self._tn = t_stop
        self._fps = fps
        self._spf = 1 / fps
        self._ft = int((t_stop - t_start) * fps)
        self._f0 = f_start

    def get_frame_iterator(self, time=None):
        if time is None:
            # Yield all frames in order
            yield from np.arange(self._f0, self._f0 + self._ft, dtype=int)
        else:
            # Convert time to frames
            yield from (self._f0 + (t - self._t0) * self._fps for t in time)
