from . import encoders, frames, properties


class CalibrationNotSupportedError(Exception):
    pass


class Animator:
    def __init__(self, encoder, property):
        self._encoder = encoder
        self._property = property

    def animate(self, bn_obj, time_window, signal, time=None):
        key_frames = self._encoder.encode(signal, time)
        for frame, value in key_frames.get_frames(time_window):
            self._property.keyframe_insert(bn_obj, frame, value)

    def calibrate(self, min, max):
        try:
            calibrator = getattr(self._encoder, "calibrate")
        except AttributeError:
            raise CalibrationNotSupportedError(f"{type(self._encoder).__name__} does not support calibration.")
        calibrator(min, max)


def create_window(*args, **kwargs):
    return frames.TimeWindow(*args, **kwargs)


def create_animator(encoder=None, property=None, **kwargs):
    if encoder is None:
        encoder = encoders.NormEncoder()
    if property is None:
        property = properties.EmissionProperty()
    return Animator(encoder, property, **kwargs)
