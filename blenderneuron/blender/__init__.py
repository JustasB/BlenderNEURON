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

    @staticmethod
    def groups_exist(context):
        """
        Checks if there are any cell groups
        """
        return any(context.scene.BlenderNEURON.groups)

    @staticmethod
    def group_count(context):
        """
        Checks if there are any cell groups
        """
        return len(context.scene.BlenderNEURON.groups.keys())

    @staticmethod
    def imported_groups_exist(context):
        """
        Checks if there are any imported cell groups
        """
        return any([g for g in context.scene.BlenderNEURON.groups if g.node_group.state == 'imported'])

    @staticmethod
    def visible_groups_exist(context):
        """
        Checks if there are any cell groups whose view is visible
        """
        return any([g for g in context.scene.BlenderNEURON.groups if g.node_group.view is not None])

    def get_group_list(self, context):
        return [(g.name, g.name, g.name) for g in context.scene.BlenderNEURON.groups.values()]