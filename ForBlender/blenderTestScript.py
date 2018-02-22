#15 - 0.1 s
#32 - 0.3 s
#256 - 15s - splines wihout objs 11s - with handles at co locs - 0.4s!
#512 - 105s


import pickle, zlib

with open("R:\\test.txt","rb") as f:
   data = f.read()
   data = zlib.decompress(data)
   data = pickle.loads(data)

group = data

import sys, bpy
sys.path.append('C:\\Users\\Justas\\Miniconda3\\envs\\pb35\\lib\\site-packages')
import line_profiler
import os

os.chdir('E:\Code\BlenderNEURON\ForBlender')

import neuroserver
bpy.types.Object.neuron_server = neuroserver.NeuroServer()
bpy.types.Object.profiler = line_profiler.LineProfiler(bpy.types.Object.neuron_server.visualize_group)
bpy.types.Object.profiler.add_function(bpy.types.Object.neuron_server.create_curve_obj)
bpy.types.Object.profiler.add_function(bpy.types.Object.neuron_server.add_spline)

def thecall():
    bpy.types.Object.neuron_server.visualize_group(group)

bpy.types.Object.profiler.runcall(thecall)
bpy.types.Object.profiler.print_stats()

