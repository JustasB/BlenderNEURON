import abc, numpy as np

class Property(abc.ABC):
    @abc.abstractmethod
    def keyframe_insert(self, obj, frame, value):
        pass


class ColorProperty(Property):
    def keyframe_insert(self, obj, frame, value):
        c = np.ones(4)
        c[0] = value
        obj.color = c
        obj.keyframe_insert(data_path="color", frame=frame)


class EmissionProperty(Property):
    def keyframe_insert(self, obj, frame, value):
        emit_strength = obj.node_tree.nodes["Emission"].inputs[1]
        emit_strength.default_value = value
        emit_strength.keyframe_insert(data_path="default_value", frame=frame)
