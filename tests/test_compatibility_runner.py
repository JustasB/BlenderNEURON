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
        for path in ('test-compatibility.py', 'compatibility/__init__.py', 'compatibility/integration.py', 'compatibility/releases.py'):
            shutil.copy2(str(ROOT / 'scripts' / path), str(scripts / path))
        self.calls = self.root / 'docker-calls.jsonl'
        fake = self.root / 'docker'
        fake.write_text('#!' + sys.executable + '\n' + '''from __future__ import print_function
import json, os, sys, time
with open(os.environ['FAKE_DOCKER_CALLS'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'info':
    print(os.environ.get('FAKE_ARCH', 'x86_64'))
elif sys.argv[1] == 'run':
    print('individual test output', flush=True)
    time.sleep(float(os.environ.get('FAKE_SLEEP', '0')))
    if 'blenderneuron-integration:neuron8' in sys.argv:
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
        completed = self.run_runner('neuron8', 'blender4', FAKE_FAILURE='7')
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(self.read_result('neuron8')['exit_code'], 7)
        self.assertEqual(self.read_result('blender4')['exit_code'], 0)
        self.assertIn('individual test output', completed.stdout)
        self.assertIn('individual test output', (self.root / '.compatibility-results/neuron8/tests.log').read_text())
        runs = [call for call in self.read_calls() if call[0] == 'run']
        self.assertEqual(len(runs), 2)
        for call in runs:
            self.assertIn('/source/scripts/compatibility/integration_check.py', call)
            self.assertIn('BLENDERNEURON_TEST_KEEP_GOING=1', call)
            self.assertIn('OMPI_MCA_rmaps_base_oversubscribe=1', call)

    def test_suite_deadline_reports_timeout_and_removes_container(self):
        completed = self.run_runner('neuron8', '--timeout', '1', FAKE_SLEEP='60')
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = self.read_result('neuron8')
        self.assertEqual(result['exit_code'], 124)
        self.assertEqual(result['phase'], 'test')
        calls = self.read_calls()
        run = next(call for call in calls if call[0] == 'run')
        name = run[run.index('--name') + 1]
        self.assertIn(['rm', '-f', name], calls)

    def test_arm_host_does_not_silently_start_emulation(self):
        completed = self.run_runner('neuron8', FAKE_ARCH='aarch64')
        self.assertEqual(completed.returncode, 2)
        self.assertIn('native x86-64', completed.stderr)
        self.assertFalse(any(call[0] == 'run' for call in self.read_calls()))

    def test_latest_resolved_versions_reach_build_runtime_and_report(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        from compatibility import integration
        args = SimpleNamespace(results=self.root / 'reports', skip_build=False,
                               build_timeout=30, timeout=30, test_timeout=10)
        resolved = ('10.0.1', '3.15.2-slim-bookworm', '6.0.1')
        with patch.object(integration, 'resolve_latest', return_value=resolved), \
                patch.object(integration.subprocess, 'run') as docker, \
                patch.object(integration, 'run_tests', return_value=0) as tests:
            self.assertEqual(integration.run_lane('latest', args), 0)
        build = docker.call_args_list[0][0][0]
        self.assertIn('NEURON_VERSION=10.0.1', build)
        self.assertIn('BASE_IMAGE=python:3.15.2-slim-bookworm', build)
        self.assertIn('BLENDER_VERSION=6.0.1', build)
        command = tests.call_args[0][0]
        self.assertIn('EXPECTED_PYTHON=3.15.2', command)
        self.assertIn('EXPECTED_NEURON=10.0.1', command)
        self.assertIn('EXPECTED_BLENDER=6.0.1', command)
        result = json.loads((args.results / 'latest/result.json').read_text())
        self.assertEqual((result['neuron'], result['python'], result['blender']),
                         ('10.0.1', '3.15.2', '6.0.1'))

    def test_latest_resolution_failure_is_reported_without_running_tests(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        from compatibility import integration
        args = SimpleNamespace(results=self.root / 'reports')
        with patch.object(integration, 'resolve_latest', side_effect=ValueError('upstream unavailable')), \
                patch.object(integration.subprocess, 'run') as docker:
            self.assertEqual(integration.run_lane('latest', args), 1)
        result = json.loads((args.results / 'latest/result.json').read_text())
        self.assertEqual(result['phase'], 'resolve')
        self.assertIn('upstream unavailable', result['setup_error'])
        self.assertEqual(docker.call_count, 1)  # Cleanup only, no build/run.

    def test_ci_matrix_covers_shared_lane_definitions_once(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
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
        self.assertEqual(set(matrix.AXES['neuron']) & set(matrix.AXES['blender']), {'neuron8'})


class TestReleaseResolution(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            'releases', ROOT / 'scripts/compatibility/releases.py')
        self.releases = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.releases)

    def test_stable_wheels_and_newest_supported_python(self):
        def wheel(tag, yanked=False):
            return dict(filename='neuron-9.0.2-' + tag + '.whl', yanked=yanked)
        data = {'releases': {
            '9.0.2': [wheel('cp313-cp313-manylinux_2_17_x86_64'),
                      wheel('cp314-cp314-manylinux_2_27_x86_64.manylinux_2_28_x86_64'),
                      wheel('cp315-cp315-manylinux_2_27_aarch64'),
                      wheel('cp316-cp316-manylinux_2_27_x86_64', True)],
            '10.0.0rc1': [wheel('cp315-cp315-manylinux_2_27_x86_64')],
            '10.0.0': [wheel('cp315-cp315-manylinux_2_27_x86_64', True)]}}
        images = {minor: dict(version=minor + '.10', variants=['slim-bookworm'])
                  for minor in ('3.13', '3.14', '3.15', '3.16')}
        self.assertEqual(self.releases.resolve_neuron(data, images),
                         ('9.0.2', '3.14.10-slim-bookworm'))
        # A new release without usable wheels must fail, not test an older one.
        data['releases']['10.0.0'] = [dict(filename='neuron-10.0.0.tar.gz')]
        with self.assertRaises(ValueError):
            self.releases.resolve_neuron(data, images)

    def test_blender_skips_prereleases_and_sorts_numerically(self):
        pages = {
            self.releases.BLENDER: '<a href="Blender5.9/">x</a><a href="Blender5.10/">x</a><a href="Blender6.0/">x</a>',
            self.releases.BLENDER + 'Blender6.0/': '<a href="blender-6.0.0-beta-linux-x64.tar.xz">x</a>',
            self.releases.BLENDER + 'Blender5.10/': '<a href="blender-5.10.2-linux-x64.tar.xz">x</a><a href="blender-5.10.10-linux-x64.tar.xz">x</a>'}
        self.releases.fetch = pages.__getitem__
        self.assertEqual(self.releases.resolve_blender(), '5.10.10')


if __name__ == '__main__':
    unittest.main()
