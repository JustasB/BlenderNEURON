"""Exercise CI lane selection, failure reporting and deadline cleanup."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestCompatibilityRunner(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        scripts = self.root / 'scripts'
        (scripts / 'compatibility').mkdir(parents=True)
        for path in ('test-compatibility.py', 'compatibility/integration.py'):
            shutil.copy2(ROOT / 'scripts' / path, scripts / path)
        self.calls = self.root / 'docker-calls.jsonl'
        fake = self.root / 'docker'
        fake.write_text('#!' + sys.executable + '\n' + '''import json, os, sys, time
with open(os.environ['FAKE_DOCKER_CALLS'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'info':
    print(os.environ.get('FAKE_ARCH', 'x86_64'))
elif sys.argv[1] == 'run':
    print('individual test output', flush=True)
    time.sleep(float(os.environ.get('FAKE_SLEEP', '0')))
    if 'blenderneuron-integration:baseline' in sys.argv:
        sys.exit(int(os.environ.get('FAKE_FAILURE', '0')))
''')
        fake.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ['PATH'],
                        FAKE_DOCKER_CALLS=str(self.calls))

    def run_runner(self, *arguments, **environment):
        return subprocess.run([sys.executable, str(self.root / 'scripts/test-compatibility.py'),
                               '--skip-build'] + list(arguments),
                              env=dict(self.env, **environment), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=15)

    def read_result(self, lane):
        return json.loads((self.root / '.compatibility-results' / lane / 'result.json').read_text())

    def read_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_failed_lane_does_not_skip_later_lanes(self):
        completed = self.run_runner('baseline', 'neuron9', FAKE_FAILURE='7')
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(self.read_result('baseline')['exit_code'], 7)
        self.assertEqual(self.read_result('neuron9')['exit_code'], 0)
        self.assertIn('individual test output', completed.stdout)
        self.assertIn('individual test output', (self.root / '.compatibility-results/baseline/tests.log').read_text())
        runs = [call for call in self.read_calls() if call[0] == 'run']
        self.assertEqual(len(runs), 2)
        for call in runs:
            self.assertIn('/source/scripts/compatibility/integration_check.py', call)
            self.assertIn('BLENDERNEURON_TEST_KEEP_GOING=1', call)
            self.assertIn('OMPI_MCA_rmaps_base_oversubscribe=1', call)

    def test_suite_deadline_reports_timeout_and_removes_container(self):
        completed = self.run_runner('baseline', '--timeout', '1', FAKE_SLEEP='60')
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = self.read_result('baseline')
        self.assertEqual(result['exit_code'], 124)
        self.assertEqual(result['phase'], 'test')
        calls = self.read_calls()
        run = next(call for call in calls if call[0] == 'run')
        name = run[run.index('--name') + 1]
        self.assertIn(['rm', '-f', name], calls)

    def test_arm_host_does_not_silently_start_emulation(self):
        completed = self.run_runner('baseline', FAKE_ARCH='aarch64')
        self.assertEqual(completed.returncode, 2)
        self.assertIn('native x86-64', completed.stderr)
        self.assertFalse(any(call[0] == 'run' for call in self.read_calls()))

    def test_ci_matrix_covers_shared_lane_definitions_once(self):
        spec = importlib.util.spec_from_file_location('compatibility_matrix',
                                                      ROOT / 'scripts/compatibility/integration.py')
        matrix = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(matrix)
        config = (ROOT / '.circleci/config.yml').read_text()
        listed = re.findall(r'\blane: \[([^\]]+)\]', config)
        self.assertEqual(len(listed), 1)
        lanes = [value.strip() for value in listed[0].split(',')]
        self.assertCountEqual(lanes, matrix.LANES)
        self.assertEqual(len(lanes), 6)
        self.assertEqual(len(set(matrix.LANES.values())), 6)
        self.assertEqual(set(matrix.AXES['neuron']) & set(matrix.AXES['blender']), {'baseline'})


if __name__ == '__main__':
    unittest.main()
