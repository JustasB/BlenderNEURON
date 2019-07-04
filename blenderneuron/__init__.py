try:
    import bpy
    inside_blender = True
except:
    inside_blender = False

if inside_blender:
    from bpy.app.handlers import persistent

    import blenderneuron
    from blenderneuron.commnode import CommNode

    from blenderneuron.addon.operators.connection import *
    from blenderneuron.addon.panels.connection import *
    from blenderneuron.addon.properties.connection import *

    from blenderneuron.addon.operators.cellgroups import *
    from blenderneuron.addon.panels.cellgroups import *
    from blenderneuron.addon.properties.cellgroups import *

    from blenderneuron.addon.utils import register_module_classes

    bl_info = {
        "name": "BlenderNEURON",
        "description": "A Blender GUI for NEURON simulator",
        "author": "Justas Birgiolas",
        "version": (2, 0),
        "blender": (2, 79, 0),
        "location": "View3D > Tools > BlenderNEURON side tab",
        "wiki_url": "BlenderNEURON.org",
        "tracker_url": "https://github.com/JustasB/BlenderNEURON/issues",
        "support": "COMMUNITY",
        "category": "Import-Export",
    }

    @persistent
    def auto_start(scene):
        # Remove auto-execute command after starting
        bpy.app.handlers.scene_update_post.remove(auto_start)

        bpy.ops.wm.blenderneuron_node_start()


    def register():
        try:
            bpy.utils.register_module(__name__)
        except:
            pass

        register_module_classes(blenderneuron.addon.operators.connection)
        register_module_classes(blenderneuron.addon.panels.connection)
        register_module_classes(blenderneuron.addon.properties.connection)

        blenderneuron.addon.properties.connection.register()

        register_module_classes(blenderneuron.addon.operators.cellgroups)
        register_module_classes(blenderneuron.addon.panels.cellgroups)
        register_module_classes(blenderneuron.addon.properties.cellgroups)

        blenderneuron.addon.properties.cellgroups.register()

        # This ensures the server starts on Blender load (self-removing)
        bpy.app.handlers.scene_update_post.append(auto_start)

    def unregister():
        bpy.ops.wm.blenderneuron_node_stop()

        try:
            bpy.utils.unregister_module(__name__)
        except:
            pass

        register_module_classes(blenderneuron.addon.operators.connection, unreg=True)
        register_module_classes(blenderneuron.addon.panels.connection, unreg=True)
        register_module_classes(blenderneuron.addon.properties.connection, unreg=True)

        blenderneuron.addon.connection.properties.unregister()

        register_module_classes(blenderneuron.addon.operators.cellgroups, unreg=True)
        register_module_classes(blenderneuron.addon.panels.cellgroups, unreg=True)
        register_module_classes(blenderneuron.addon.properties.cellgroups, unreg=True)

        blenderneuron.addon.properties.cellgroups.unregister()



# Only for testing from Blender Text Editor
if __name__ == "__main__" and inside_blender:
    register()

