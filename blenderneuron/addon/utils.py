import atexit
import inspect
import os
import time
import bpy
import shlex
import subprocess

def launch_neuron(command):
    command = shlex.split(command)
    globals()["BlenderNEURON_neuron"] = subprocess.Popen(command)

@atexit.register
def force_stop_neuron():
    try:
        # If at exit, there is still a Blender launched NEURON process, kill it
        globals()["BlenderNEURON_neuron"].terminate()

        # Reset terminal if needed
        os.system("tset")
    except:
        pass

def stop_neuron():
    if blender_launched_neuron_running():

        # First try to instruct NEURON to self-quit
        try:
            if bpy.types.Object.BlenderNEURON_node.client is not None:
                bpy.types.Object.BlenderNEURON_node.client.run_command("quit()")

        except:
            pass

        # Give it a sec to quit
        if globals()["BlenderNEURON_neuron"].poll() == None:
            time.sleep(1)

        # If not gone after a sec, terminate the process
        if globals()["BlenderNEURON_neuron"].poll() == None:
            globals()["BlenderNEURON_neuron"].terminate()

            # Forceful terminations don't reset terminal echo and newline modes
            # `tset` resets them without clearing terminal output
            try:
                os.system("tset")
            except:
                pass

        # Cleanup
        globals()["BlenderNEURON_neuron"] = None
        globals().pop("BlenderNEURON_neuron")

def blender_launched_neuron_running():
    return "BlenderNEURON_neuron" in globals() and \
           globals()["BlenderNEURON_neuron"] is not None

def register_module_classes(module, unreg=False):
    classes = [i[1] for i in inspect.getmembers(module, inspect.isclass)]

    for cls in classes:
        try:
            if unreg:
                bpy.utils.unregister_class(cls)
            else:
                bpy.utils.register_class(cls)
                # print('REGISTERED', cls)
        except:
            # print('Could not register', cls)
            pass

