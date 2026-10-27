"""Container entry point: own both runtimes and bound the complete example."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return value


def show_progress(log):
    """Forward the tutorial's messages, leaving Blender's detailed output in its log."""
    found_message = False
    while True:
        line = log.readline()
        if not line:
            return found_message
        if line.startswith('[example] '):
            print(line.rstrip(), flush=True)
            found_message = True


def main():
    # These affect the rendered output, not the biophysics in model.py.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='/output',
                        help='results directory; Docker mounts the default /output')
    parser.add_argument('--width', type=positive, default=320)
    parser.add_argument('--height', type=positive, default=240)
    parser.add_argument('--frames', type=positive, default=60)
    parser.add_argument('--samples', type=positive, default=4)
    parser.add_argument('--fps', type=positive, default=20)
    parser.add_argument('--timeout', type=positive, default=600,
                        help='whole example deadline in seconds')
    args = parser.parse_args()
    if args.frames < 2:
        parser.error('--frames must be at least 2')
    if args.width % 2 or args.height % 2:
        parser.error('--width and --height must be even for H.264 video')
    # Docker maps /output to the host. CI can choose a writable workspace
    # directory instead. Each run gets its own folder to preserve old results.
    output_root = Path(args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = datetime.now().strftime('run-%Y%m%d-%H%M%S-')
    output = Path(tempfile.mkdtemp(prefix=prefix, dir=str(output_root)))
    os.environ['BLENDERNEURON_OUTPUT_DIR'] = str(output)
    (output / 'settings.json').write_text(json.dumps(vars(args), indent=2))
    print('Results: %s' % output, flush=True)
    print('Rendering %d frames at %d x %d, %d samples, %d FPS.' %
          (args.frames, args.width, args.height, args.samples, args.fps), flush=True)
    print('Starting NEURON and building three cells...', flush=True)
    # Each invocation pairs only its own processes, including in a reused container.
    with tempfile.TemporaryDirectory(prefix='bn-example-') as config:
        os.environ['BLENDERNEURON_CONFIG_DIR'] = config
        os.environ.pop('DISPLAY', None)
        os.environ.pop('COVERAGE_PROCESS_START', None)
        directory = Path(__file__).resolve().parent
        ready = Path(config) / 'model-ready'
        if ready.exists():
            ready.unlink()
        # Keep handles to both direct children, even if startup fails partway.
        # Docker --init handles orphan reaping when the container shuts down.
        processes = []
        deadline = time.monotonic() + args.timeout
        try:
            with (output / 'neuron.log').open('w') as nrn_log, \
                    (output / 'blender.log').open('w') as blender_log, \
                    (output / 'blender.log').open('r') as progress_log:
                model = subprocess.Popen([sys.executable, '-u', str(directory / 'model.py')],
                                         stdout=nrn_log, stderr=subprocess.STDOUT)
                processes.append(model)
                # Start Blender only after NEURON has published its endpoint.
                # A failed model should fail promptly instead of hanging here.
                startup = min(deadline, time.monotonic() + 60)
                next_update = time.monotonic() + 15
                while not ready.exists():
                    if model.poll() is not None:
                        raise RuntimeError('NEURON failed; see neuron.log')
                    if time.monotonic() > startup:
                        raise TimeoutError('NEURON startup deadline exceeded')
                    if time.monotonic() >= next_update:
                        print('Waiting for NEURON startup; details in neuron.log...', flush=True)
                        next_update = time.monotonic() + 15
                    time.sleep(0.1)
                # Blender has a separate Python runtime. The mounted render.py
                # imports cells through the live API and writes numbered PNGs.
                print('NEURON is ready. Starting background Blender...', flush=True)
                blender = subprocess.Popen([
                    'blender', '--background', '--factory-startup', '--python-exit-code', '1',
                    '--python', str(directory / 'render.py')],
                    stdout=blender_log, stderr=subprocess.STDOUT)
                processes.append(blender)
                # Read only our tagged messages from the log. This keeps the
                # terminal useful while preserving the full Blender diagnostics.
                next_update = time.monotonic() + 15
                while blender.poll() is None:
                    if show_progress(progress_log):
                        next_update = time.monotonic() + 15
                    if time.monotonic() >= next_update:
                        elapsed = args.timeout - (deadline - time.monotonic())
                        print('Still working (%ds elapsed); details in blender.log...' % elapsed,
                              flush=True)
                        next_update = time.monotonic() + 15
                    if model.poll() is not None:
                        raise RuntimeError('NEURON exited during transfer; see neuron.log')
                    if time.monotonic() > deadline:
                        raise TimeoutError('Example deadline exceeded; see blender.log')
                    time.sleep(0.2)
                # A quick run can finish between polls; forward its final messages too.
                show_progress(progress_log)
                if blender.returncode:
                    raise RuntimeError('Blender failed; see blender.log')
        finally:
            # Stop NEURON on success as well as on errors and interruptions.
            # Give each child a short graceful exit before forcing termination.
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    print('Done: preview.png, activity.mp4, scene.blend and recorded activity saved in %s' %
          output, flush=True)


if __name__ == '__main__':
    main()
