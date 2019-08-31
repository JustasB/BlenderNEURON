import atexit
import inspect
import os
import time
import bpy
import shlex
import subprocess
import bpy
import numpy as np

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


def get_operator_context_override(selected_object = None):
    override = {}

    try:
        for area in bpy.data.screens["Default"].areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override['area'] = area
                        override['region'] = region
                        raise StopIteration()

    except StopIteration:
        pass

    override["window"]        = bpy.context.window_manager.windows[0]
    override["scene"]         = bpy.data.scenes['Scene']
    override["screen"]        = bpy.data.screens["Default"]

    override["edit_object"] = None
    override["gpencil_data"] = None

    if selected_object:
        override["object"]        = selected_object
        override["active_object"] = selected_object
        override["edit_object"]   = selected_object

    return override


def create_many_copies(target_obj, count):
    """
    Efficiently creates a large number of copies of a target object. This saves on
    the overhead incurred from .new() or .copy() calls.

    :param target_obj: Mesh, Empty, or Curve (might work with other types)
    :param count: Number of copies to create
    :return: List of the object copies
    """
    # Create a particle system container
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object

    # Create a particle system within the container
    bpy.ops.object.particle_system_add()
    particle_sys = cube.particle_systems[0].settings

    # Set parameters so all particles show up at once
    particle_sys.frame_start = -1
    particle_sys.frame_end = 1

    particle_sys.count = count

    particle_sys.emit_from = 'VOLUME'

    # No random rotations
    particle_sys.use_rotations = True
    particle_sys.rotation_mode = 'NONE'

    # No physics
    particle_sys.physics_type = 'NO'

    # Duplicate the target object for each particle
    particle_sys.render_type = 'OBJECT'
    particle_sys.dupli_object = target_obj
    particle_sys.particle_size = 1.0
    particle_sys.use_rotation_dupli = True
    particle_sys.use_scale_dupli = True

    # Make sure we're at the correct frame
    bpy.context.scene.frame_set(1)

    # Efficiently set the location of the objects (here all to 0,0,0)
    # must be a flat array/list with all locations pre-set
    # Otherwise the locations will be random and can be set by
    # looping over objects (slower than foreach_set)
    # Rotations can be set in similar fashion
    locs = np.zeros(count*3)
    cube.particle_systems[0].particles.foreach_set("location", locs)

    bpy.ops.object.duplicates_make_real()

    # Cleanup
    bpy.data.meshes.remove(cube.data)
    bpy.data.objects.remove(cube)
    bpy.data.particles.remove(particle_sys)

    return bpy.context.selected_objects

def fast_get(coll, prop_name, sub_items_per_item=1):
    count = len(coll)
    result = np.empty(count*sub_items_per_item)
    coll.foreach_get(prop_name, result)
    if sub_items_per_item > 1:
        result.shape = (-1, sub_items_per_item)
    return result

# Line simplification algorithm using Numpy from:
# https://github.com/fhirschmann/rdp/issues/7

def line_dists(points, start, end):
    if np.all(start == end):
        return np.linalg.norm(points - start, axis=1)

    vec = end - start
    cross = np.cross(vec, start - points)
    return np.divide(abs(cross), np.linalg.norm(vec))


def rdp(M, epsilon=0):
    M = np.array(M)
    start, end = M[0], M[-1]
    dists = line_dists(M, start, end)

    index = np.argmax(dists)
    dmax = dists[index]

    if dmax > epsilon:
        result1 = rdp(M[:index + 1], epsilon)
        result2 = rdp(M[index:], epsilon)

        result = np.vstack((result1[:-1], result2))
    else:
        result = np.array([start, end])

    return result

# End line simplification


# From: https://stackoverflow.com/a/43553331
def make_safe_filename(s):
    def safe_char(c):
        if c.isalnum():
            return c
        else:
            return "_"

    return "".join(safe_char(c) for c in s).rstrip("_")