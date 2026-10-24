from blenderneuron.nrn.neuronnode import NeuronNode
from neuron import h

_parallel_ctx = h.ParallelContext()
_is_mpi_worker = int(_parallel_ctx.nhost()) > 1 and int(_parallel_ctx.id()) != 0

# Blender talks only to rank zero.  Other ranks retain a fully functional
# NeuronNode for coordinator requests without competing for the NEURON XML-RPC
# address file or opening an unnecessary server socket.
BlenderNEURON = globals()["BlenderNEURON"] = NeuronNode(
    server_end="Package" if _is_mpi_worker else None)

if not _is_mpi_worker:
    print(f'BlenderNEURON running in NEURON and accessible by Blender with BlenderNEURON addon at: {BlenderNEURON.server_address}')
    if int(_parallel_ctx.nhost()) > 1:
        print('BlenderNEURON MPI rank 0 of %d: this is the only Blender-facing rank. '
              'After model setup, call init_mpi(...) and start_mpi_coordinator() on every rank.' %
              int(_parallel_ctx.nhost()))
else:
    print('BlenderNEURON MPI worker rank %d of %d loaded. It will serve rank 0 after '
          'start_mpi_coordinator() is called on every rank.' %
          (int(_parallel_ctx.id()), int(_parallel_ctx.nhost())))
