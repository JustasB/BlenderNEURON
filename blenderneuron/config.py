
end_types = ["NEURON", "Blender"]           # The types of communication node types

default_ip = {
    "Blender": "127.0.0.1",                   # Default IP address of machine running Blender
    "NEURON":  "127.0.0.1"                    # Default IP address of machine running NEURON
}

imports = {                                   # modules to import before executing a command
    "Blender": "import bpy, mathutils",
    "NEURON": "from neuron import h"
}