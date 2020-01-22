# From repo root, run all tests with 'python tests/test_cell_import_export.py'
# Run single test with: 'python tests/test_layer_confinement.py TestCellImportExport.test_object_levels'

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
                "bpy.ops.blenderneuron.import_groups();"
                "bpy.data.objects['TestCell[0].soma'].location = (0,0,0);"
                "bpy.ops.mesh.primitive_plane_add(location=(0,0,0));"
                "bpy.ops.mesh.primitive_plane_add(location=(0,0,60));"
                "bpy.data.objects['Plane.001'].scale = bpy.data.objects['Plane'].scale = [200]*3;"
            )

            # Setup and run default confiner
            x, y, z = bcn.client.run_command(
                "confiner = bpy.context.scene.BlenderNEURON.groups[0].layer_confiner_settings;"
                "confiner.start_mesh = bpy.data.objects['Plane'];"
                "confiner.end_mesh   = bpy.data.objects['Plane.001'];"
                "bpy.ops.blenderneuron.confine_between_layers();"
                "return_value = list(bpy.data.objects['TestCell[0].dendrites[13]'].rotation_euler);"
            )

            self.assertAlmostEqual(x * degs, -5, 2)
            self.assertAlmostEqual(y * degs, -0.04, 2)
            self.assertAlmostEqual(z * degs, -0.88, 2)

            # Run confiner with split sections
            x, y, z = bcn.client.run_command(
                "confiner = bpy.context.scene.BlenderNEURON.groups[0].layer_confiner_settings;"
                "confiner.max_section_length = 25;"
                "bpy.ops.blenderneuron.confine_between_layers();"
                "return_value = list(bpy.data.objects['TestCell[0].dendrites[13]'].rotation_euler);"
            )

            self.assertAlmostEqual(x * degs, -5, 2)
            self.assertAlmostEqual(y * degs, -0.04, 2)
            self.assertAlmostEqual(z * degs, -0.88, 2)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()


if __name__ == '__main__':
    unittest.main()
