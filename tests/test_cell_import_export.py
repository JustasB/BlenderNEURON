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

            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()


if __name__ == '__main__':
    unittest.main()
