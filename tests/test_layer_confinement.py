# From repo root, run all tests with 'python tests/test_layer_confinement.py'
# Run single test with: 'python tests/test_layer_confinement.py TestLayerConfinement.test_confine_cell'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, NEURON, Blender, BlenderTestCase
from math import pi
degs = 180/pi

class TestLayerConfinement(BlenderTestCase):

    def test_confine_cell(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();')

            # Load cell, add two layer planes
            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
                "bpy.context.scene.BlenderNEURON.groups[0].interaction_granularity = 'Section';"
                "bpy.ops.blenderneuron.import_groups();"
                "bpy.data.objects['TestCell[0].soma'].location = (0,0,0);"
                "bpy.ops.mesh.primitive_plane_add(location=(0,0,0));"
                "bpy.ops.mesh.primitive_plane_add(location=(0,0,60));"
                "bpy.data.objects['Plane.001'].scale = bpy.data.objects['Plane'].scale = [200]*3;"
            )

            # Setup and run default confiner
            x, y, z = bcn.client.run_command(
                "group = bpy.context.scene.BlenderNEURON.groups[0].node_group;"
                "group.set_confiner_layers('Plane', 'Plane.001', 15, 0, 0.5);"
                "bpy.ops.blenderneuron.confine_between_layers();"
                "return_value = list(bpy.data.objects['TestCell[0].dendrites[13]'].rotation_euler);"
            )

            self.assertAlmostEqual(x * degs, -5, 2)
            self.assertAlmostEqual(y * degs, -0.04, 2)
            self.assertAlmostEqual(z * degs, -0.88, 2)

            # Update group with confiner results
            # Redisplay the updated group
            x, y, z = bcn.client.run_command(
                "bpy.ops.blenderneuron.update_groups_with_view_data();"
                "bpy.ops.blenderneuron.display_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].dendrites[13]'].location);"
            )

            # Results should be different as these are not global coordinates
            self.assertAlmostEqual(x, -112.59, 2)
            self.assertAlmostEqual(y, 53.03, 2)
            self.assertAlmostEqual(z, 27.06, 2)

            # Run confiner with split sections
            x, y, z = bcn.client.run_command(
                "bpy.ops.blenderneuron.import_groups();"
                "confiner = bpy.context.scene.BlenderNEURON.groups[0].layer_confiner_settings;"
                "confiner.max_section_length = 15;"
                "confiner.max_bend_angle = 5;"
                "bpy.ops.blenderneuron.confine_between_layers();"
                "return_value = list(bpy.data.objects['TestCell[0].dendrites[13][0]'].rotation_euler);"
            )

            self.assertAlmostEqual(x * degs, -4.09, 1)
            self.assertAlmostEqual(y * degs, -0.07, 1)
            self.assertAlmostEqual(z * degs, -0.22, 1)

            # Update group with confiner results
            # Redisplay the updated group
            x, y, z = bcn.client.run_command(
                "bpy.ops.blenderneuron.update_groups_with_view_data();"
                "bpy.ops.blenderneuron.display_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].dendrites[13]'].location);"
            )

            self.assertAlmostEqual(x, 50.31, 1)
            self.assertAlmostEqual(y, -92.22, 1)
            self.assertAlmostEqual(z, 15.45, 1)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()


if __name__ == '__main__':
    unittest.main()
