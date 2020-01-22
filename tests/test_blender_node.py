# From repo root, run all tests with 'python tests/test_blender_node.py'
# Run single test with: 'python tests/test_blender_node.py TestBlenderNode.test_server_established'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, NEURON, Blender, BlenderTestCase

class TestBlenderNode(BlenderTestCase):
    def test_server_established(self):
        # Start Blender with a running node
        with Blender(), CommNode("Control-Blender") as bcn:
            self.assertEqual(bcn.client.ping(), 1)

            bcn.client.end_code_coverage()

    def test_can_connect_to_neuron(self):
        # Start Blender with a running node
        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # See if Blender is able to connect to the NEURON process node
            result = bcn.client.run_command("return_value = str(bpy.types.Object.BlenderNEURON_node.client)")
            self.assertIn("Proxy", result)



            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_add_remove_group_and_cells(self):
        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:
                # Create a few named root sections in NEURON
                ncn.client.run_command('s1 = h.Section(name="soma1");'
                                       's2 = h.Section(name="soma2");')

                # Check that a default group was added
                self.assertEqual([1, 0], bcn.client.run_command(
                    "groups = bpy.data.scenes['Scene'].BlenderNEURON.groups;"
                    "count = len(groups);"
                    "index = bpy.data.scenes['Scene'].BlenderNEURON.groups_index;"
                    "return_value = [count, index];"
                ))

                # Refresh the list after adding the cells - this should not break the later tests
                # Check that there are 2 cells within the group
                self.assertEqual(2, bcn.client.run_command(
                    "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = len(group.root_entries);"
                ))

                # The last cell listed is the last cell created
                self.assertEqual("soma2", bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = group.root_entries[-1].name"
                ))

                # Check that both cells are selected
                self.assertEqual(True, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = all(cell.selected for cell in group.root_entries)"
                ))

                # Create a second cell group
                # Check that a group was added
                self.assertEqual(2, bcn.client.run_command(
                    "bpy.ops.blenderneuron.cell_group_add();"
                    "return_value = len(bpy.data.scenes['Scene'].BlenderNEURON.groups)"
                ))

                # Check that there are 2 cells within the 2nd group
                self.assertEqual(2, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[1];"
                    "return_value = len(group.root_entries)"
                ))

                # Check that NONE of the cells are selected in 2nd group
                self.assertEqual(True, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[1];"
                    "return_value = all(cell.selected == False for cell in group.root_entries)"
                ))

                # Select the last cell of the *2nd* group
                # Check that the last cell of the *1st* group becomes unselected
                self.assertEqual(False, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[1];"
                    "group.root_entries[-1].selected = True;"
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = group.root_entries[-1].selected"
                ))

                # Now select the first cell of the 2nd group (both cells should be selected)
                # Delete the second cell group (this should free the 2nd group's cells)
                # Check that a group was removed
                self.assertEqual(1, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[1];"
                    "group.root_entries[0].selected = True;"
                    "bpy.ops.blenderneuron.cell_group_remove();"
                    "return_value = len(bpy.data.scenes['Scene'].BlenderNEURON.groups)"
                ))

                # Add a new cell group (it should now contain the free'd cells)
                # Check that a group was added
                self.assertEqual(2, bcn.client.run_command(
                    "bpy.ops.blenderneuron.cell_group_add();"
                    "return_value = len(bpy.data.scenes['Scene'].BlenderNEURON.groups)"
                ))

                # Check that both cells are selected
                self.assertEqual(True, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[1];"
                    "return_value = all(cell.selected for cell in group.root_entries)"
                ))

                bcn.client.end_code_coverage()
                ncn.client.end_code_coverage()

    def test_group_select_all_none_invert(self):
        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

                # Create a few named root sections in NEURON
                ncn.client.run_command('s1 = h.Section(name="soma1");'
                                       's2 = h.Section(name="soma2");')

                # Refresh the default cell group in Blender
                bcn.client.run_command(
                    "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
                )

                # Check the group contains the two root sections
                self.assertEqual(2, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = len(group.root_entries);"
                ))

                # Unselect all, Check that no cells are selected
                self.assertEqual(True, bcn.client.run_command(
                    "bpy.ops.blenderneuron.unselect_all_cells();"
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = all(cell.selected == False for cell in group.root_entries)"
                ))

                # Select all, Check that all cells are selected
                self.assertEqual(True, bcn.client.run_command(
                    "bpy.ops.blenderneuron.select_all_cells();"
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "return_value = all(cell.selected for cell in group.root_entries)"
                ))

                # Unselect last cell, invert selection, and check that first cell is unselected
                self.assertEqual(False, bcn.client.run_command(
                    "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                    "group.root_entries[-1].selected = False;"
                    "bpy.ops.blenderneuron.invert_cell_selection();"
                    "return_value = group.root_entries[0].selected"
                ))

                bcn.client.end_code_coverage()
                ncn.client.end_code_coverage()

    def test_simulator_settings_exchange(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # set settings in Blender and send to NEURON
            bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "params.neuron_tstop = 1111;"
                "params.time_step = 0.002;"
                "params.abs_tolerance = 0.005;"
                "params.temperature = 44;"
                "params.integration_method = '1';"
                "bpy.ops.blenderneuron.sim_settings_to_neuron();"
                "bpy.ops.blenderneuron.sim_settings_from_neuron();"
            )

            self.assertEqual(1111, bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "return_value = params.neuron_tstop"
            ))

            self.assertAlmostEqual(0.005, bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "return_value = params.abs_tolerance"
            ), places=3)

            self.assertEqual(44, bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "return_value = params.temperature"
            ))

            self.assertEqual('1', bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "return_value = params.integration_method"
            ))

            # Test fixed step integration
            bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "params.time_step = 0.002;"
                "params.integration_method = '0';"
                "bpy.ops.blenderneuron.sim_settings_to_neuron();"
                "bpy.ops.blenderneuron.sim_settings_from_neuron();"
            )

            self.assertAlmostEqual(0.002, bcn.client.run_command(
                "params = bpy.data.scenes['Scene'].BlenderNEURON.simulator_settings;"
                "return_value = params.time_step"
            ), places=3)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_simulator_run(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Create a root section in NEURON
            ncn.client.run_command('s1 = h.Section(name="soma1");'
                                   's1.insert("pas");'
                                   's1.insert("hh");')

            # Run the sim
            bcn.client.run_command(
                "bpy.ops.blenderneuron.init_and_run_neuron()"
            )

            # Check that sim time is advanced
            self.assertAlmostEqual(5.0,
                                   ncn.client.run_command('return_value=h.t'),
                                   places=1)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

if __name__ == '__main__':
    unittest.main()
