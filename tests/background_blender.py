"""Serve production BlenderNode tasks on the main thread without a UI loop.

The GUI operator's modal timer is intentionally not used in background mode.
Every test still gets a fresh Blender process, owned by the normal test helper.
"""
import time
import bpy
import blenderneuron
from blenderneuron.blender.blendernode import BlenderNode


class MainThreadNode(BlenderNode):
    def setup_server(self, service_queue=True):
        return super().setup_server(service_queue=False)


if not hasattr(bpy.context.scene, 'BlenderNEURON'):
    blenderneuron.register()


def connected(node):
    bpy.context.scene.BlenderNEURON.simulator_settings.from_neuron()


node = MainThreadNode(on_client_connected=connected)
bpy.types.Object.BlenderNEURON_node = node
bpy.context.scene.BlenderNEURON.clear()
if node.client is not None:
    node.add_group()
    node.add_synapse_set()
try:
    while True:  # The parent enforces startup/test deadlines and owns cleanup.
        node.work_on_queue_tasks()
        time.sleep(.01)
finally:
    node.stop_server()
