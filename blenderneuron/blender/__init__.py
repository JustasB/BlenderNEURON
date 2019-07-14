import bpy
from abc import ABCMeta

class BlenderNodeClass:
    __metaclass__ = ABCMeta


    @property
    def node(self):
        if hasattr(bpy.types.Object, "BlenderNEURON_node"):
            return bpy.types.Object.BlenderNEURON_node
        else:
            return None

    @node.setter
    def node(self, value):
        bpy.types.Object.BlenderNEURON_node = value


    @property
    def client(self):
        try:
            return self.node.client
        except:
            return None