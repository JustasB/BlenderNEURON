"""Exercise pairing controls in Blender's actual Python environment."""
import os
import tempfile
import unittest
from unittest.mock import patch

from blenderneuron.commnode import CommNode
from tests import Blender, NEURON, BlenderTestCase
from textwrap import dedent


class TestConnectionUI(BlenderTestCase):
    def test_pairing_controls(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, BLENDERNEURON_CONFIG_DIR=directory), \
                Blender(), CommNode('Control-Blender') as control:
            self.assertTrue(control.client.run_command(
                "bpy.ops.blenderneuron.connection_settings(action='COPY');"
                "import json; info = json.loads(bpy.context.window_manager.clipboard);"
                "return_value = info['version'] == 1 and len(info['secret']) == 64"))
            self.assertEqual('manual', control.client.run_command(
                "bpy.ops.blenderneuron.connection_settings(action='MANUAL');"
                "return_value = bpy.types.Object.BlenderNEURON_node.connection_settings['mode']"))
            self.assertEqual(['manual', '12346', True], control.client.run_command(
                "props = bpy.context.scene.BlenderNEURON_properties;"
                "props.client_port = '12345'; props.server_port = '12346';"
                "bpy.ops.blenderneuron.connection_settings(action='PASTE');"
                "return_value = [props.connection_mode.lower(), props.server_port, props.client_port == str(__import__('urllib.parse', fromlist=['urlparse']).urlparse(info['address']).port)]"))
            self.assertEqual('local', control.client.run_command(
                "bpy.ops.blenderneuron.connection_settings(action='LOCAL');"
                "return_value = bpy.types.Object.BlenderNEURON_node.connection_settings['mode']"))
            self.assertTrue(control.client.run_command(
                "node = bpy.types.Object.BlenderNEURON_node; old_secret = node.secret;"
                "bpy.ops.blenderneuron.connection_settings(action='FORGET');"
                "return_value = node.secret != old_secret and node.client is None"))


    def test_connect_and_panel_disclosure(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, BLENDERNEURON_CONFIG_DIR=directory), \
                NEURON(), Blender(), CommNode('Control-Blender') as control:
            self.assertTrue(control.client.run_command(dedent("""
                from types import SimpleNamespace
                from blenderneuron.blender.panels.connection import NodesPanel
                from blenderneuron import connection
                node = bpy.types.Object.BlenderNEURON_node
                props = bpy.context.scene.BlenderNEURON_properties
                props.connection_mode = 'MANUAL'
                neuron_address = connection.load('BlenderNEURON-NEURON.address', '')
                node.configure_connection(mode='manual', peer_address=neuron_address)
                bpy.ops.blenderneuron.connect_dialog()
                assert node.client is not None
                assert props.connection_message == 'Connected to NEURON.'
                groups = list(node.groups.keys())
                # A listener restart must preserve the runtime node and groups.
                props.server_port = str(node.server_port)
                bpy.ops.blenderneuron.connection_settings(action='RESTART')
                assert bpy.types.Object.BlenderNEURON_node is node
                assert list(node.groups.keys()) == groups
                assert node.client is not None
                class Layout:
                    def __init__(self):
                        self.labels, self.fields, self.buttons = [], [], []
                    def box(self): return self
                    def row(self, **kw): return self
                    def label(self, text='', **kw): self.labels.append(text)
                    def prop(self, data, name, **kw): self.fields.append(name)
                    def operator(self, name, text='', **kw):
                        self.buttons.append(text)
                        return SimpleNamespace()
                    def separator(self): pass
                def draw():
                    layout = Layout()
                    panel = SimpleNamespace(layout=layout, node=node, set_node=lambda: None)
                    NodesPanel.draw(panel, bpy.context)
                    return layout
                props.connection_advanced_open = False
                layout = draw()
                assert 'Reconnect' in layout.buttons
                assert 'Add Neon Effect' in layout.buttons
                assert 'server_port' not in layout.fields
                assert 'client_port' not in layout.fields
                assert 'Change connection...' in layout.buttons
                assert 'connection_mode' not in layout.fields
                from blenderneuron.blender.operators.connection import draw_connection_setup, NEURON_PAIRING_COMMAND
                dialog = Layout()
                draw_connection_setup(dialog, bpy.context, node)
                assert 'Copy Python command' in dialog.buttons
                assert 'Paste from clipboard' in dialog.buttons
                assert 'client_port' in dialog.fields
                assert 'pairing_secret' in dialog.fields
                assert props.bl_rna.properties['pairing_secret'].subtype == 'PASSWORD'
                original_secret = props.pairing_secret
                assert 'Saved secret: ' + original_secret[:4] + ' ****** ' + original_secret[-2:] in dialog.labels
                assert all(original_secret not in label for label in dialog.labels)
                props.pairing_secret = 'invalid'
                assert props.pairing_secret_invalid
                assert props.pairing_secret == original_secret
                props.pairing_secret = original_secret
                assert not props.pairing_secret_invalid
                assert node.secret == original_secret
                assert 'pairing_secret' not in props.keys()
                assert connection.load('Blender-manual.json', {})['secret'] == original_secret
                bpy.ops.blenderneuron.connection_settings(action='CONNECT')
                assert node.client is not None
                assert any('Python session running your NEURON model' in line for line in dialog.labels)
                assert any('{ }' in line for line in dialog.labels)
                bpy.ops.blenderneuron.connection_settings(action='COPY_COMMAND')
                assert bpy.context.window_manager.clipboard == NEURON_PAIRING_COMMAND
                assert 'print(BlenderNEURON.pairing_information())' in NEURON_PAIRING_COMMAND
                props.connection_advanced_open = True
                dialog = Layout()
                draw_connection_setup(dialog, bpy.context, node)
                assert 'server_port' in dialog.fields
                assert 'fixed_listen_port' in dialog.fields
                assert any(node.server_address in label and '(fixed port)' in label for label in dialog.labels)
                props.fixed_listen_port = False
                assert props.server_port == ''
                auto_dialog = Layout()
                draw_connection_setup(auto_dialog, bpy.context, node)
                assert 'server_port' not in auto_dialog.fields
                assert any('Automatic: Blender chooses' in label for label in auto_dialog.labels)
                from unittest.mock import patch
                with patch.object(node, 'stop_server') as stop, patch.object(node, 'setup_server') as setup, patch.object(node, 'test_connection', return_value=True):
                    bpy.ops.blenderneuron.connection_settings(action='CONNECT')
                    stop.assert_called_once()
                    setup.assert_called_once_with(service_queue=False)
                props.fixed_listen_port = True
                assert props.server_port == str(node.server_port)
                assert 'Forget saved connection' in dialog.buttons
                assert 'server_port' not in draw().fields
                props.client_port = '1'
                bpy.ops.blenderneuron.connection_settings(action='CONNECT')
                assert node.client is None
                assert 'NEURON did not respond' in props.connection_message
                return_value = True
            """)))


if __name__ == '__main__':
    unittest.main()
