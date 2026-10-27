"""One lane definition shared by local commands and the parallel CI matrix."""
from __future__ import print_function
import argparse
import errno
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from .releases import resolve_latest

ROOT = Path(__file__).resolve().parents[2]
FIXED_BLENDER = '5.2.3'
FIXED_NEURON = '8.2.7'
# Python is the NEURON-side interpreter. Blender uses its bundled interpreter.
LANES = {
    'neuron8': (FIXED_NEURON, '3.13.18-slim-bookworm', FIXED_BLENDER),
    'python2': ('8.0.2', '2.7.18-buster', FIXED_BLENDER),
    'neuron7': ('7.8.2', '3.9.25-slim-bookworm', FIXED_BLENDER),
    'latest': None,
    'blender2': (FIXED_NEURON, '3.13.18-slim-bookworm', '2.93.18'),
    'blender4': (FIXED_NEURON, '3.13.18-slim-bookworm', '4.5.15'),
}
AXES = {'neuron': ('neuron8', 'python2', 'neuron7', 'latest'),
        'blender': ('neuron8', 'blender2', 'blender4')}


def run_tests(command, path, timeout, cleanup=None):
    """Keep full logs as artifacts while streaming individual results to CI."""
    with path.open('w') as log, path.open('r', errors='replace') as reader:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=cleanup is not None)
        deadline = time.monotonic() + timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                try:
                    status = process.wait(timeout=min(.2, remaining))
                except subprocess.TimeoutExpired:
                    status = None
                output = reader.read()
                if output:
                    sys.stdout.write(output)
                    sys.stdout.flush()
                if status is not None:
                    return status
        finally:
            if cleanup is not None:
                cleanup(process)
            elif process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            output = reader.read()
            if output:
                sys.stdout.write(output)
                sys.stdout.flush()


def run_lane(lane, args):
    directory = (args.results / lane).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    print('Logs and reports: ' + str(directory), flush=True)
    for name in ('coverage.xml', 'python2-assessment.json', 'result.json', 'tests.log'):
        try:
            (directory / name).unlink()
        except (OSError, IOError) as error:
            if error.errno != errno.ENOENT:
                raise
    shutil.rmtree(str(directory / 'htmlcov'), ignore_errors=True)
    image = 'blenderneuron-integration:' + lane
    container = 'blenderneuron-matrix-' + uuid.uuid4().hex[:12]
    status, error_message, phase = 1, None, 'resolve'
    neuron = python = blender = None
    started = time.monotonic()
    try:
        neuron, python_image, blender = resolve_latest() if lane == 'latest' else LANES[lane]
        python = python_image.split('-')[0]
        print('{}: NEURON {}, Python {}, Blender {} (linux/amd64, full suite)'.format(
            lane, neuron, python, blender), flush=True)
        phase = 'build'
        if not args.skip_build:
            print('{}: building cached dependency image (limit {}s)'.format(lane, args.build_timeout), flush=True)
            with (directory / 'build.log').open('w') as log:
                subprocess.run([
                    'docker', 'build', '--platform', 'linux/amd64', '-t', image,
                    '-f', str(ROOT / 'scripts/compatibility/Dockerfile.integration'),
                    '--build-arg', 'BASE_IMAGE=' + ('python2-modern' if python == '2.7.18' else 'python:' + python_image),
                    '--build-arg', 'NEURON_VERSION=' + neuron,
                    '--build-arg', 'BLENDER_VERSION=' + blender,
                    str(ROOT / 'scripts')], stdout=log, stderr=subprocess.STDOUT,
                    check=True, timeout=args.build_timeout)
        phase, started = 'test', time.monotonic()
        print('{}: starting tests (limit {}s)'.format(lane, args.timeout), flush=True)
        command = [
            'docker', 'run', '--rm', '--init', '--platform', 'linux/amd64',
            '--name', container, '-v', str(ROOT) + ':/source:ro',
            '-v', str(directory) + ':/reports', '-e', 'PYTHONUNBUFFERED=1',
            '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'OPENBLAS_NUM_THREADS=1',
            '-e', 'OMP_NUM_THREADS=2', '-e', 'OMPI_MCA_rmaps_base_oversubscribe=1', '-e', 'LIBGL_ALWAYS_SOFTWARE=1',
            '-e', 'LP_NUM_THREADS=1', '-e', 'LP_NATIVE_VECTOR_WIDTH=128',
            '-e', 'EXPECTED_ARCH=x86_64', '-e', 'EXPECTED_NEURON=' + neuron,
            '-e', 'EXPECTED_BLENDER=' + blender, '-e', 'EXPECTED_PYTHON=' + python,
            '-e', 'BLENDERNEURON_TEST_KEEP_GOING=1',
            '-e', 'BLENDERNEURON_TEST_TIMEOUT=' + str(args.test_timeout),
            image, '/usr/bin/python3', '/source/scripts/compatibility/integration_check.py']
        status = run_tests(command, directory / 'tests.log', args.timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        status = 124 if isinstance(error, subprocess.TimeoutExpired) else getattr(error, 'returncode', 1)
        error_message = str(error)
        print('{}: {}'.format(lane, error), flush=True)
    finally:
        subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30)
    result = dict(lane=lane, neuron=neuron, python=python, blender=blender,
                  exit_code=status, logs=str(directory), setup_error=error_message,
                  architecture='amd64', phase=phase,
                  elapsed_seconds=round(time.monotonic() - started, 1))
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('{}: {} - {}'.format(lane, 'PASS' if status == 0 else 'FAIL', directory), flush=True)
    return status


def main():
    parser = argparse.ArgumentParser(description='Full-suite compatibility lanes (parallel jobs in CI)')
    parser.add_argument('lanes', nargs='*',  help='Default: all lanes')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--timeout', type=int, default=600, help='Seconds per suite (default: 10 minutes)')
    parser.add_argument('--test-timeout', type=int, default=180)
    parser.add_argument('--build-timeout', type=int, default=1800)
    parser.add_argument('--results', type=Path, default=ROOT / '.compatibility-results')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    if set(args.lanes) - set(LANES):
        parser.error('Unknown lanes: ' + ', '.join(sorted(set(args.lanes) - set(LANES))))
    if min(args.timeout, args.test_timeout, args.build_timeout) <= 0:
        parser.error('Timeouts must be positive')
    selected = args.lanes or tuple(LANES)
    if args.list:
        for lane in selected:
            neuron, python, blender = resolve_latest() if lane == 'latest' else LANES[lane]
            print('{}: NEURON {}, Python {}, Blender {}'.format(lane, neuron, python.split('-')[0], blender))
        return 0
    architecture = subprocess.check_output(['docker', 'info', '--format', '{{.Architecture}}'], timeout=30).decode().strip()
    if architecture not in ('amd64', 'x86_64'):
        parser.error('Compatibility lanes require a native x86-64 Docker runner. Use CI.')
    # Local invocations share a lock. CI lanes have independent checked-out VMs.
    lock_path = ROOT / '.compatibility-results/matrix.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        statuses = [run_lane(lane, args) for lane in selected]
    return int(any(statuses))
