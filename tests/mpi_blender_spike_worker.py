"""Live rank-zero RPC endpoint for the Blender cross-rank animation test."""
import json
from pathlib import Path
import sys
import time

from neuron import h


def main(directory):
    h.load_file('stdrun.hoc')
    pc = h.ParallelContext()
    rank = int(pc.id())
    assert int(pc.nhost()) == 2
    soma = h.Section(name='Cell[%d].soma' % rank)
    soma.L = soma.diam = 20
    soma.insert('hh')
    for x in (0, 10, 20):
        h.pt3dadd(x, rank * 40, 0, 20, sec=soma)
    detector = h.NetCon(soma(0.5)._ref_v, None, sec=soma)
    detector.threshold = 0
    pc.set_gid2node(rank, rank)
    pc.cell(rank, detector)
    if rank == 0:
        stimulus = h.IClamp(soma(0.5))
        stimulus.delay, stimulus.dur, stimulus.amp = 5, 1, 0.3
    else:
        synapse = h.ExpSyn(soma(0.5))
        synapse.tau, synapse.e = 2, 0
        connection = pc.gid_connect(0, synapse)
        connection.delay, connection.weight[0] = 2, 0.05
    spikes = h.Vector()
    detector.record(spikes)
    pc.set_maxstep(1)
    pc.timeout(10)
    h.dt, h.tstop, h.v_init = 0.025, 25, -65

    # Use the normal production endpoint and coordinator, including RPC threads.
    from blenderneuron.neuronstart import BlenderNEURON as node
    node.init_mpi(pc)
    node.start_mpi_coordinator()
    directory = Path(directory)
    if rank == 0:
        (directory / 'ready').touch()
        deadline = time.monotonic() + 120
        while not (directory / 'stop').exists():
            if time.monotonic() > deadline:
                raise RuntimeError('Timed out waiting for Blender test completion')
            time.sleep(.05)
        node.stop_mpi_coordinator()
    (directory / ('rank-%d.json' % rank)).write_bytes(json.dumps(
        {'rank': rank, 'spikes_ms': list(spikes), 'time_ms': h.t,
         'server': getattr(node, 'server_address', None)}).encode('utf-8'))
    node.stop_server()
    pc.barrier()
    pc.gid_clear()
    pc.done()


if __name__ == '__main__':
    main(sys.argv[-1])
