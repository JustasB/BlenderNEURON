"""Attempt every test module under Python 2; distinguish blocked collection.

The supervisor uses Python 3 only for deadlines, process cleanup and reporting.
Every test process, its NEURON import and nrniv use Python 2. Blender retains
its bundled Python 3. A failing assessment exits nonzero, like any other lane.
"""
import ast
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

report = {'modules': [], 'syntax_errors': [], 'suite_python': '2.7.18'}
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


for path in sorted(Path('tests').glob('test_*.py')):
    tree = ast.parse(path.read_text(), filename=str(path))
    candidates = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name.startswith('test_') for node in ast.walk(tree))
    log = Path('/reports') / (path.stem + '.log')
    try:
        status = run_tests(['python', '-m', 'coverage', 'run', '--rcfile=' + coverage_config,
                            '--parallel-mode', '--branch', str(path)], log,
                           float(os.environ['BLENDERNEURON_TEST_TIMEOUT']), cleanup=finish_test)
    except subprocess.TimeoutExpired:
        status = 124
    output = log.read_text()
    ran = re.search(r'Ran (\d+) tests? in', output)
    blocked = not ran and bool(re.search(r'(ImportError|SyntaxError|ModuleNotFoundError):', output))
    result = dict(module=str(path), declared_test_methods=candidates,
                  tests_run=int(ran.group(1)) if ran else 0, exit_code=status,
                  outcome='pass' if status == 0 else 'blocked' if blocked else 'fail',
                  log=log.name)
    errors = re.findall(r'^(?:ImportError|SyntaxError|ModuleNotFoundError|AttributeError):.*',
                        output, flags=re.MULTILINE)
    result['error'] = errors[-1] if errors else None
    failed = re.search(r'FAILED \(([^\n]*)\)', output)
    counts = dict(re.findall(r'(failures|errors|skipped)=(\d+)', failed.group(1))) if failed else {}
    result['test_failures'] = int(counts.get('failures', 0))
    result['test_errors'] = int(counts.get('errors', 0))
    result['tests_skipped'] = int(counts.get('skipped', 0))
    report['modules'].append(result)
    print('{}: {} ({} declared methods, {} ran)'.format(
        path, result['outcome'], candidates, result['tests_run']), flush=True)
report['summary'] = {outcome: sum(item['outcome'] == outcome for item in report['modules'])
                     for outcome in ('pass', 'blocked', 'fail')}
report['declared_test_methods'] = sum(item['declared_test_methods'] for item in report['modules'])
report['tests_run'] = sum(item['tests_run'] for item in report['modules'])
report['test_failures'] = sum(item['test_failures'] for item in report['modules'])
report['test_errors'] = sum(item['test_errors'] for item in report['modules'])
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
print('Python 2 assessment:', report['summary'], flush=True)
raise SystemExit(bool(report['summary']['blocked'] or report['summary']['fail']
                      or report['native_smoke_exit_code'] or combined or coverage_status))
