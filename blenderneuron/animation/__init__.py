from . import encoders, frames

class Animator:
    def __init__(self, encoder, property, time_window):
        self._encoder = encoder
        self._property = property
        self._time_window = time_window

    def animate(self, bn_obj, time_window, signal, time=None):
        key_frames = self._encoder.encode(signal, time)
        for frame, value in key_frames.get_frames(time_window):
            self._property.keyframe_insert(bn_obj, frame, value)

def create_window(*args, **kwargs):
    return frames.TimeWindow(*args, **kwargs)
