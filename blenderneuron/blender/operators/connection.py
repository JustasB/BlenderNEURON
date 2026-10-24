
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
        self.modal_timer = wm.event_timer_add(self.modal_timer_period, window=context.window)
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
        bpy.types.Object.BlenderNEURON_node.test_connection()
        return {'FINISHED'}

class ExecNeuronCommandOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.exec_neuron_command"
    bl_label = "Execute a Python command in NEURON"
    bl_description = "Runs a command in NEURON. Printed result is visible in Blender's console window."

    def execute(self, context):
        command = context.scene.BlenderNEURON_properties.neuron_last_command
        bpy.types.Object.BlenderNEURON_node.client.run_command(command)

        return {'FINISHED'}


class ConnectionSettingsOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = 'blenderneuron.connection_settings'
    bl_label = 'Connection settings'
    action: bpy.props.StringProperty()

    def execute(self, context):
        from blenderneuron import connection
        node = self.node
        props = context.scene.BlenderNEURON_properties
        try:
            if self.action == 'COPY_COMMAND':
                context.window_manager.clipboard = NEURON_PAIRING_COMMAND
                self.report({'INFO'}, 'Python command copied. Run it in your NEURON Python session.')
            elif self.action in {'CONNECT', 'RESTART'}:
                if node is None:
                    bpy.ops.blenderneuron.node_start()
                    node = self.node
                settings = node.connection_settings
                manual = settings['mode'] == 'manual'
                if manual and props.pairing_secret_invalid:
                    raise ValueError('Enter a valid pairing secret or import NEURON connection information.')
                if manual and not settings.get('peer_address'):
                    raise ValueError('Paste NEURON connection information or enter its address and port.')
                changed = (node.server is None or
                    (manual and (settings.get('listen_host', '127.0.0.1') != node.server_ip or
                     str(settings.get('listen_port', '')) != getattr(node, 'server_requested_port', ''))) or
                    (not manual and (node.server_ip != '127.0.0.1' or getattr(node, 'server_requested_port', ''))))
                if self.action == 'RESTART' or changed:
                    # Keep model groups and the existing modal queue handler.
                    node.stop_server()
                    node.setup_server(service_queue=False)
                connected = node.test_connection()
                props.connection_message = ('Connected to NEURON.' if connected else
                    getattr(node, 'last_connection_error', 'NEURON is unavailable. Check the address and port.'))
                self.report({'INFO'} if connected else {'WARNING'}, props.connection_message)
            elif self.action == 'COPY':
                if node is None:
                    raise ValueError('Start the Blender connection before copying its information.')
                context.window_manager.clipboard = node.pairing_information()
                self.report({'INFO'}, 'Blender connection information copied. Share only with a trusted peer.')
            elif self.action == 'FORGET':
                if node is None:
                    raise ValueError('Start the Blender connection before forgetting its credentials.')
                node.forget_connection()
                props.connection_message = 'Connection forgotten. Pair again to reconnect.'
            elif self.action == 'PASTE':
                if node is None:
                    bpy.ops.blenderneuron.node_start()
                    node = self.node
                previous = connection.load('Blender-manual.json', {})
                node.configure_connection(mode='manual', pairing=context.window_manager.clipboard,
                    listen_host=previous.get('listen_host', '127.0.0.1'),
                    listen_port=previous.get('listen_port', ''))
                props.pairing_secret_invalid = False
                props.connection_message = 'Connection information loaded. Pairing secret saved privately.'
                self.report({'INFO'}, props.connection_message)
            elif self.action in {'LOCAL', 'MANUAL'}:
                props.connection_mode = 'LOCAL' if self.action == 'LOCAL' else 'MANUAL'
            else:
                raise ValueError('Unknown connection action')
        except (ValueError, KeyError, TypeError, OSError) as error:
            props.connection_message = str(error)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


NEURON_PAIRING_COMMAND = (
    "from blenderneuron.neuronstart import BlenderNEURON\n"
    "print(BlenderNEURON.pairing_information())"
)


def draw_connection_setup(layout, context, node):
    props = context.scene.BlenderNEURON_properties
    layout.label(text='Where is NEURON running?')
    layout.prop(props, 'connection_mode', expand=True)
    if props.connection_mode == 'MANUAL':
        steps = layout.box()
        steps.label(text='1. In the Python session running your NEURON model, run:')
        for line in NEURON_PAIRING_COMMAND.splitlines():
            steps.label(text=line)
        steps.operator('blenderneuron.connection_settings',
                       text='Copy Python command', icon='COPYDOWN').action = 'COPY_COMMAND'
        steps.separator()
        steps.label(text='2. Copy the full output, including the { } braces.')
        steps.label(text='3. Return here and paste it from the clipboard.')
        steps.operator('blenderneuron.connection_settings',
                       text='Paste from clipboard', icon='PASTEDOWN').action = 'PASTE'
        layout.label(text='Check the address used by Blender (or your SSH tunnel):')
        layout.prop(props, 'client_ip', text='NEURON address')
        layout.prop(props, 'client_port', text='NEURON port')
        layout.prop(props, 'pairing_secret', text='Pairing secret')
        secret = props.pairing_secret
        if secret:
            layout.label(text='Saved secret: ' + secret[:4] + ' ****** ' + secret[-2:])
        else:
            layout.label(text='No pairing secret saved. Import or enter it above.')
        layout.label(text='Import the information above, or enter all three fields manually.')
    else:
        layout.label(text='Find NEURON automatically on this computer.')
    if props.connection_message:
        import textwrap
        for line in textwrap.wrap(props.connection_message, width=72):
            layout.label(text=line)
    layout.prop(props, 'connection_advanced_open', text='Advanced',
                icon='TRIA_DOWN' if props.connection_advanced_open else 'TRIA_RIGHT', emboss=False)
    if not props.connection_advanced_open:
        return
    running = node is not None and node.server is not None
    advanced = layout.box()
    advanced.label(text='Blender receives connections at:')
    if running:
        automatic = not getattr(node, 'server_requested_port', '')
        advanced.label(text=node.server_address + (' (automatic port)' if automatic else ' (fixed port)'))
    else:
        advanced.label(text='Not currently listening.')
    if props.connection_mode == 'MANUAL':
        advanced.prop(props, 'server_ip', text='Listen address')
        advanced.prop(props, 'fixed_listen_port')
        if props.fixed_listen_port:
            advanced.prop(props, 'server_port', text='Fixed port')
        else:
            advanced.label(text='Automatic: Blender chooses an available port.')
        advanced.label(text='Listening changes are applied when you connect.')
    else:
        advanced.label(text='An available port is chosen automatically.')
    advanced.label(text='For Docker or SSH, NEURON may use a different address')
    advanced.label(text='to reach this listener. Configure that address in NEURON.')
    copy = advanced.row()
    copy.enabled = running
    copy.operator('blenderneuron.connection_settings',
                  text='Copy Blender connection information', icon='COPYDOWN').action = 'COPY'
    advanced.separator()
    forget = advanced.row()
    forget.enabled = running
    forget.operator('blenderneuron.connection_settings',
                    text='Forget saved connection', icon='X').action = 'FORGET'
    advanced.separator()
    advanced.label(text='Diagnostics')
    advanced.label(text='Blender: ' + (node.server_address if running else 'Stopped'))
    connected = running and node.client is not None
    advanced.label(text='NEURON: ' + (node.client_address if connected else 'Not connected'))
    if running:
        advanced.operator('blenderneuron.node_stop', text='Stop Blender connection', icon='CANCEL')
    if blender_launched_neuron_running():
        advanced.operator('blenderneuron.stop_neuron', text='Stop NEURON', icon='CANCEL')


class ConnectDialogOperator(bpy.types.Operator, BlenderNodeClass):
    bl_idname = 'blenderneuron.connect_dialog'
    bl_label = 'Connect to NEURON'
    bl_description = 'Choose where NEURON runs and set up a remembered connection'

    def invoke(self, context, event):
        context.scene.BlenderNEURON_properties.connection_message = ''
        try:
            return context.window_manager.invoke_props_dialog(self, width=560, confirm_text='Connect')
        except TypeError:  # Blender 4.0 uses its standard confirmation label.
            return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        draw_connection_setup(self.layout, context, self.node)

    def execute(self, context):
        result = bpy.ops.blenderneuron.connection_settings(action='CONNECT')
        return result
