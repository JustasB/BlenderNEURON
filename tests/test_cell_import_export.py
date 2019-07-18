# From repo root, run all tests with 'python tests/test_CommNode.py'
# Run single test with: 'python tests/test_CommNode.py TestClassNameHere.test_method'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, BlenderTestCase

class TestCellImportExport(BlenderTestCase):

    def test_import_export_cell(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            # Create a control node
            with CommNode("Control") as cn:
                # Tell Blender to launch own NEURON process
                try:
                    cn.client.run_command("bpy.ops.wm.blenderneuron_launch_neuron()")
                    sleep(1)

                    # Load TestCell.hoc - create a group
                    cn.client.run_command(
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('h.load_file(\"tests/TestCell.hoc\")');"
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('tc = h.TestCell()');"
                        "bpy.ops.custom.cell_group_add();"
                    )

                    # Check that the cell was loaded
                    self.assertEqual("TestCell[0].soma", cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                        "return_value = group.root_entries[0].name"
                    ))

                    # Import the cell and check if created in correct location
                    x,y,z = cn.client.run_command(
                        "bpy.ops.custom.import_selected_groups();"
                        "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
                    )

                    self.assertAlmostEqual(x, 150, 1)
                    self.assertAlmostEqual(y, -176, 1)
                    self.assertAlmostEqual(z, 0, 1)

                    # And cell bounding box dimensions are correct
                    dim_x,dim_y,dim_z = cn.client.run_command(
                        "return_value = list(bpy.data.objects['TestCell[0].soma'].dimensions)"
                    )

                    # Import the cell and check if created in correct location
                    self.assertAlmostEqual(dim_x, 165.45, 1)
                    self.assertAlmostEqual(dim_y, 165.80, 1)
                    self.assertAlmostEqual(dim_z, 1, 1)

                    # Shift the cell up by 100 um, and export to NRN
                    cn.client.run_command(
                        "bpy.data.objects['TestCell[0].soma'].location = [150, -176, 100];"
                        "bpy.ops.custom.export_selected_groups();"
                    )

                    # Test if coordinates in NRN changed by same amount
                    z_soma, z_dend1, z_dend2 = cn.client.run_command(
                        "nrn_run = bpy.types.Object.BlenderNEURON_node.client.run_command;"
                        "return_value = nrn_run('return_value = [h.z3d(0,sec=tc.soma), h.z3d(0,sec=tc.dendrites[-1]), h.z3d(0,sec=tc.dendrites[15])]');"
                    )

                    self.assertEqual(z_soma, 100.0)
                    self.assertEqual(z_soma, z_dend1)
                    self.assertEqual(z_dend1, z_dend2)

                    # Re-import the cell and check if change persists
                    x,y,z = cn.client.run_command(
                        "bpy.ops.custom.import_selected_groups();"
                        "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
                    )

                    self.assertAlmostEqual(z, 100, 1)

                    # And that duplicate objects were not created
                    count = cn.client.run_command(
                        "cellObjs = [ob for ob in bpy.data.objects if 'TestCell[0].soma' in ob.name];"
                        "return_value = len(cellObjs)"
                    )

                    self.assertEqual(count, 1)


                finally:
                    # Stop NEURON
                    cn.client.run_command("bpy.ops.wm.blenderneuron_stop_neuron()")

    def test_import_remove_import_again(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            # Create a control node
            with CommNode("Control") as cn:
                # Tell Blender to launch own NEURON process
                try:
                    cn.client.run_command("bpy.ops.wm.blenderneuron_launch_neuron()")
                    sleep(1)

                    # Load TestCell.hoc - create a group
                    cn.client.run_command(
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('h.load_file(\"tests/TestCell.hoc\")');"
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('tc = h.TestCell()');"
                        "bpy.ops.custom.cell_group_add();"
                    )

                    # Import the cell and check if created in correct location
                    x,y,z = cn.client.run_command(
                        "bpy.ops.custom.import_selected_groups();"
                        "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
                    )

                    self.assertAlmostEqual(x, 150, 1)
                    self.assertAlmostEqual(y, -176, 1)
                    self.assertAlmostEqual(z, 0, 1)

                    # Shift the cell up by 100 um
                    cn.client.run_command(
                        "bpy.data.objects['TestCell[0].soma'].location = [150, -176, 100];"
                    )

                    # Re-Import the cell and check if overwrote the shift above
                    x,y,z = cn.client.run_command(
                        "bpy.ops.custom.import_selected_groups();"
                        "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
                    )

                    self.assertAlmostEqual(z, 0, 1)

                    # Shift the cell up again by 100 um
                    cn.client.run_command(
                        "bpy.data.objects['TestCell[0].soma'].location = [150, -176, 100];"
                    )

                    # Remove the group, there should be no cell objects
                    count = cn.client.run_command(
                        "bpy.ops.custom.cell_group_remove();"
                        "return_value = len([ob for ob in bpy.data.objects if 'TestCell[0].soma' in ob.name])"
                    )

                    # Add a new group, import it
                    x,y,z = cn.client.run_command(
                        "bpy.ops.custom.cell_group_add();"
                        "bpy.ops.custom.import_selected_groups();"
                        "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
                    )

                    # The z position should be the original position (not shifted)
                    self.assertAlmostEqual(z, 0, 1)

                finally:
                    # Stop NEURON
                    cn.client.run_command("bpy.ops.wm.blenderneuron_stop_neuron()")


if __name__ == '__main__':
    unittest.main()
