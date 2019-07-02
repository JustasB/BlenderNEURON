import bpy
from blenderneuron.addon.utils import blender_launched_neuron_running

class BlenderNEURONPanel(object):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"
    bl_category = "BlenderNEURON"
    bl_label = ""

    def draw(self, context):
        pass

    def set_node(self):
        try:
            self.node = bpy.types.Object.BlenderNEURON_node
        except:
            self.node = None


class blenderneuron_nodes_panel(BlenderNEURONPanel, bpy.types.Panel):
    bl_label = "Node Status"

    def draw(self, context):

        self.set_node()

        if self.node is None or self.node.server is None:
            self.layout.label(text="Blender Node is not running")
            self.layout.prop(context.scene.BlenderNEURON_properties, "server_ip")
            self.layout.prop(context.scene.BlenderNEURON_properties, "server_port")
            self.layout.operator("wm.blenderneuron_node_start", text="Start Blender Node", icon="PLAY")

        else:  # Node is running

            self.layout.label(text="NEURON Client Status")

            col = self.layout.box().column(align=True)

            if self.node.client is None:
                col.label(text="Status: Not Connected", icon="ERROR")
                col.prop(context.scene.BlenderNEURON_properties, "client_ip")
                col.prop(context.scene.BlenderNEURON_properties, "client_port")
                col.separator()
                col.operator("wm.blenderneuron_try_connect_to_neuron", text="Try Connecting to NEURON", icon="PLAY")
                col.separator()

                if not blender_launched_neuron_running():
                    col.prop(context.scene.BlenderNEURON_properties, "neuron_launch_command")
                    col.operator("wm.blenderneuron_launch_neuron", text="Launch NEURON", icon="PLAY")

            else:
                col.label(text="Status: Connected")
                col.label(text="Address: " + self.node.client_address)

            if blender_launched_neuron_running():
                col.prop(context.scene.BlenderNEURON_properties, "neuron_last_command")
                col.separator()
                col.operator("wm.blenderneuron_exec_neuron_command", text="Send Command to NEURON", icon="CONSOLE")
                col.separator()
                col.operator("wm.blenderneuron_stop_neuron", text="Stop NEURON", icon="CANCEL")


            # ----------- #

            self.layout.label(text="Blender Server Status")

            col = self.layout.box().column(align=True)

            if self.node.server is None:
                col.label(text="Node Server Status: Stopped")
            else:
                col.label(text="Status: Listening")
                col.label(text="Address: " + self.node.server_address)

            # ----------- #

            self.layout.operator("wm.blenderneuron_node_stop", text="Stop Blender Node", icon="CANCEL")


class blenderneuron_NEURON_panel(BlenderNEURONPanel, bpy.types.Panel):
    bl_label = "NEURON"

    def draw(self, context):

        self.set_node()

        self.layout.label(text="NEURON Client Status")

        col = self.layout.box().column(align=True)

        if self.node is None or self.node.client is None:
            col.label(text="Status: Not Connected", icon="ERROR")

        else:
            col.label(text="Status: Connected")

        if blender_launched_neuron_running():
            col.label("Blender launched NEURON is running")