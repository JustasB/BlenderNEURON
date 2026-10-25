bl_info = {
    "name": "BlenderNEURON",
    "description": "A Blender GUI for NEURON simulator",
    "author": "Justas Birgiolas, Alistair Peet",
    "version": (2, 1, 3),
    "blender": (5, 2, 0),
    "location": "3D View > Right Sidebar > BlenderNEURON",
    "wiki_url": "BlenderNEURON.org",
    "tracker_url": "https://github.com/JustasB/BlenderNEURON/issues",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

vars = {}

try:
    import bpy
    inside_blender = True
except:
    inside_blender = False


import os
if 'COVERAGE_PROCESS_START' in os.environ:
    try:
        print('Importing COVERAGE: Inside ', "BLENDER" if inside_blender else "NEURON")
        import coverage
        COV = coverage.process_startup()
    except:
        print('Coverage error. Skipping coverage')

if inside_blender:
    from bpy.app.handlers import persistent

    import blenderneuron
    from blenderneuron.commnode import CommNode

    from blenderneuron.blender.operators.connection import *
    from blenderneuron.blender.panels.connection import *
    from blenderneuron.blender.properties.connection import *

    from blenderneuron.blender.operators.rootgroup import *
    from blenderneuron.blender.panels.rootgroup import *
    from blenderneuron.blender.properties.rootgroup import *

    from blenderneuron.blender.utils import register_module_classes

    import sys

    def start_node_after_load():
        # CLI file loading can run both startup and load handlers. Wait until
        # Blender returns to its event loop before publishing the RPC server.
        existing = getattr(bpy.types.Object, "BlenderNEURON_node", None)
        if existing is not None:
            existing.stop_server()
        bpy.ops.blenderneuron.node_start()
        return None

    @persistent
    def save_dataset_state(scene):
        from blenderneuron.blender.dataset import save_offline_state
        save_offline_state(scene)

    def schedule_node_start():
        if not bpy.app.timers.is_registered(start_node_after_load):
            bpy.app.timers.register(start_node_after_load, first_interval=0.0)

    @persistent
    def auto_start(scene):
        bpy.app.handlers.depsgraph_update_post.remove(auto_start)
        schedule_node_start()

    @persistent
    def on_blend_load(scene):
        if auto_start in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(auto_start)
        schedule_node_start()

    def register():
        from blenderneuron.blender import somadisplay
        somadisplay.register()
        sys.setrecursionlimit(1500)

        register_module_classes(blenderneuron.blender.operators.rootgroup)
        register_module_classes(blenderneuron.blender.panels.rootgroup)
        register_module_classes(blenderneuron.blender.properties.rootgroup)

        blenderneuron.blender.properties.rootgroup.register() # already-iterative

        register_module_classes(blenderneuron.blender.operators.connection)
        register_module_classes(blenderneuron.blender.panels.connection)
        register_module_classes(blenderneuron.blender.properties.connection)

        blenderneuron.blender.properties.connection.register() # already-iterative

        # This ensures the server starts on Blender load (self-removing)
        bpy.app.handlers.depsgraph_update_post.append(auto_start)

        # Reload the addon on file open
        bpy.app.handlers.load_post.append(on_blend_load)
        bpy.app.handlers.save_pre.append(save_dataset_state)

    def unregister():
        from blenderneuron.blender import somadisplay
        somadisplay.unregister()
        if save_dataset_state in bpy.app.handlers.save_pre:
            bpy.app.handlers.save_pre.remove(save_dataset_state)
        if bpy.app.timers.is_registered(start_node_after_load):
            bpy.app.timers.unregister(start_node_after_load)
        bpy.ops.blenderneuron.node_stop()

        blenderneuron.blender.properties.connection.unregister() # already-iterative
        blenderneuron.blender.properties.rootgroup.unregister() # already-iterative

        register_module_classes(blenderneuron.blender.properties.connection, unreg=True)
        register_module_classes(blenderneuron.blender.panels.connection, unreg=True)
        register_module_classes(blenderneuron.blender.operators.connection, unreg=True)

        register_module_classes(blenderneuron.blender.properties.rootgroup, unreg=True)
        register_module_classes(blenderneuron.blender.panels.rootgroup, unreg=True)
        register_module_classes(blenderneuron.blender.operators.rootgroup, unreg=True)



# Only for testing from Blender Text Editor
if __name__ == "__main__" and inside_blender:
    register()
