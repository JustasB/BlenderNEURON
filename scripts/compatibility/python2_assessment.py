"""Run the full suite under Python 2 with the shared test isolation runner.

The supervisor uses Python 3 only for deadlines, process cleanup and reporting.
Every test process, its NEURON import and nrniv use Python 2. Blender retains
its bundled Python 3. A failing assessment exits nonzero, like any other lane.
"""
import ctypes
import configparser
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
from scripts.compatibility.integration import run_tests

spec = importlib.util.spec_from_file_location('process_utils', 'tests/process_utils.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)
if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'Could not enable child subreaper')

report = {'syntax_errors': [], 'suite_python': '2.7.18'}
# coverage 5.5 is the final Python 2 release. Preserve all measurement settings
# and the threshold; only its unsupported SIGTERM-saving option is omitted.
coverage_config = '.coveragerc-python2'
config = configparser.ConfigParser()
config.read('.coveragerc')
config.remove_option('run', 'sigterm')
with open(coverage_config, 'w') as stream:
    config.write(stream)
os.environ['COVERAGE_PROCESS_START'] = coverage_config
report['native_smoke_exit_code'] = subprocess.call(['python', 'scripts/compatibility/check.py'])
sources = [str(path) for path in Path('blenderneuron').rglob('*.py')
           if 'blender' not in path.parts[1:]]
syntax_probe = '''import json, sys
errors = []
for path in json.load(sys.stdin):
    try:
        compile(open(path).read(), path, 'exec')
    except SyntaxError as error:
        errors.append(dict(path=path, line=error.lineno, message=str(error)))
print(json.dumps(errors))
'''
report['syntax_errors'] = json.loads(subprocess.check_output(
    ['python', '-c', syntax_probe], input=json.dumps(sources).encode('utf-8')))
import_probe = '''import json
results = []
for name in ('connection', 'commnode', 'utils', 'activity', 'rootgroup', 'section',
             'nrn.recording', 'nrn.neuronrootgroup', 'nrn.neuronnode', 'nrn.offline'):
    try:
        __import__('blenderneuron.' + name)
        results.append(dict(module=name, outcome='pass'))
    except Exception as error:
        results.append(dict(module=name, outcome='blocked', error=type(error).__name__ + ': ' + str(error)))
print(json.dumps(results))
'''
report['component_imports'] = json.loads(subprocess.check_output(
    ['python', '-c', import_probe]).decode('utf-8').splitlines()[-1])
def finish_test(process):
    cleanup.stop_process_group(process)
    cleanup.reap_descendants()


# Use the same per-test isolation and watchdog as the Python 3 lanes.
# Sharing one interpreter across a module retains NEURON and RPC state.
try:
    suite_status = run_tests(['python', 'test_with_coverage.py'],
                             Path('/reports/python2-suite.log'), 600,
                             cleanup=finish_test)
except subprocess.TimeoutExpired:
    suite_status = 124
report['suite_exit_code'] = suite_status
Path('python2-assessment.json').write_text(json.dumps(report, indent=2) + '\n')
# Analyze the mixed Python 2/Blender-Python data with the modern reporter, which
# can parse all current sources. Test execution above remains entirely Python 2.
reporter = next(str(path) for path in Path('/blender').glob('*/python/bin/python3.*')
                if re.search(r'/python3\.\d+$', str(path)))
combined = subprocess.call([reporter, '-m', 'coverage', 'combine', '--rcfile=.coveragerc'])
coverage_status = subprocess.call([reporter, '-m', 'coverage', 'report', '--rcfile=.coveragerc', '--fail-under=91'])
subprocess.call([reporter, '-m', 'coverage', 'xml', '--rcfile=.coveragerc'])
subprocess.call([reporter, '-m', 'coverage', 'html', '--rcfile=.coveragerc'])
report['coverage_exit_code'] = coverage_status
Path('python2-assessment.json').write_text(json.dumps(report, indent=2) + '\n')
print('Python 2 full-suite exit code:', suite_status, flush=True)
raise SystemExit(bool(suite_status or report['syntax_errors']
                      or report['native_smoke_exit_code'] or combined or coverage_status))
