# From repo root, run all tests with 'python tests/test_CommNode.py'
# Run single test with: 'python tests/test_CommNode.py TestClassNameHere.test_method'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, BlenderTestCase

class TestCommNode(BlenderTestCase):
    def test_server_established(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            with CommNode("Control") as control_node:
                self.assertEqual(control_node.client.ping(), 1)

    def test_can_launch_and_stop_neuron(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            with CommNode("Control") as control_node:
                # Tell Blender to launch own NEURON process
                control_node.client.run_command("bpy.ops.wm.blenderneuron_launch_neuron()")
                sleep(1)

                # See if Blender is able to connect to the NEURON process node
                result = control_node.client.run_command("return_value = str(bpy.types.Object.BlenderNEURON_node.client)")
                self.assertIn("Proxy", result)

                # Stop NEURON
                control_node.client.run_command("bpy.ops.wm.blenderneuron_stop_neuron()")

                # Check if the client was cleaned up
                result = control_node.client.run_command("return_value = str(bpy.types.Object.BlenderNEURON_node.client)")
                self.assertIn("None", result)

    def test_add_remove_group_and_cells(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            # Create a control node
            with CommNode("Control") as cn:
                # Tell Blender to launch own NEURON process
                try:
                    cn.client.run_command("bpy.ops.wm.blenderneuron_launch_neuron()")
                    sleep(1)

                    # Create a few named root sections in NEURON, Create a new cell group
                    cn.client.run_command(
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('s1 = h.Section(name=\"soma1\")');"
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('s2 = h.Section(name=\"soma2\")');"
                        "bpy.ops.custom.cell_group_add();"
                    )

                    # Check that a group was added
                    self.assertEqual([1, 0], cn.client.run_command(
                        "groups = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups;"
                        "count = len(groups);"
                        "index = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups_index;"
                        "return_value = [count, index];"
                    ))

                    # Refresh the list after adding the cells - this should not break the later tests
                    # Check that there are 2 cells within the group
                    self.assertEqual(2, cn.client.run_command(
                        "bpy.ops.custom.get_cell_list_from_neuron();"
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "return_value = len(group.group_cells);"
                    ))

                    # The last cell listed is the last cell created
                    self.assertEqual("soma2", cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "return_value = group.group_cells[-1].name"
                    ))

                    # Check that both cells are selected
                    self.assertEqual(True, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "return_value = all(cell.selected for cell in group.group_cells)"
                    ))

                    # Create a second cell group
                    # Check that a group was added
                    self.assertEqual(2, cn.client.run_command(
                        "bpy.ops.custom.cell_group_add();"
                        "return_value = len(bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups)"
                    ))

                    # Check that there are 2 cells within the 2nd group
                    self.assertEqual(2, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[1];"
                        "return_value = len(group.group_cells)"
                    ))

                    # Check that NONE of the cells are selected in 2nd group
                    self.assertEqual(True, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[1];"
                        "return_value = all(cell.selected == False for cell in group.group_cells)"
                    ))

                    # Select the last cell of the *2nd* group
                    # Check that the last cell of the *1st* group becomes unselected
                    self.assertEqual(False, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[1];"
                        "group.group_cells[-1].selected = True;"
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "return_value = group.group_cells[-1].selected"
                    ))

                    # Now select the first cell of the 2nd group (both cells should be selected)
                    # Delete the second cell group (this should free the 2nd group's cells)
                    # Check that a group was removed
                    self.assertEqual(1, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[1];"
                        "group.group_cells[0].selected = True;"
                        "bpy.ops.custom.cell_group_remove();"
                        "return_value = len(bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups)"
                    ))

                    # Add a new cell group (it should now contain the free'd cells)
                    # Check that a group was added
                    self.assertEqual(2, cn.client.run_command(
                        "bpy.ops.custom.cell_group_add();"
                        "return_value = len(bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups)"
                    ))

                    # Check that both cells are selected
                    self.assertEqual(True, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[1];"
                        "return_value = all(cell.selected for cell in group.group_cells)"
                    ))

                finally:
                    # Stop NEURON
                    cn.client.run_command("bpy.ops.wm.blenderneuron_stop_neuron()")

    def test_group_select_all_none_invert(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            # Create a control node
            with CommNode("Control") as cn:
                # Tell Blender to launch own NEURON process
                try:
                    cn.client.run_command("bpy.ops.wm.blenderneuron_launch_neuron()")
                    sleep(1)

                    # Create a few named root sections in NEURON
                    cn.client.run_command(
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('s1 = h.Section(name=\"soma1\")');"
                        "bpy.types.Object.BlenderNEURON_node.client.run_command('s2 = h.Section(name=\"soma2\")');"
                    )

                    # Create a new cell group
                    cn.client.run_command("bpy.ops.custom.cell_group_add()")

                    # Unselect all, Check that no cells are selected
                    self.assertEqual(True, cn.client.run_command(
                        "bpy.ops.custom.select_none_neuron_cells();"
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "return_value = all(cell.selected == False for cell in group.group_cells)"
                    ))

                    # Select all, Check that all cells are selected
                    self.assertEqual(True, cn.client.run_command(
                        "bpy.ops.custom.select_all_neuron_cells();"
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "return_value = all(cell.selected for cell in group.group_cells)"
                    ))

                    # Unselect last cell, invert selection, and check that first cell is unselected
                    self.assertEqual(False, cn.client.run_command(
                        "group = bpy.data.scenes['Scene'].BlenderNEURON_neuron_cellgroups[0];"
                        "group.group_cells[-1].selected = False;"
                        "bpy.ops.custom.select_invert_neuron_cells();"
                        "return_value = group.group_cells[0].selected"
                    ))

                finally:
                    # Stop NEURON
                    cn.client.run_command("bpy.ops.wm.blenderneuron_stop_neuron()")

if __name__ == '__main__':
    unittest.main()
