# From repo root, run all tests with 'python tests/test_cell_import_export.py'
# Run single test with: 'python tests/test_cell_import_export.py TestCellImportExport.test_object_levels'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, NEURON, Blender, BlenderTestCase

class TestCellImportExport(BlenderTestCase):

    def test_import_export_cell(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();')

            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )

            # Check that the cell was loaded
            self.assertEqual("TestCell[0].soma", bcn.client.run_command(
                "group = bpy.data.scenes['Scene'].BlenderNEURON.groups['Group.000'];"
                "return_value = group.root_entries[0].name"
            ))

            # Import the cell and check if created in correct location
            x,y,z = bcn.client.run_command(
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
            )

            self.assertAlmostEqual(x, 150, 1)
            self.assertAlmostEqual(y, -176, 1)
            self.assertAlmostEqual(z, 0, 1)

            # And cell bounding box dimensions are correct
            dim_x,dim_y,dim_z = bcn.client.run_command(
                "return_value = list(bpy.data.objects['TestCell[0].soma'].dimensions)"
            )


            self.assertAlmostEqual(dim_x, 165.45, 1)
            self.assertAlmostEqual(dim_y, 165.80, 1)
            self.assertAlmostEqual(dim_z, 1, 0)

            # Shift the cell up by 100 um, and export to NRN
            bcn.client.run_command(
                "bpy.data.objects['TestCell[0].soma'].location = [150, -176, 100];"
                "bpy.ops.blenderneuron.update_groups_with_view_data();"
                "bpy.ops.blenderneuron.export_groups();"
            )

            # Test if coordinates in NRN changed by same amount
            z_soma, z_dend1, z_dend2 = ncn.client.run_command(
                'return_value = [h.z3d(0,sec=tc.soma), h.z3d(0,sec=tc.dendrites[-1]), h.z3d(0,sec=tc.dendrites[15])]'
            )

            self.assertEqual(z_soma, 100.0)
            self.assertEqual(z_soma, z_dend1)
            self.assertEqual(z_dend1, z_dend2)

            # Re-import the cell and check if change persists
            x,y,z = bcn.client.run_command(
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
            )

            self.assertAlmostEqual(z, 100, 1)

            # And that duplicate objects were not created
            count = bcn.client.run_command(
                "cellObjs = [ob for ob in bpy.data.objects if 'TestCell[0].soma' in ob.name];"
                "return_value = len(cellObjs)"
            )

            self.assertEqual(count, 1)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_import_remove_import_again(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();')

            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )


            # Import the cell and check if created in correct location
            x,y,z = bcn.client.run_command(
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
            )


            self.assertAlmostEqual(x, 150, 1)
            self.assertAlmostEqual(y, -176, 1)
            self.assertAlmostEqual(z, 0, 1)

            # Shift the cell up by 100 um
            bcn.client.run_command(
                "bpy.data.objects['TestCell[0].soma'].location = [150, -176, 100];"
            )


            # Re-Import the cell and check if overwrote the shift above
            x,y,z = bcn.client.run_command(
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
            )


            self.assertAlmostEqual(z, 0, 1)


            # Shift the cell up again by 100 um
            bcn.client.run_command(
                "bpy.data.objects['TestCell[0].soma'].location = [150, -176, 100];"
            )

            # Remove the group, there should be no cell objects
            count = bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_remove();"
                "return_value = len([ob for ob in bpy.data.objects if 'TestCell[0].soma' in ob.name])"
            )

            # Add a new group, import it
            x,y,z = bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_add();"
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = list(bpy.data.objects['TestCell[0].soma'].location)"
            )

            # The z position should be the original position (not shifted)
            self.assertAlmostEqual(z, 0, 1)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_object_levels(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Load TestCell.hoc - and add somatic stimulus
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();'
                                   'ic = h.IClamp(0.5);'
                                   'ic.amp = 1; ic.delay = 1; ic.dur = 10;'
            )

            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )

            # ----------------- Cell level objects --------------- #
            soma_object_exists, dendrite_object_exists = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].interaction_granularity = 'Cell';"
                "bpy.ops.blenderneuron.import_groups();"
                "objs = bpy.data.objects;"
                "return_value = ('TestCell[0].soma' in objs, 'TestCell[0].dendrites[0]' in objs);"
            )

            self.assertTrue(soma_object_exists)
            self.assertFalse(dendrite_object_exists)

            # Import animation - animate WHOLE CELL
            soma_mat_exists, dendrite_mat_exists,  = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].record_activity = True;"
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].recording_granularity = 'Cell';"
                "bpy.ops.blenderneuron.import_groups();"
                "mats = bpy.data.materials;"
                "return_value = ('TestCell[0].soma' in mats, 'TestCell[0].dendrites[0]' in mats);"
            )

            self.assertTrue(soma_mat_exists)
            self.assertFalse(dendrite_mat_exists)

            soma_emission_start, soma_emission_end,  = bcn.client.run_command(
                "mats = bpy.data.materials;"
                "bpy.context.scene.frame_set(0);"
                "start_emit = mats['TestCell[0].soma'].emit;"
                "bpy.context.scene.frame_set(5);"
                "end_emit = mats['TestCell[0].soma'].emit;"
                "return_value = (start_emit, end_emit);"
            )

            self.assertGreater(soma_emission_start, 0)
            self.assertGreater(soma_emission_end, soma_emission_start)

            # Import animation - animate EACH SECTION
            soma_mat_exists, dendrite_mat_exists,  = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].record_activity = True;"
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].recording_granularity = 'Section';"
                "bpy.ops.blenderneuron.import_groups();"
                "mats = bpy.data.materials;"
                "return_value = ('TestCell[0].soma' in mats, 'TestCell[0].dendrites[0]' in mats);"
            )

            self.assertTrue(soma_mat_exists)
            self.assertTrue(dendrite_mat_exists)

            dend_emission_start, dend_emission_end,  = bcn.client.run_command(
                "mats = bpy.data.materials;"
                "bpy.context.scene.frame_set(0);"
                "start_emit = mats['TestCell[0].dendrites[0]'].emit;"
                "bpy.context.scene.frame_set(5);"
                "end_emit = mats['TestCell[0].dendrites[0]'].emit;"
                "return_value = (start_emit, end_emit);"
            )

            self.assertGreater(dend_emission_start, 0)
            self.assertGreater(dend_emission_end, dend_emission_start)

            # --------------- Section level objects ------------------- #
            soma_object_exists, dendrite_object_exists = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].interaction_granularity = 'Section';"
                "bpy.ops.blenderneuron.import_groups();"
                "objs = bpy.data.objects;"
                "return_value = ('TestCell[0].soma' in objs, 'TestCell[0].dendrites[0]' in objs);"
            )

            self.assertTrue(soma_object_exists)
            self.assertTrue(dendrite_object_exists)

            # Import animation - animate WHOLE CELL
            soma_mat_exists, dendrite_mat_exists,  = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].record_activity = True;"
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].recording_granularity = 'Cell';"
                "bpy.ops.blenderneuron.import_groups();"
                "mats = bpy.data.materials;"
                "return_value = ('TestCell[0].soma' in mats, 'TestCell[0].dendrites[0]' in mats);"
            )

            self.assertTrue(soma_mat_exists)
            self.assertFalse(dendrite_mat_exists)

            soma_emission_start, soma_emission_end,  = bcn.client.run_command(
                "mats = bpy.data.materials;"
                "bpy.context.scene.frame_set(0);"
                "start_emit = mats['TestCell[0].soma'].emit;"
                "bpy.context.scene.frame_set(5);"
                "end_emit = mats['TestCell[0].soma'].emit;"
                "return_value = (start_emit, end_emit);"
            )

            self.assertGreater(soma_emission_start, 0)
            self.assertGreater(soma_emission_end, soma_emission_start)

            # Import animation - animate EACH SECTION
            soma_mat_exists, dendrite_mat_exists,  = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].record_activity = True;"
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].recording_granularity = 'Section';"
                "bpy.ops.blenderneuron.import_groups();"
                "mats = bpy.data.materials;"
                "return_value = ('TestCell[0].soma' in mats, 'TestCell[0].dendrites[0]' in mats);"
            )

            self.assertTrue(soma_mat_exists)
            self.assertTrue(dendrite_mat_exists)

            dend_emission_start, dend_emission_end,  = bcn.client.run_command(
                "mats = bpy.data.materials;"
                "bpy.context.scene.frame_set(0);"
                "start_emit = mats['TestCell[0].dendrites[0]'].emit;"
                "bpy.context.scene.frame_set(5);"
                "end_emit = mats['TestCell[0].dendrites[0]'].emit;"
                "return_value = (start_emit, end_emit);"
            )

            self.assertGreater(dend_emission_start, 0)
            self.assertGreater(dend_emission_end, dend_emission_start)


            # Test group renaming logic
            group_name = bcn.client.run_command(
                "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[0];"
                "group.name = 'TEST_GROUP';"
                "return_value = group.name;"
            )

            self.assertEqual(group_name, 'TEST_GROUP')


            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_ugly_render_curves(self):

        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
             Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            # Load TestCell.hoc
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();')

            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )

            # Non-smooth curves
            bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].interaction_granularity = 'Cell';"
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].smooth_sections = False;"
                "bpy.ops.blenderneuron.import_groups();"
            )

            # Non-smooth curves
            bevel = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].interaction_granularity = 'Cell';"
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].as_lines = True;"
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = bpy.data.curves['Group.000_bezier.001'].bevel_depth"
            )

            # Should have no bevel
            self.assertEqual(bevel, 0)

    def test_copy_group(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc1 = h.TestCell();')

            # Load cell into first group
            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )

            # Create 2nd cell
            ncn.client.run_command('tc2 = h.TestCell();')

            # Add second group, and shift 2nd cell up by 5 um
            bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_add();"
                "bpy.ops.blenderneuron.import_groups();"
                "bpy.data.objects['TestCell[1].soma'].location[2] += 5;"
            )

            # Test group copying logic
            group_int_granularity = bcn.client.run_command(
                "bpy.data.scenes['Scene'].BlenderNEURON.groups[0].interaction_granularity = 'Section';"
                "bpy.context.scene.BlenderNEURON.groups_index = 1;"
                "group = bpy.data.scenes['Scene'].BlenderNEURON.groups[1];"
                "group.copy_from_group = 'Group.000';"
                "bpy.ops.blenderneuron.copy_from_group();"
                "return_value = group.interaction_granularity;"
            )

            self.assertEqual(group_int_granularity, 'Section')

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_save_groups(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc1 = h.TestCell();')

            # Load cell into first group
            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )

            # Create 2nd cell
            ncn.client.run_command('tc2 = h.TestCell();')

            # Add second group, and shift 2nd cell up by 5 um
            bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_add();"
                "bpy.ops.blenderneuron.import_groups();"
                "bpy.data.objects['TestCell[1].soma'].location[2] += 5;"
            )

            file1 = 'test_group1.json'
            file2 = 'test_group2.json'

            try:

                # Test group saving
                bcn.client.run_command(
                    "groups = bpy.types.Object.BlenderNEURON_node.groups;"
                    "groups['Group.000'].to_file('" + file1 + "');"
                    "groups['Group.001'].to_file('" + file2 + "');"
                )

                # Read the saved files
                import json
                with open(file1) as f1, open(file2) as f2:
                    json1 = json.load(f1)
                    json2 = json.load(f2)


                # check that correct cells were saved
                self.assertEqual(json1['roots'][0]['name'], 'TestCell[0].soma')
                self.assertEqual(json2['roots'][0]['name'], 'TestCell[1].soma')


                # Check that the z-location was saved correctly
                self.assertEqual(json1['roots'][0]['coords'][-1], 0)

                # 2nd cell should be shifted up by 5um
                self.assertEqual(json2['roots'][0]['coords'][-1], 5)

            finally:
                os.remove(file1)
                os.remove(file2)

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()

    def test_remove_cells_groups(self):

        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
                Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc1 = h.TestCell();')

            # Load cell into first group
            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
            )

            # Create 2nd cell
            ncn.client.run_command('tc2 = h.TestCell();')

            # Add second group, and shift 2nd cell up by 5 um
            group_count = bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_add();"
                "bpy.ops.blenderneuron.import_groups();"
                "bpy.data.objects['TestCell[1].soma'].location[2] += 5;"
                "return_value = len(bpy.context.scene.BlenderNEURON.groups);"
            )

            self.assertEqual(group_count, 2)

            # Unselect 2nd cell from 2nd group and remove the empty group
            group_count = bcn.client.run_command(
                "bpy.context.scene.BlenderNEURON.groups[1].root_entries[1].selected = False;"
                "bpy.ops.blenderneuron.cell_group_remove();"
                "return_value = len(bpy.context.scene.BlenderNEURON.groups);"
            )

            self.assertEqual(group_count, 1)

            # Remove the last group
            group_count = bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_remove();"
                "return_value = len(bpy.context.scene.BlenderNEURON.groups);"
            )

            self.assertEqual(group_count, 0)

    def test_remove_cell_from_nrn(self):

        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
                Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            # Load TestCell.hoc - create a group
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc1 = h.TestCell();')

            # Load cell into first group and show it
            bcn.client.run_command(
                "bpy.ops.blenderneuron.get_cell_list_from_neuron();"
                "bpy.ops.blenderneuron.import_groups();"
            )

            # Create 2nd cell
            ncn.client.run_command('tc2 = h.TestCell();')

            # Delete the first cell from NRN
            ncn.client.run_command('tc1 = None;'
                                   'del tc1;')

            # Add second group, check the number of ui cells
            ui_cell_count = bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_add();"
                "bpy.ops.blenderneuron.import_groups();"
                "return_value = len(bpy.context.scene.BlenderNEURON.groups[0].root_entries);"
            )

            self.assertEqual(ui_cell_count, 1)

            # Get the name of the visible cell of the second group
            ui_cell_name = bcn.client.run_command(
                "return_value = bpy.context.scene.BlenderNEURON.groups[1].root_entries[0].name;"
            )

            self.assertEqual(ui_cell_name, "TestCell[1].soma")


if __name__ == '__main__':
    unittest.main()
