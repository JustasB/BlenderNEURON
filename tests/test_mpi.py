# From repo root, run all tests with 'python tests/test_MPI.py'
# Run single test with: 'python tests/test_MPI.py TestMPI.test_method'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, NEURON, BlenderTestCase


class TestMPI(BlenderTestCase):
    def test_mpi(self):
        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
                Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            # Load TestCell.hoc - create a cell name:mpi rank map
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();'
                                   'from blenderneuron.neuronstart import BlenderNEURON as bn_node;')

            # Get section name before MPI map is provided
            self.assertEqual(ncn.client.run_command('return_value = bn_node.rank_section_name(tc.soma.name());'),
                             'TestCell[0].soma')

            # Provide MPI map
            ncn.client.run_command('pc = h.ParallelContext();'
                                   'single_rank_name = "TestCell[0]";'
                                   'mpi_rank_name =    "TestCell[0]";'
                                   'mpimap = {};'
                                   'mpimap[single_rank_name] = { "name": mpi_rank_name, "rank": pc.id() };'            
                                   'mpimap["TestCell[1]"] = { "name": mpi_rank_name, "rank": 2 };'
                                   'bn_node.init_mpi(pc, mpimap);')

            # Get section name after MPI init
            self.assertEqual(ncn.client.run_command('return_value = bn_node.rank_section_name(tc.soma.name());'),
                             'TestCell[0].soma')

            # Cell without a specific section
            self.assertEqual(ncn.client.run_command('return_value = bn_node.rank_section_name("TestCell[0]");'),
                             'TestCell[0]')

            # Try section that does not exist on the rank
            self.assertEqual(ncn.client.run_command('return_value = bn_node.rank_section_name("TestCell[1].soma");'),
                             None)

    def test_mpi_synset(self):
        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
                Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            # Load TestCell.hoc - create a cell name:mpi rank map
            ncn.client.run_command('h.load_file("tests/TestCell.hoc");'
                                   'tc = h.TestCell();'
                                   'from blenderneuron.neuronstart import BlenderNEURON as bn_node;'
                                   'bn_node.update_section_index();')


            # Provide MPI map - first cell on this rank, 2nd cell on another rank
            ncn.client.run_command('pc = h.ParallelContext();'
                                   'mpimap = {};'
                                   'mpimap["TestCell[0]"] = { "name": "TestCell[0]", "rank": 0 };'            
                                   'mpimap["TestCell[1]"] = { "name": "TestCell[1]", "rank": 1 };'
                                   'bn_node.init_mpi(pc, mpimap);')

            ncn.client.run_command('from json import load;'
                                   'f = open("tests/test_synset.json");'
                                   'bn_node.create_synapses(load(f));'
                                   'f.close();')


if __name__ == '__main__':
    unittest.main()
