# From repo root, run all tests with 'python tests/test_MPI.py'
# Run single test with: 'python tests/test_MPI.py TestMPI.test_method'

import unittest
import json
import os, sys
import subprocess
import tempfile
from multiprocessing import Process, Queue
from pathlib import Path
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from blenderneuron.nrn.neuronnode import NeuronNode
from tests import test_hoc_file, Blender, NEURON, BlenderTestCase


class TestMPI(BlenderTestCase):
    def test_merge_duplicate_local_cell_names(self):
        node = NeuronNode.__new__(NeuronNode)
        node.mpimap = {
            "MitralCell[0]": {"name": "MitralCell[0]", "rank": 0},
            "MitralCell[1]": {"name": "MitralCell[0]", "rank": 1},
        }
        fragments = [[{"name": "Group", "roots": [{"name": "MitralCell[0].soma"}]}],
                     [{"name": "Group", "roots": [{"name": "MitralCell[0].soma"}]}]]
        merged = node.merge_mpi_group_fragments(fragments)
        self.assertEqual([root["name"] for root in merged[0]["roots"]],
                         ["MitralCell[0].soma", "MitralCell[1].soma"])

    def test_duplicate_hoc_cell_names(self):
        with tempfile.TemporaryDirectory() as directory:
            command = ["mpiexec", "--allow-run-as-root", "-n", "2", "nrniv", "-mpi",
                       "-python", "tests/mpi_duplicate_hoc_worker.py", directory]
            environment = dict(os.environ, OMPI_ALLOW_RUN_AS_ROOT="1",
                               OMPI_ALLOW_RUN_AS_ROOT_CONFIRM="1")
            completed = subprocess.run(command, cwd=os.getcwd(), env=environment,
                                       text=True, capture_output=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            groups = json.loads((Path(directory) / "rank-0.json").read_text())
            self.assertEqual([root["name"] for root in groups[0]["roots"]],
                             ["TestCell_rank0[0].soma", "TestCell_rank1[0].soma"])

    def test_two_rank_activity_collection(self):
        """Rank zero imports a complete, deterministic activity payload."""
        with tempfile.TemporaryDirectory() as directory:
            command = [
                "mpiexec", "--allow-run-as-root", "-n", "2", "nrniv", "-mpi", "-python",
                "tests/mpi_activity_worker.py", directory,
            ]
            environment = dict(os.environ, OMPI_ALLOW_RUN_AS_ROOT="1",
                               OMPI_ALLOW_RUN_AS_ROOT_CONFIRM="1")
            completed = subprocess.run(command, cwd=os.getcwd(), env=environment,
                                       text=True, capture_output=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

            records = [json.loads((Path(directory) / ("rank-%d.json" % rank)).read_text())
                       for rank in range(2)]
            self.assertEqual([record["rank"] for record in records], [0, 1])
            self.assertIsNone(records[1]["groups"])

            groups = records[0]["groups"]
            self.assertEqual(len(groups), 1)
            roots = groups[0]["roots"]
            self.assertEqual([root["name"] for root in roots],
                             ["Cell[0].soma", "Cell[1].soma"])
            for root in roots:
                self.assertEqual(set(root["segment_activity"]), {"0", "1"})
                for values in root["segment_activity"].values():
                    self.assertEqual(len(values["values"]),
                                     len(groups[0]["activity"]["times"]))

            # Every Blender-facing operation is sent only through rank zero.
            self.assertEqual([root["name"] for root in records[0]["roots"]],
                             ["Cell[0].soma", "Cell[1].soma"])
            self.assertEqual([root["name"] for root in records[0]["initialized_groups"][0]["roots"]],
                             ["Cell[0].soma", "Cell[1].soma"])
            for record in records:
                self.assertAlmostEqual(record["tstop"], 2.0)
                self.assertAlmostEqual(record["dt"], 0.05)
                self.assertAlmostEqual(record["celsius"], 33.0)
                self.assertAlmostEqual(record["first_x"], 100.0)
                self.assertEqual(record["synapse_count"], 0)

    def test_mpi(self):
        with NEURON(), CommNode("Control-NEURON") as ncn, \
                Blender(), CommNode("Control-Blender") as bcn:

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
        with NEURON(), CommNode("Control-NEURON") as ncn, \
                Blender(), CommNode("Control-Blender") as bcn:

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
