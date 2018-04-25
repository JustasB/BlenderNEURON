import sys, threading;
sys.path.append('E:\Code\BlenderNEURON\ForBlender');
from neuroserver import NeuroServer

import bpy, threading
from bpy.app.handlers import persistent
import cProfile

# import sys
# sys.path.append('C:\\Users\\Justas\\Miniconda3\\envs\\pb35\\lib\\site-packages')
# import line_profiler
# import os
# os.chdir('E:\Code\BlenderNEURON\ForBlender')
# bpy.types.Object.profiler = line_profiler.LineProfiler(bpy.types.Object.neuron_server.create_path)
# bpy.types.Object.profiler.print_stats()

bl_info = {
    "name": "NEURON Blender Interface",
    "category": "Import-Export",
}
class NEURONClearModelOperator(bpy.types.Operator):
    """Removes all model meshes from the current scene"""
    bl_idname = "wm.neuron_clear_model_operator"
    bl_label = "Clear Model"

    def execute(self, context):
        bpy.types.Object.neuron_server.clear()
        return {'FINISHED'}

class NEURONLinkObjectsOperator(bpy.types.Operator):
    """Links all unlinked model objects to the current scene"""
    bl_idname = "wm.neuron_link_objects_operator"
    bl_label = "Refresh Scene"

    def execute(self, context):
        bpy.types.Object.neuron_server.link_objects()
        return {'FINISHED'}

class NEURONServerStopOperator(bpy.types.Operator):
    """Stops the NEURON server"""
    bl_idname = "wm.neuron_server_stop_operator"
    bl_label = "Stop Server"

    def execute(self, context):
        bpy.types.Object.neuron_server.stop()
        bpy.types.Object.neuron_server = None
        return {'FINISHED'}

class NEURONServerStartOperator(bpy.types.Operator):
    """Starts the NEURON server"""
    bl_idname = "wm.neuron_server_operator"
    bl_label = "Start Server"

    _timer = None

    def create_server(self):

        self.neuron_server = NeuroServer()
        bpy.types.Object.neuron_server = self.neuron_server

        # This creates a background thread that listens for external requests
        self.externalEventThread = threading.Thread(target=self.neuron_server.listenForExternal)
        self.externalEventThread.daemon = True
        self.externalEventThread.start()



    def work_on_queue_tasks(self):
        q = self.neuron_server.queue

        while not q.empty():
            task = q.get()
            task()
            q.task_done()

        print("Quitting worker thread...")

    def service_queue(self):
        print("Checking queue...")

        q = self.neuron_server.queue

        if not q.empty():
            print("TASKS FOUND")

            self.queue_servicer = threading.Thread(target=self.work_on_queue_tasks)
            self.queue_servicer.daemon = True

            print("Starting service thread...")
            self.queue_servicer.start()

            print("Waiting for tasks to finish...")
            q.join()
            print("Task queue DONE")

    def modal(self, context, event):

        if event.type == 'TIMER':

            self.service_queue()

        if bpy.types.Object.neuron_server is None:
            self.cancel(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def execute(self, context):

        # Start the server that will listen for external events
        self.create_server()

        wm = context.window_manager
        self._timer = wm.event_timer_add(5.0, context.window)  # This will periodically call the modal() method above
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)

class NEURONBlenderPanel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"
    bl_label = "NEURON Blender"
    bl_category = "NEURON"

    def draw(self, context):
        server = bpy.types.Object.neuron_server

        layout = self.layout
        col = layout.column(align=True)

        col.label(text="Model:")
        col.operator("wm.neuron_link_objects_operator", icon="LINKED")
        col.operator("wm.neuron_clear_model_operator", icon="PANEL_CLOSE")

        col.label(text=" ")

        if server is not None:
            col.label(text="Server: Listening")
            col.label(text="IP: " + bpy.types.Object.neuron_server.IP)
            col.label(text="Port: " + str(bpy.types.Object.neuron_server.Port))
            col.operator("wm.neuron_server_stop_operator", icon="CANCEL")
        else:
            col.label(text="Server: Stopped")
            col.operator("wm.neuron_server_operator", icon="PLAY")

@persistent
def auto_start(scene):
    # Remove auto-execute command after starting
    bpy.app.handlers.scene_update_post.remove(auto_start)

    bpy.ops.wm.neuron_server_operator()


def register():
    bpy.utils.register_class(NEURONServerStartOperator)
    bpy.utils.register_class(NEURONBlenderPanel)
    bpy.utils.register_class(NEURONLinkObjectsOperator)
    bpy.utils.register_class(NEURONServerStopOperator)
    bpy.utils.register_class(NEURONClearModelOperator)

    # This ensures the server starts on Blender load
    bpy.app.handlers.scene_update_post.append(auto_start)


def unregister():
    bpy.utils.unregister_class(NEURONServerStartOperator)
    bpy.utils.unregister_class(NEURONBlenderPanel)
    bpy.utils.unregister_class(NEURONLinkObjectsOperator)
    bpy.utils.unregister_class(NEURONServerStopOperator)
    bpy.utils.unregister_class(NEURONClearModelOperator)


# Only for testing from Blender Text Editor
if __name__ == "__main__":
    register()

