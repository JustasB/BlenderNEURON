"""Run with Python, or: mpiexec -n 2 nrniv -mpi -python tutorials/offline_simulation.py

Writes simulation.bnresults in the working directory. Blender need not be running.
"""
from neuron import h
from blenderneuron.nrn.offline import SimulationExport

h.load_file('stdrun.hoc')
pc = h.ParallelContext()
rank = int(pc.id())

# Replace this model setup with your own local cells and network connections.
soma = h.Section(name='soma')
soma.L, soma.diam = 20, 20
soma.insert('hh')
h.pt3dclear(sec=soma)
h.pt3dadd(0, rank * 40, 0, 20, sec=soma)
h.pt3dadd(20, rank * 40, 0, 20, sec=soma)
stimulus = h.IClamp(soma(0.5))
stimulus.delay, stimulus.dur, stimulus.amp = 1, 2, 0.5

# Register the local spike source for ParallelContext's simulation solver.
pc.set_gid2node(rank, rank)
detector = h.NetCon(soma(0.5)._ref_v, None, sec=soma)
pc.cell(rank, detector)

# Configure after building cells, before initializing/running the simulation.
export = SimulationExport(parallel_context=pc)
export.add_group(
    'Network', roots=[soma],
    recording_granularity='Section', record_variable='v',
    recording_period=0.1,
    display={'default_color': [0.1, 0.3, 0.8, 1.0]},
)
export.prepare()  # All MPI ranks call this, including ranks with no local cells.

# Your simulation code owns initialization and execution.
pc.set_maxstep(10)
h.dt = 0.025
h.finitialize(-65)
pc.psolve(10)

# All ranks contribute; only rank 0 writes the combined file. No rerun occurs.
export.save('simulation.bnresults')
pc.done()
