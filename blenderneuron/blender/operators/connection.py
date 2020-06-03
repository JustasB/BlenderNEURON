
import bpy

from blenderneuron.blender.blendernode import BlenderNode
from blenderneuron.blender.utils import *
from blenderneuron.blender import BlenderNodeClass

class NodeStartOpearator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.node_start"
    bl_label = "Start BlenderNEURON Blender node"
    bl_description = "Starts a communications node in Blender which creates a server and a client for " \
                     "bi-directional communication with NEURON"

    modal_timer = None
    modal_timer_period = 0.1  # in seconds
    servicing = False

    def execute(self, context):
        def on_client_connected(self):
            # Pull NRN sim params to Blender GUI
            context.scene.BlenderNEURON.simulator_settings.from_neuron()

        # Create the communications node for Blender end
        self.node = BlenderNode(
            on_client_connected=on_client_connected
        )

        # Clear existing UI groups (if any, eg. saved)
        context.scene.BlenderNEURON.clear()

        if self.client is not None:
            # Add a cell group (will contain all root sections by default)
            self.node.add_group()

            # Add a blank synapse set
            self.node.add_synapse_set()

        # Create a timer that will trigger task queue servicing during modal operator events
        # If the queue is serviced during other times, it results in intermittent Blender segfaults
        # These happen when the queue task is creating/freeing a blender object, but some other Blender thread
        # is accessing its data e.g. during UI updates
        # Performing task servicing during modal operator calls is the recommended way to asynchronously update scenes
        self.node.service_thread_continue = False
        wm = context.window_manager
        self.modal_timer = wm.event_timer_add(self.modal_timer_period, context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):

        if not self.servicing and event.type == 'TIMER':
            self.servicing = True

            try:
                if self.node is not None:
                    self.node.work_on_queue_tasks()

            finally:
                self.servicing = False

        return {'PASS_THROUGH'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self.modal_timer)


class NodeStopOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.node_stop"
    bl_label = "Stop BlenderNEURON Blender node"
    bl_description = "Stops the Blender node, including the server and any NEURON processes that were " \
                     "started from Blender"

    def execute(self, context):
        bpy.ops.blenderneuron.stop_neuron()

        if hasattr(bpy.types.Object, "BlenderNEURON_node") and \
           bpy.types.Object.BlenderNEURON_node is not None:
                bpy.types.Object.BlenderNEURON_node.stop_server()
                bpy.types.Object.BlenderNEURON_node = None

        return {'FINISHED'}


class StopNeuronOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.stop_neuron"
    bl_label = "Stop NEURON that was launched from Blender"
    bl_description = "Stops the NEURON process, if any, that was launched from Blender"

    def execute(self, context):
        # raise NotImplementedError('NOT SUPPORTED')

        try:
            bpy.ops.blenderneuron.remove_all_groups()
        except:
            pass

        stop_neuron()

        # If a client was connected, try re-connect or cleanup
        try:
            bpy.types.Object.BlenderNEURON_node.try_setup_client(warn=False)
        except:
            pass

        return {'FINISHED'}



class LaunchNeuronOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.launch_neuron"
    bl_label = "Start NEURON from Blender"
    bl_description = "Optionally launch NEURON from Blender. NEURON+BlenderNEURON package can be " \
                     "launched separatelly if needed."

    def execute(self, context):
        # raise NotImplementedError('NOT SUPPORTED')

        bpy.ops.blenderneuron.stop_neuron()

        # Launch a new NEURON process in parallel
        command = context.scene.BlenderNEURON_properties.neuron_launch_command
        launch_neuron(command)

        return {'FINISHED'}



class TryConnectToNeuronOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.try_connect_to_neuron"
    bl_label = "Attempt to connect to NEURON running a BlenderNEURON node."
    bl_description = "Attemps to connect to NEURON+BlenderNEURON process at the above IP address and port"

    def execute(self, context):
        bpy.types.Object.BlenderNEURON_node.try_setup_client()
        return {'FINISHED'}

class ExecNeuronCommandOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.exec_neuron_command"
    bl_label = "Execute a Python command in NEURON"
    bl_description = "Runs a command in NEURON. Printed result is visible in Blender's console window."

    def execute(self, context):
        command = context.scene.BlenderNEURON_properties.neuron_last_command
        bpy.types.Object.BlenderNEURON_node.client.run_command(command)

        return {'FINISHED'}