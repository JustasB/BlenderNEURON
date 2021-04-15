from . import encoders, frames, properties

class Animator:
    def __init__(self, encoder, property):
        self._encoder = encoder
        self._property = property

    def animate(self, bn_obj, time_window, signal, time=None):
        key_frames = self._encoder.encode(signal, time)
        for frame, value in key_frames.get_frames(time_window):
            self._property.keyframe_insert(bn_obj, frame, value)

def create_window(*args, **kwargs):
    return frames.TimeWindow(*args, **kwargs)
