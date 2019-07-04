
import bpy
import os
import time

from blenderneuron.commnode import CommNode
from blenderneuron.addon.utils import *

class blenderneuron_node_start(bpy.types.Operator):
    bl_idname = "wm.blenderneuron_node_start"
    bl_label = "Start BlenderNEURON Blender node"
    bl_description = "Starts a communications node in Blender which creates a server and a client for " \
                     "bi-directional communication with NEURON"

    def execute(self, context):
        # Create the communications node for Blender end
        node = CommNode("Blender")

        # Save it so it's accessible globally from Blender
        bpy.types.Object.BlenderNEURON_node = node

        return {'FINISHED'}


class blenderneuron_node_stop(bpy.types.Operator):
    bl_idname = "wm.blenderneuron_node_stop"
    bl_label = "Stop BlenderNEURON Blender node"
    bl_description = "Stops the Blender node, including the server and any NEURON processes that were " \
                     "started from Blender"

    def execute(self, context):
        bpy.ops.wm.blenderneuron_stop_neuron()

        if hasattr(bpy.types.Object, "BlenderNEURON_node") and \
           bpy.types.Object.BlenderNEURON_node is not None:
                bpy.types.Object.BlenderNEURON_node.stop_server()
                bpy.types.Object.BlenderNEURON_node = None

        return {'FINISHED'}


class blenderneuron_stop_neuron(bpy.types.Operator):
    bl_idname = "wm.blenderneuron_stop_neuron"
    bl_label = "Stop NEURON that was launched from Blender"
    bl_description = "Stops the NEURON process, if any, that was launched from Blender"

    def execute(self, context):
        stop_neuron()

        # If a client was connected, try re-connect or cleanup
        try:
            bpy.types.Object.BlenderNEURON_node.try_setup_client(warn=False)
        except:
            pass

        return {'FINISHED'}



class blenderneuron_launch_neuron(bpy.types.Operator):
    bl_idname = "wm.blenderneuron_launch_neuron"
    bl_label = "Start NEURON from Blender"
    bl_description = "Optionally launch NEURON from Blender. NEURON+BlenderNEURON package can be " \
                     "launched separatelly if needed."

    def execute(self, context):
        bpy.ops.wm.blenderneuron_stop_neuron()

        # Launch a new NEURON process in parallel
        command = context.scene.BlenderNEURON_properties.neuron_launch_command
        launch_neuron(command)

        return {'FINISHED'}



class blenderneuron_try_connect_to_neuron(bpy.types.Operator):
    bl_idname = "wm.blenderneuron_try_connect_to_neuron"
    bl_label = "Attempt to connect to NEURON running a BlenderNEURON node."
    bl_description = "Attemps to connect to NEURON+BlenderNEURON process at the above IP address and port"

    def execute(self, context):
        bpy.types.Object.BlenderNEURON_node.try_setup_client()
        return {'FINISHED'}

class blenderneuron_exec_neuron_command(bpy.types.Operator):
    bl_idname = "wm.blenderneuron_exec_neuron_command"
    bl_label = "Execute a Python command in NEURON"
    bl_description = "Runs a command in NEURON. Printed result is visible in Blender's console window."

    def execute(self, context):
        command = context.scene.BlenderNEURON_properties.neuron_last_command
        bpy.types.Object.BlenderNEURON_node.client.run_command(command)

        return {'FINISHED'}