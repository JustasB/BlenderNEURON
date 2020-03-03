# From repo root, run all tests with 'python tests/test_synapse_former.py'
# Run single test with: 'python tests/test_synapse_former.py TestSynapseFormer.test_find_synapses'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, NEURON, Blender, BlenderTestCase
from math import pi
degs = 180/pi

class TestSynapseFormer(BlenderTestCase):

    def test_find_synapses(self):

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
            bcn.client.run_command(
                "bpy.ops.blenderneuron.cell_group_add();"
                "bpy.ops.blenderneuron.import_groups();"
                "bpy.data.objects['TestCell[1].soma'].location[2] += 5;"
            )

            # Setup synapse former to look for synapses between the two cells
            syn_count = bcn.client.run_command(
                "syn_set = bpy.data.scenes['Scene'].BlenderNEURON.synapse_sets[0];"
                "syn_set.section_pattern_source = '*dend*';"
                "syn_set.group_dest = 'Group.001';"
                "syn_set.is_reciprocal = True;"
                "syn_set.create_spines = True;"
                "syn_set.use_radius = False;"
                "syn_set.max_syns_per_pt = 1;"
                "bpy.ops.blenderneuron.find_synapse_locations();"
                "return_value = len(bpy.data.objects['SynapsePreview'].data.splines)"
            )

            self.assertEqual(syn_count, 32)

            # There should be no synapses when max search distance is very small
            syn_count = bcn.client.run_command(
                "syn_set = bpy.data.scenes['Scene'].BlenderNEURON.synapse_sets[0];"
                "syn_set.max_distance = 1;"
                "bpy.ops.blenderneuron.find_synapse_locations();"
                "return_value = len(bpy.data.objects['SynapsePreview'].data.splines)"
            )

            self.assertEqual(syn_count, 0)

            # When using radius, it should find the same synapses at a shortened distance
            syn_count = bcn.client.run_command(
                "syn_set = bpy.data.scenes['Scene'].BlenderNEURON.synapse_sets[0];"
                "syn_set.use_radius = True;"
                "syn_set.max_distance = 4;"
                "bpy.ops.blenderneuron.find_synapse_locations();"
                "return_value = len(bpy.data.objects['SynapsePreview'].data.splines)"
            )

            self.assertEqual(syn_count, 32)

            # Sub-divide the cell sections in NEURON
            ncn.client.run_command("[setattr(sec,'nseg', 10) for sec in h.allsec()];")

            # And create the found synapses
            bcn.client.run_command("bpy.ops.blenderneuron.create_synapses();")

            # check if the syns were created correctly in NEURON
            syn1_sec, syn1_x = ncn.client.run_command(
                'seg = h.ExpSyn[0].get_segment();'
                'return_value = (seg.sec.name(), seg.x);'
            )

            self.assertEqual(syn1_sec, 'TestCell[1].dendrites[4]')
            self.assertEqual(syn1_x, 0.95) # middle of the 10th segment = 0.95

            syn2_sec, syn2_x = ncn.client.run_command(
                'seg = h.ExpSyn[1].get_segment();'
                'return_value = (seg.sec.name(), seg.x);'
            )

            self.assertEqual(syn2_sec, 'SynapseSet_001_Spine[0].head')
            self.assertEqual(syn2_x, 0.5) # middle of the spine head


            # Save the found synapses into a JSON file
            syn_file = 'syn_test.json'

            bcn.client.run_command("bpy.context.scene.BlenderNEURON.synapse_set.save_synapses('" + syn_file + "');")

            import json
            with open(syn_file) as f:
                syns = json.load(f)

            import os
            try:
                os.remove(syn_file)
            except:
                pass

            self.assertEqual(syns['entries'][0]['dest_section'], 'TestCell[1].dendrites[4]')
            self.assertEqual(syns['entries'][0]['source_section'], 'TestCell[0].dendrites[4]')
            self.assertEqual(syns['entries'][0]['dest_x'], 1.0)
            self.assertEqual(syns['entries'][0]['source_x'], 1.0)

            # Test renaming logic
            syn_set_name = bcn.client.run_command(
                "syn_set = bpy.data.scenes['Scene'].BlenderNEURON.synapse_sets[0];"
                "syn_set.name = 'TEST_NAME';"
                "return_value = syn_set.name;"
            )

            self.assertEqual(syn_set_name, 'TEST_NAME')


if __name__ == '__main__':
    unittest.main()
