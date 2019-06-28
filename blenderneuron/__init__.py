try:
    import os, sys
    from blenderneuron.commnode import CommNode
    import bpy, threading
    from bpy.app.handlers import persistent

    inside_blender = True
except:
    inside_blender = False

if inside_blender:
    bl_info = {
        "name": "NEURON Blender Interface",
        "category": "Import-Export",
    }

    class NEURONServerStopOperator(bpy.types.Operator):
        bl_idname = "wm.blenderneuron_node_stop"
        bl_label = "Stop BlenderNEURON Blender node"

        def execute(self, context):
            if hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None:
                    bpy.types.Object.BlenderNEURON_node.stop_server()
                    bpy.types.Object.BlenderNEURON_node = None

            return {'FINISHED'}


    class NEURONServerStartOperator(bpy.types.Operator):
        bl_idname = "wm.blenderneuron_node_start"
        bl_label = "Start BlenderNEURON Blender node"

        def execute(self, context):
            # Create the communications node for Blender end
            node = CommNode("Blender")

            # Save it so it's accessible globally from Blender
            bpy.types.Object.BlenderNEURON_node = node

            return {'FINISHED'}


    @persistent
    def auto_start(scene):
        # Remove auto-execute command after starting
        bpy.app.handlers.scene_update_post.remove(auto_start)

        bpy.ops.wm.blenderneuron_node_start()


    def register():
        bpy.utils.register_class(NEURONServerStartOperator)
        bpy.utils.register_class(NEURONServerStopOperator)

        # This ensures the server starts on Blender load (self-removing)
        bpy.app.handlers.scene_update_post.append(auto_start)

    def unregister():
        bpy.ops.wm.blenderneuron_node_stop()

        bpy.utils.unregister_class(NEURONServerStartOperator)
        bpy.utils.unregister_class(NEURONServerStopOperator)

# Only for testing from Blender Text Editor
if __name__ == "__main__" and inside_blender:
    register()

