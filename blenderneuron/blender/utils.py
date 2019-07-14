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
    debug = False

    def get_classes(module):
        '''
        Gets the list of module classes listed in the order of their declaration
        '''

        members = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            source, start_line = inspect.getsourcelines(obj)
            members.append([name, obj, start_line])

        def _line_order(value):
            return value[2]

        members.sort(key=_line_order)

        return members

    classes = [i[1] for i in get_classes(module)]

    for cls in classes:
        try:
            if unreg:
                bpy.utils.unregister_class(cls)
            else:
                bpy.utils.register_class(cls)

                if debug:
                    print('REGISTERED', cls)
        except:
            if debug:
                print('Could not register', cls)


def remove_prop_collection_item(collection, item):
    collection.remove(collection.find(item.name))