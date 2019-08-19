import bpy
from blenderneuron.blender import BlenderNodeClass

class AbstractBlenderNEURONPanel(BlenderNodeClass):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"
    bl_category = "BlenderNEURON"
    bl_label = ""

    def draw(self, context):
        pass

    def get_group(self, context):
        """
        Returns the currently selected cell group

        :param context:
        :return:
        """
        scene = context.scene

        # Get the group for which the list of cells will be shown
        group_index = scene.BlenderNEURON.groups_index
        group = scene.BlenderNEURON.groups[group_index]

        return group

    def get_sim_settings(self, context):
        """
        Returns the simulator settings

        :param context:
        :return:
        """
        return context.scene.BlenderNEURON.simulator_settings

    def get_synapse_set(self, context):
        """
        Returns the synapse connector settings

        :param context:
        :return:
        """
        return context.scene.BlenderNEURON.synapse_set

    def set_node(self):
        try:
            self.node = bpy.types.Object.BlenderNEURON_node
        except:
            self.node = None