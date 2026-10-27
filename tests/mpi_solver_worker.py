"""Two-rank spike-transfer experiment, independent of BlenderNEURON's runner.

Usage: mpiexec -n 2 nrniv -mpi -python tests/mpi_solver_worker.py MODE OUTPUT
MODE is hrun, psolve, or disconnected. OUTPUT receives traces and parameters.
"""
import json
import sys

from neuron import h


def main(mode, output):
    h.load_file('stdrun.hoc')
    pc = h.ParallelContext()
    rank = int(pc.id())
    if int(pc.nhost()) != 2:
        raise RuntimeError('Exactly two MPI ranks are required')
    soma = h.Section(name='soma')
    soma.L = soma.diam = 20
    soma.nseg = 1
    soma.insert('hh')
    detector = h.NetCon(soma(0.5)._ref_v, None, sec=soma)
    detector.threshold = 0
    pc.set_gid2node(rank, rank)
    pc.cell(rank, detector)

    stimulus = synapse = connection = None
    if rank == 0:
        stimulus = h.IClamp(soma(0.5))
        stimulus.delay, stimulus.dur, stimulus.amp = 5, 1, 0.3
    else:
        synapse = h.ExpSyn(soma(0.5))
        synapse.tau, synapse.e = 2, 0
        connection = pc.gid_connect(0, synapse)
        connection.delay = 2
        connection.weight[0] = 0 if mode == 'disconnected' else 0.05

    times = h.Vector().record(h._ref_t)
    voltage = h.Vector().record(soma(0.5)._ref_v)
    spikes = h.Vector()
    detector.record(spikes)
    synaptic_current = h.Vector().record(synapse._ref_i) if synapse is not None else None
    pc.set_maxstep(1)
    pc.timeout(10)
    h.dt, h.tstop, h.v_init = 0.025, 25, -65
    if mode == 'hrun':
        h.run()
    else:
        h.finitialize(h.v_init)
        pc.psolve(h.tstop)

    record = {'rank': rank, 'times_ms': list(times), 'voltage_mV': list(voltage),
              'spikes_ms': list(spikes),
              'synaptic_current_nA': list(synaptic_current) if synaptic_current is not None else []}
    records = pc.py_alltoall([record, None])
    if rank == 0:
        with open(output, 'w') as destination:
            json.dump({'mode': mode, 'neuron_version': h.nrnversion(),
                       'parameters': {'soma_length_um': 20, 'soma_diameter_um': 20,
                                      'mechanism': 'hh', 'nseg': 1,
                                      'iclamp_nA': 0.3, 'iclamp_delay_ms': 5,
                                      'iclamp_duration_ms': 1, 'synapse_tau_ms': 2,
                                      'synapse_reversal_mV': 0, 'synapse_delay_ms': 2,
                                      'synapse_weight_uS': 0 if mode == 'disconnected' else 0.05,
                                      'dt_ms': 0.025, 'tstop_ms': 25},
                       'ranks': records}, destination)
    pc.barrier()
    pc.gid_clear()
    pc.done()


if __name__ == '__main__':
    main(sys.argv[-2], sys.argv[-1])
