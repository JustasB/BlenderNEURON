import bpy

from blenderneuron.blender.panels import AbstractBlenderNEURONPanel


class NodesPanel(AbstractBlenderNEURONPanel, bpy.types.Panel):
    bl_idname = 'BLENDERNEURON_PT_NodesPanel'
    bl_label = 'Node Status'

    def draw(self, context):
        self.set_node()
        node = self.node
        props = context.scene.BlenderNEURON_properties
        layout = self.layout
        running = node is not None and node.server is not None
        connected = running and node.client is not None
        status = layout.box()
        status.label(text='Connected to NEURON' if connected else 'Disconnected',
                     icon='CHECKMARK' if connected else 'INFO')
        if connected:
            status.label(text=node.client_address)
        if props.connection_message:
            # Several short lines stay readable in a narrow sidebar.
            import textwrap
            for line in textwrap.wrap(props.connection_message, width=42):
                status.label(text=line)

        row = layout.row(align=True)
        if connected:
            row.operator('blenderneuron.connection_settings',
                         text='Reconnect', icon='FILE_REFRESH').action = 'CONNECT'
        row.operator('blenderneuron.connect_dialog',
                     text='Change connection...' if connected else 'Connect to NEURON...',
                     icon='PREFERENCES' if connected else 'PLAY')

        layout.operator('blenderneuron.add_neon_effect', text='Add Neon Effect', icon='PARTICLES')
