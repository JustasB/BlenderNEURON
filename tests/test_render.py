# From repo root, run all tests with 'python tests/test_render.py'
# Run single test with: 'python tests/test_render.py TestRender.test_glare'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from textwrap import dedent
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, NEURON, BlenderTestCase


class TestRender(BlenderTestCase):
    def test_glare(self):
        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
                Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            bcn.client.run_command('bpy.ops.blenderneuron.add_neon_effect();')

            # Adding 2nd time should not fail either
            bcn.client.run_command('bpy.ops.blenderneuron.add_neon_effect();')

            result = bcn.client.run_command(dedent("""
                scene = bpy.context.scene
                is_blender_5 = bpy.app.version[0] >= 5
                nt = scene.compositing_node_group if is_blender_5 else scene.node_tree
                nodes = nt.nodes
                links = nt.links
                glare_nodes = [node for node in nodes if node.type == 'GLARE']
                comp = nodes.get('Composite')
                viewer = nodes.get('Viewer')
                view_compositor_modes = []

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            space = area.spaces.active
                            if hasattr(space, 'shading') and hasattr(space.shading, 'use_compositor'):
                                view_compositor_modes.append(space.shading.use_compositor)

                return_value = {
                    'is_blender_5': is_blender_5,
                    'has_tree': nt is not None,
                    'glare_count': len(glare_nodes),
                    'has_composite': comp is not None,
                    'has_viewer': viewer is not None,
                    'output_link_count': len([link for link in links if link.to_node == comp]),
                    'view_compositor_modes': view_compositor_modes,
                    'use_nodes': getattr(scene, 'use_nodes', None),
                    'use_bloom': getattr(getattr(scene, 'eevee', None), 'use_bloom', None),
                }
            """))

            self.assertTrue(result['has_tree'])
            self.assertEqual(1, result['glare_count'])
            self.assertTrue(result['has_composite'])
            self.assertEqual(1, result['output_link_count'])

            if result['is_blender_5']:
                self.assertIn('ALWAYS', result['view_compositor_modes'])
                self.assertFalse(result['has_viewer'])
            else:
                self.assertTrue(result['use_nodes'])
                self.assertTrue(result['has_viewer'])

                if result['use_bloom'] is not None:
                    self.assertTrue(result['use_bloom'])


if __name__ == '__main__':
    unittest.main()
