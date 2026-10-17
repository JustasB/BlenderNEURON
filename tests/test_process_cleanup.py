"""Regression tests for failed startup and unresponsive test children."""
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from tests import BlenderNEURONProcess, BlenderTestCase
from tests.process_utils import stop_process_group


class PythonProcess(BlenderNEURONProcess):
    executable = sys.executable


def python_args(code):
    return '-c ' + shlex.quote(code)


class TestProcessCleanup(BlenderTestCase):
    def test_context_exception_stops_process(self):
        process = PythonProcess(cmd_args=python_args('import time; time.sleep(60)'), sleep=0)
        with self.assertRaisesRegex(ValueError, 'test failure'):
            with process:
                raise ValueError('test failure')
        self.assertIsNotNone(process.process.poll())

    def test_startup_timeout_cleans_process_and_address(self):
        process = PythonProcess(cmd_args=python_args('import time; time.sleep(60)'))
        process.server_end = 'cleanup-test'
        process.startup_timeout = 0.2
        with self.assertRaisesRegex(RuntimeError, 'did not become ready'):
            with process:
                self.fail('Startup should fail')
        self.assertIsNotNone(process.process.poll())
        self.assertFalse(os.path.exists(process.address_file(process.server_end)))

    def test_startup_crash_fails_promptly(self):
        process = PythonProcess(cmd_args=python_args('raise SystemExit(7)'))
        process.server_end = 'cleanup-test'
        with self.assertRaisesRegex(RuntimeError, 'status 7'):
            with process:
                self.fail('Startup should fail')

    def test_unresponsive_process_is_killed_without_touching_peer(self):
        with tempfile.TemporaryDirectory() as directory:
            ready = os.path.join(directory, 'ready')
            code = ('import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN);'
                    'open(%r, "w").close(); time.sleep(60)' % ready)
            peer = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                    start_new_session=True)
            process = subprocess.Popen([sys.executable, '-c', code], start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while not os.path.exists(ready) and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(os.path.exists(ready))
                stop_process_group(process, timeout=0.2)
                self.assertEqual(process.returncode, -signal.SIGKILL)
                self.assertIsNone(peer.poll())
            finally:
                stop_process_group(process)
                stop_process_group(peer)

    def check_runner_cleanup(self, hang, interrupt=False):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = os.path.join(directory, 'child.pid')
            script = os.path.join(directory, 'fixture.py')
            with open(script, 'w') as stream:
                stream.write(
                    'import subprocess, sys, time\n'
                    'child = subprocess.Popen([sys.executable, "-c", '
                    '"import time; time.sleep(60)"], start_new_session=True)\n'
                    'with open(%r, "w") as stream: stream.write(str(child.pid))\n'
                    '%s\n' % (pid_file, 'time.sleep(60)' if hang else 'pass'))
            code = (
                'import unittest, test_with_coverage as runner;'
                'suite = unittest.TestSuite([unittest.TestCase()]);'
                'runner.unittest.TestLoader.discover = lambda *a, **k: suite;'
                'runner.test_file = lambda test: %r;'
                'import sys; sys.exit(runner.main())' % script)
            env = dict(os.environ, BLENDERNEURON_TEST_TIMEOUT='2')
            runner = subprocess.Popen([sys.executable, '-c', code], env=env)
            try:
                if interrupt:
                    deadline = time.monotonic() + 5
                    while not os.path.exists(pid_file) and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(os.path.exists(pid_file))
                    runner.terminate()
                status = runner.wait(timeout=15)
                if interrupt:
                    self.assertNotEqual(status, 0)
                else:
                    self.assertEqual(status, 124 if hang else 0)
            finally:
                if runner.poll() is None:
                    runner.kill()
                    runner.wait(timeout=3)
            with open(pid_file) as stream:
                child_pid = int(stream.read())
            self.assertFalse(os.path.exists('/proc/%s' % child_pid),
                             'Runner left an orphan or zombie child')

    def test_runner_reaps_orphans_after_normal_exit(self):
        self.check_runner_cleanup(hang=False)

    def test_runner_reaps_orphans_after_timeout(self):
        self.check_runner_cleanup(hang=True)

    def test_runner_reaps_orphans_after_interruption(self):
        self.check_runner_cleanup(hang=True, interrupt=True)

    def test_worker_crash_does_not_wait_forever(self):
        def crash():
            os._exit(7)
        with self.assertRaisesRegex(RuntimeError, 'without a result'):
            self.in_separate_process(crash, timeout=1)

    def test_worker_timeout(self):
        def hang():
            time.sleep(60)
        with self.assertRaises(TimeoutError):
            self.in_separate_process(hang, timeout=0.2)


if __name__ == '__main__':
    unittest.main()
