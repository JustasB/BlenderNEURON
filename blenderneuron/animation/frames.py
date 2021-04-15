import numpy as np, math

class TimeInfoError(Exception):
    pass


class KeyFrames:
    def __init__(self, signal, time):
        self._signal = signal
        self._time = time

    def get_frames(self, time_window):
        yield from zip(time_window.iterate_keyframes(self), self._signal)

    @property
    def signal(self):
        return self._signal.copy()

    @signal.setter
    def signal(self, value):
        if len(value) != len(self._signal):
            raise ValueError("Can only assign KeyFrame signals when number of frames is the same.")
        self._signal = np.array(value)


class TimeWindow:
    def __init__(self, t_start, t_stop, dt=0.0001, fps=24, f_start=0):
        self._t0 = t_start
        self._tn = t_stop
        self._dt = dt
        self._fps = fps
        self._spf = 1 / fps
        self._ft = int((t_stop - t_start) * fps)
        self._f0 = f_start

    def iterate_keyframes(self, keyframes):
        time = keyframes._time
        if time is None:
            # Yield all frames in order
            yield from np.arange(self._f0, self._f0 + self._ft, dtype=int)
        else:
            # Convert time to frames
            # TODO: Should deal with multiple datapoints per frame. Currently we
            # would use `keyframe_insert` multiple times per frame, resulting in
            # wasted resources and only the last value per frame being used.
            yield from map(self.get_frame, time)

    def get_total_frames(self):
        return math.floor((self._tn - self._t0) * self._fps)

    def get_frame(self, t):
        return self._f0 + (t - self._t0) * self._fps

class TimeSeries:
    def __init__(self, signal, time):
        pass

    def __getitem__(self, key):
        print(key)
