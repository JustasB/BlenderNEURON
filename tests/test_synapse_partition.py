import copy
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from blenderneuron.nrn.neuronnode import NeuronNode


class TestSynapsePartition(unittest.TestCase):
    def setUp(self):
        self.node = NeuronNode.__new__(NeuronNode)
        self.node.parallel_ctx = SimpleNamespace(nhost=lambda: 3)
        self.node.mpimap = {'Cell[%d]' % i: dict(name='Cell[0]', rank=float(i)) for i in range(3)}
        base = json.loads(Path('tests/test_synset.json').read_text())['entries'][0]
        self.payload = dict(name='set', entries=[
            dict(base, source_section='Cell[0].soma', dest_section='Cell[%d].soma' % i)
            for i in (0, 1, 0)])

    def test_routing_and_metadata(self):
        before = copy.deepcopy(self.payload)
        parts, checks = self.node._partition_synapse_set(self.payload)
        self.assertEqual(self.payload, before)
        self.assertEqual([p['_entry_indices'] for p in parts], [[0, 1, 2], [1], []])
        self.assertEqual([len(p['entries']) for p in parts], [3, 1, 0])
        self.assertTrue(all(p['name'] == 'set' for p in parts))
        self.assertEqual(checks[2]['sections'], [])

    def test_invalid_ownership_before_dispatch(self):
        self.node._uses_mpi_coordinator = lambda: True
        self.node._mpi_request_targeted = lambda *args: self.fail('Invalid dispatch')
        for rank in (-1, 3, .5, True, '1', None):
            self.node.mpimap['Cell[1]']['rank'] = rank
            with self.assertRaisesRegex(ValueError, "set.*entry 1"):
                self.node.create_synapses(self.payload)
        del self.node.mpimap['Cell[1]']
        with self.assertRaisesRegex(ValueError, 'Missing ownership'):
            self.node.create_synapses(self.payload)
        del self.payload['entries'][0]['source_section']
        with self.assertRaisesRegex(ValueError, 'Missing source_section'):
            self.node.create_synapses(self.payload)

    def test_local_compatibility(self):
        self.node._uses_mpi_coordinator = lambda: False
        values = []
        self.node._create_synapses_local = values.append
        self.node.create_synapses(self.payload)
        self.assertIs(values[0], self.payload)

    def test_three_rank_broadcast_equivalence(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ('broadcast', 'targeted'):
                run = subprocess.run(['mpiexec', '--allow-run-as-root', '-n', '3',
                                      'nrniv', '-mpi', '-python',
                                      'tests/mpi_synapse_partition_worker.py', mode, directory],
                                     capture_output=True, text=True, timeout=60)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            total = 0
            for rank in range(3):
                old, new = [json.loads(Path(directory, '%s-%d.json' % (mode, rank)).read_text())
                            for mode in ('broadcast', 'targeted')]
                self.assertEqual(old['components'], new['components'])
                self.assertEqual(old['gids'], new['gids'])
                self.assertEqual(len(new['received']), [3, 2, 0][rank])
                total += len(new['received'])
            self.assertEqual(total, 5)


if __name__ == '__main__':
    unittest.main()
