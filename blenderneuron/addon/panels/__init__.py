import bpy

class BlenderNEURONPanel(object):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"
    bl_category = "BlenderNEURON"
    bl_label = ""

    def draw(self, context):
        pass

    @staticmethod
    def groups_exist(context):
        """
        Checks if there are any cell groups
        """
        return len(context.scene.BlenderNEURON_neuron_cellgroups) > 0

    def set_node(self):
        try:
            self.node = bpy.types.Object.BlenderNEURON_node
        except:
            self.node = None