"""Batching must preserve bounded execution, fail-fast behavior, and cleanup."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_with_coverage as runner
from tests import BackgroundBlender, Blender


class TestTestRunner(unittest.TestCase):
    def test_batch_selection_is_explicit_and_can_be_disabled(self):
        names = ['test_serializer.TestSerialization.test_a',
                 'test_serializer.TestSerialization.test_b',
                 'test_process_cleanup.TestProcessCleanup.test_a',
                 'new_module.Unknown.test_a', 'new_module.Unknown.test_b']
        tests = [SimpleNamespace(id=lambda name=name: name) for name in names]
        with patch.dict(os.environ, BLENDERNEURON_TEST_BATCH='1'):
            self.assertEqual([len(b) for b in runner.test_batches(tests)], [2, 1, 1, 1])
        with patch.dict(os.environ, BLENDERNEURON_TEST_BATCH='0'):
            self.assertEqual([len(b) for b in runner.test_batches(tests)], [1] * 5)

    def test_background_command_and_gui_fallback(self):
        with patch.dict(os.environ, BLENDERNEURON_TEST_HEADLESS='1'):
            command = BackgroundBlender().cmd_args
            self.assertIn('--background', command)
            self.assertIn('--python-exit-code 1', command)
            self.assertIn('tests/background_blender.py', command)
        with patch.dict(os.environ, BLENDERNEURON_TEST_HEADLESS='0'):
            self.assertEqual(BackgroundBlender().cmd_args, Blender.cmd_args)

    def check_batch(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory, 'marker')
            pid_file = Path(directory, 'child.pid')
            module = Path(directory, 'batch_fixture.py')
            module.write_text(
                'import os, subprocess, sys, time, unittest\n'
                'class Fixture(unittest.TestCase):\n'
                '    def test_a(self):\n'
                '        with open(%r, "a") as stream: stream.write(str(os.getpid()) + "\\n")\n'
                '        if %r == "success": time.sleep(.9)\n'
                '        else:\n'
                '            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)\n'
                '            with open(%r, "w") as stream: stream.write(str(child.pid))\n'
                '            if %r == "exit": os._exit(0)\n'
                '            if %r == "failure": self.fail("deliberate failure")\n'
                '            time.sleep(60)\n'
                '    def test_b(self):\n'
                '        with open(%r, "a") as stream: stream.write(str(os.getpid()) + "\\n")\n'
                '        time.sleep(.9)\n' % (str(marker), mode, str(pid_file), mode, mode, str(marker)))
            code = (
                'import ctypes, signal, sys, unittest; import test_with_coverage as r;'
                'ctypes.CDLL(None).prctl(36, 1, 0, 0, 0);'
                'signal.signal(signal.SIGTERM, r.interrupted);'
                'suite=unittest.defaultTestLoader.loadTestsFromName("batch_fixture.Fixture");'
                'sys.exit(r.run_batch(list(suite), 1.5))')
            env = dict(os.environ, PYTHONPATH=directory + os.pathsep + os.getcwd())
            process = subprocess.Popen([sys.executable, '-c', code], env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                if mode == 'interrupt':
                    deadline = time.monotonic() + 5
                    while not pid_file.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(pid_file.exists())
                    process.terminate()
                output, _ = process.communicate(timeout=15)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=3)
            expected = {'success': 0, 'failure': 1, 'timeout': 124, 'exit': 1}
            if mode == 'interrupt':
                self.assertNotEqual(process.returncode, 0, output)
            else:
                self.assertEqual(process.returncode, expected[mode], output)
            pids = marker.read_text().splitlines()
            self.assertEqual(len(pids), 2 if mode == 'success' else 1, output)
            self.assertEqual(len(set(pids)), 1, 'Batch spawned a new interpreter per test')
            if pid_file.exists():
                self.assertFalse(Path('/proc', pid_file.read_text()).exists(), output)

    def test_batch_reuses_interpreter_and_resets_deadline(self):
        # Two .9s tests: independent 1.5s deadlines, not one batch budget.
        self.check_batch('success')

    def test_batch_failure_stops_and_reaps_orphans(self):
        self.check_batch('failure')
        # A zero exit without the completion marker must not hide skipped tests.
        self.check_batch('exit')

    def test_batch_timeout_stops_and_reaps_orphans(self):
        self.check_batch('timeout')

    def test_batch_interruption_reaps_orphans(self):
        self.check_batch('interrupt')


if __name__ == '__main__':
    unittest.main()
