import copy
import json
import unittest
from types import SimpleNamespace
from blenderneuron.nrn.neuronnode import NeuronNode


class TestMorphologyPartition(unittest.TestCase):
    def setUp(self):
        self.node = NeuronNode.__new__(NeuronNode)
        self.node.parallel_ctx = SimpleNamespace(nhost=lambda: 3)
        self.node.mpimap = {'Cell[%d]' % i: {'name': 'Cell[0]', 'rank': i % 2}
                            for i in range(4)}
        self.groups = [dict(name='g%d' % g, record_activity=True,
                            roots=[dict(name='Cell[%d].soma' % i,
                                        coords=list(range(300)),
                                        children=[dict(name='Cell[%d].dend' % i)])
                                   for i in (g * 2, g * 2 + 1)]) for g in range(2)]

    def test_partition(self):
        before = copy.deepcopy(self.groups)
        parts = self.node._partition_morphology_updates(self.groups)
        self.assertEqual(before, self.groups)
        for rank, part in enumerate(parts):
            self.assertEqual([g['name'] for g in part], ['g0', 'g1'])
            self.assertTrue(all(g['record_activity'] for g in part))
            roots = [r for g in part for r in g['roots']]
            expected = [] if rank == 2 else [self.groups[g]['roots'][rank] for g in range(2)]
            self.assertEqual(roots, expected)
        sizes = [sum(len(json.dumps(r)) for g in p for r in g['roots']) for p in parts]
        total = sum(len(json.dumps(r)) for g in self.groups for r in g['roots'])
        self.assertEqual(sum(sizes), total)
        self.assertLessEqual(max(sizes), total * .6)

    def test_validation_before_dispatch(self):
        self.node._uses_mpi_coordinator = lambda: True
        self.node._mpi_request_targeted = lambda *a: self.fail('dispatched invalid export')
        for bad in [-1, 3, .5, True, '1', float('nan')]:
            self.node.mpimap['Cell[3]']['rank'] = bad
            with self.assertRaisesRegex(ValueError, 'g1.*Cell'):
                self.node.update_groups(self.groups)
        del self.node.mpimap['Cell[3]']
        with self.assertRaisesRegex(ValueError, 'Missing ownership'):
            self.node.update_groups(self.groups)
        self.groups[1]['roots'] = [self.groups[0]['roots'][0]]
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.node.update_groups(self.groups)

    def test_mpi_geometry_and_recovery(self):
        import os
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ['mpiexec', '--allow-run-as-root', '-n', '2', 'nrniv', '-mpi',
                 '-python', 'tests/mpi_morphology_worker.py', directory],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            parts = [json.loads(__import__('pathlib').Path(directory, 'rank-%d.json' % rank).read_text())
                     for rank in range(2)]
            sizes = [sum(len(json.dumps(r)) for g in p for r in g['roots']) for p in parts]
            self.assertLessEqual(max(sizes), sum(sizes) * .6)

    def test_targeted_collectives_and_error_order(self):
        calls = []
        def exchange(values):
            calls.append(values)
            if len(calls) == 2:
                return [{'ok': False, 'error': 'first traceback'},
                        {'ok': False, 'error': 'second traceback'}, None]
        self.node._uses_mpi_coordinator = lambda: True
        self.node.parallel_ctx.py_alltoall = exchange
        self.node._mpi_operation_response = lambda op, payload: {'ok': True, 'result': payload}
        with self.assertRaisesRegex(ValueError, 'one MPI payload'):
            self.node._mpi_request_targeted('update_groups', [])
        with self.assertRaisesRegex(RuntimeError, 'rank 0 failed update_groups.*'):
            self.node._mpi_request_targeted('update_groups', ['zero', 'one', 'two'])
        self.assertEqual(calls[0], [('update_groups', p) for p in ['zero', 'one', 'two']])
        self.assertEqual(calls[1][0]['result'], 'zero')
        self.assertEqual(len(calls), 2)

    def test_local_path(self):
        self.node._uses_mpi_coordinator = lambda: False
        received = []
        self.node._update_groups_local = received.append
        self.node.update_groups(self.groups)
        self.assertIs(received[0], self.groups)


if __name__ == '__main__':
    unittest.main()
