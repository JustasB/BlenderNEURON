import abc, numpy as np

class Property(abc.ABC):
    def __init_subclass__(cls, data_path=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._dp = data_path

    def keyframe_insert(self, obj, frame, value):
        self.set(obj, value)
        obj.keyframe_insert(data_path=self._dp, frame=frame)

    @abc.abstractmethod
    def set(self, obj, value):
        pass

class ColorProperty(Property, data_path="color"):
    def __init__(self):
        pass

    def set(self, obj, value):
        c = np.ones(4)
        c[0] = value
        obj.color = c
