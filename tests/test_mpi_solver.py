"""Fixed-step MPI solver comparison with a causal cross-rank synapse control."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class TestMPISolver(unittest.TestCase):
    def test_cross_rank_spike_transfer(self):
        results = {}
        with tempfile.TemporaryDirectory() as directory:
            for mode in ('psolve', 'hrun', 'disconnected'):
                output = Path(directory) / (mode + '.json')
                command = ['mpiexec', '--allow-run-as-root', '-n', '2', 'nrniv',
                           '-mpi', '-python', 'tests/mpi_solver_worker.py', mode, str(output)]
                completed = subprocess.run(
                    command, env=dict(os.environ, OMPI_ALLOW_RUN_AS_ROOT='1',
                                      OMPI_ALLOW_RUN_AS_ROOT_CONFIRM='1'),
                    text=True, capture_output=True, timeout=30)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                results[mode] = json.loads(output.read_text())['ranks']

        for mode in ('psolve', 'hrun'):
            source, target = results[mode]
            self.assertEqual(len(source['spikes_ms']), 1, mode)
            self.assertEqual(len(target['spikes_ms']), 1, mode)
            self.assertGreater(target['spikes_ms'][0], source['spikes_ms'][0] + 2, mode)
            self.assertGreater(max(target['voltage_mV']), 20, mode)
            self.assertLess(min(target['synaptic_current_nA']), -0.1, mode)
            self.assertAlmostEqual(target['times_ms'][-1], 25, places=6)
        source, target = results['disconnected']
        self.assertEqual(len(source['spikes_ms']), 1)
        self.assertEqual(target['spikes_ms'], [])
        self.assertLess(max(target['voltage_mV']), -60)
        self.assertTrue(all(value == 0 for value in target['synaptic_current_nA']))
        for parallel, standard in zip(results['psolve'], results['hrun']):
            for field in ('times_ms', 'voltage_mV', 'spikes_ms', 'synaptic_current_nA'):
                self.assertEqual(len(parallel[field]), len(standard[field]))
                for left, right in zip(parallel[field], standard[field]):
                    self.assertAlmostEqual(left, right, places=9, msg=field)


if __name__ == '__main__':
    unittest.main()
