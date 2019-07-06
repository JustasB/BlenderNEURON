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

    def get_group(self, context):
        """
        Returns the currently selected cell group

        :param context:
        :return:
        """
        scene = context.scene

        # Get the group for which the list of cells will be shown
        group_index = scene.BlenderNEURON_neuron_cellgroups_index
        group = scene.BlenderNEURON_neuron_cellgroups[group_index]

        return group

    def get_sim_settings(self, context):
        """
        Returns the simulator settings

        :param context:
        :return:
        """
        return context.scene.BlenderNEURON_simulator_settings

    def set_node(self):
        try:
            self.node = bpy.types.Object.BlenderNEURON_node
        except:
            self.node = None