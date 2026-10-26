"""Run each full suite in a private checkout so parallel lanes cannot collide."""
import os
import configparser
import shutil
import subprocess
import time
import platform

if platform.machine() != os.environ["EXPECTED_ARCH"]:
    raise RuntimeError("Unexpected container architecture: " + platform.machine())

os.rmdir('/BlenderNEURON')
shutil.copytree('/source', '/BlenderNEURON',
                ignore=shutil.ignore_patterns('.git', '.compatibility-results', 'htmlcov', 'coverage.xml',
                                             '.coverage', '.coverage.*', '__pycache__', 'blender_scripts'))
os.chdir('/BlenderNEURON')
if not os.path.isfile('.coveragerc'):
    raise RuntimeError('Full-suite coverage configuration was not copied')
# Blender 2.93 intentionally uses native cylindrical somas. Measure its
# supported backend at the same threshold; sphere-only code is tested on 4/5.
if int(os.environ['EXPECTED_BLENDER'].split('.')[0]) < 4:
    config = configparser.ConfigParser()
    config.read('.coveragerc')
    omitted = config.get('run', 'omit', fallback='')
    config.set('run', 'omit', omitted + '\nblenderneuron/blender/somadisplay.py')
    with open('.coveragerc', 'w') as stream:
        config.write(stream)
os.makedirs('/tmp/blender-scripts/addons', exist_ok=True)
os.symlink('/BlenderNEURON/blenderneuron', '/tmp/blender-scripts/addons/blenderneuron')
# Preserve the release's own startup scripts and bundled add-ons (e.g. Cycles).
# Older Blender interprets SYSTEM_SCRIPTS as a replacement, not an extra path.
os.environ.pop('BLENDER_SYSTEM_SCRIPTS', None)
os.environ['BLENDER_USER_SCRIPTS'] = '/tmp/blender-scripts'
# Use software OpenGL consistently; Blender 5 also offers a Vulkan backend.
# Keep this choice in the test environment, without changing the add-on.
if int(os.environ['EXPECTED_BLENDER'].split('.')[0]) >= 5:
    os.makedirs('/tmp/blender-bin', exist_ok=True)
    with open('/tmp/blender-bin/blender', 'w') as stream:
        stream.write('#!/bin/sh\nexec /blender/blender --gpu-backend opengl "$@"\n')
    os.chmod('/tmp/blender-bin/blender', 0o755)
    os.environ['PATH'] = '/tmp/blender-bin:' + os.environ['PATH']
display = subprocess.Popen(['Xvfb', ':0', '-screen', '0', '1280x760x24', '-nolisten', 'tcp'])
window_manager = None
try:
    deadline = time.monotonic() + 15
    while not os.path.exists('/tmp/.X11-unix/X0'):
        if display.poll() is not None or time.monotonic() > deadline:
            raise RuntimeError('Xvfb did not start')
        time.sleep(.1)
    window_manager = subprocess.Popen(['openbox', '--sm-disable'],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call(['python', '-c',
        'import os, sys; from neuron import h; print(sys.version); print(h.nrnversion()); '
        'assert os.environ["EXPECTED_NEURON"] in h.nrnversion(); '
        'expected = tuple(map(int, os.environ["EXPECTED_PYTHON"].split("."))); '
        'assert sys.version_info[:len(expected)] == expected'])
    blender_version = subprocess.check_output(['blender', '--version']).decode('utf-8')
    print(blender_version, flush=True)
    if blender_version.splitlines()[0].split()[:2] != ['Blender', os.environ['EXPECTED_BLENDER']]:
        raise RuntimeError('Cached image has an unexpected Blender version')
    preferences = ('import bpy; view = bpy.context.preferences.view; view.show_splash = False; '
                   'setattr(view, "use_save_prompt", False) if hasattr(view, "use_save_prompt") else None')
    addon_status = subprocess.call(['blender', '--background', '--python-exit-code', '1',
                                    '--python-expr', preferences,
                                    '--python', 'scripts/enable_addon.py'])
    if addon_status:
        print('Add-on preflight failed; continuing with the full suite for assessment.', flush=True)
    is_python2 = subprocess.call(['python', '-c',
                                 'import sys; sys.exit(sys.version_info[0] != 2)']) == 0
    if is_python2:
        status = subprocess.call(['python3', 'scripts/compatibility/python2_assessment.py'])
    else:
        status = subprocess.call(['sh', 'test.sh'])
    status = status or addon_status
finally:
    for name in ('coverage.xml', 'htmlcov', 'python2-assessment.json'):
        if os.path.isdir(name):
            shutil.rmtree('/reports/' + name, ignore_errors=True)
            shutil.copytree(name, '/reports/' + name)
        elif os.path.isfile(name):
            shutil.copy2(name, '/reports/' + name)
    if window_manager is not None:
        window_manager.terminate()
        window_manager.wait(timeout=10)
    display.terminate()
    display.wait(timeout=10)
raise SystemExit(status)
