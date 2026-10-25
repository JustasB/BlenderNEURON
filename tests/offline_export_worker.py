"""Real NEURON/MPI producer; exits before Blender imports the saved results."""
import json
import os
import sys

from neuron import h
from blenderneuron.nrn.offline import SimulationExport
from blenderneuron.results import read_snapshot


def main(path, mode):
    h.load_file('stdrun.hoc')
    pc = h.ParallelContext()
    rank = int(pc.id())
    if mode != 'empty' or rank == 0:
        root = h.Section(name='Cell[0].soma')
        dend = h.Section(name='Cell[0].dend')
        dend.connect(root(1))
        for sec in (root, dend):
            sec.L, sec.diam, sec.nseg = 20, 2, 3
            sec.insert('pas')
            h.pt3dclear(sec=sec)
            for x in (0, 10, 20):
                h.pt3dadd(x, rank * 30, 0, 2, sec=sec)
        pc.set_gid2node(rank, rank)
        detector = h.NetCon(root(0.5)._ref_v, None, sec=root)
        pc.cell(rank, detector)
        stimulus = h.IClamp(root(0.5))
        stimulus.delay, stimulus.dur, stimulus.amp = 0, 1, 0.05 * (rank + 1)
    else:
        root = None
    morphology_only = mode.startswith('morphology-')
    requested_level = mode.split('-', 1)[1] if morphology_only else mode
    export = SimulationExport(pc)
    for level in ('Cell', 'Section', '3D Segment'):
        # Each cell belongs to one group, matching live group membership.
        # Independent exports exercise all recording granularities.
        if level != requested_level and requested_level in ('Cell', 'Section', '3D Segment'):
            continue
        if requested_level not in ('Cell', 'Section', '3D Segment') and level != 'Cell':
            continue
        variable = 'missing_variable' if mode == 'missing' and rank == int(pc.nhost()) - 1 else 'v'
        export.add_group('Network', [] if root is None else [root], recording_granularity=level,
                         record_variable=variable,
                         recording_period=0.1 if mode != 'settings' or rank == 0 else 0.2,
                         recording_time_start=0.1, recording_time_end=0.8,
                         display={'default_color': [0.1, 0.2, 0.8, 1.0],
                                  'simplification_epsilon': 0.0})
    if mode == 'empty':
        export = SimulationExport(pc)
        if rank == 0:
            export.add_group('Network', [root])
    if mode in ('groups', 'mixed'):
        extra = h.Section(name='Extra.soma')
        extra.L, extra.diam = 10, 2
        extra.insert('pas')
        h.pt3dadd(0, 100, 0, 2, sec=extra)
        h.pt3dadd(10, 100, 0, 2, sec=extra)
        export.add_group('Rank%d cells' % rank, [extra], record_activity=mode != 'mixed')
    export.prepare()
    if not morphology_only:
        pc.set_maxstep(10)
        h.dt = 0.025
        h.finitialize(-65)
        pc.psolve(1.0 if mode != 'times' or rank == 0 else 0.5)
    before = h.t
    export.save(path + '/missing' if mode == 'write' else path)
    assert h.t == before, 'Saving reran or advanced the simulation'
    export.save(path)  # Saving twice must be safe and preserve traces.
    if rank == 0:
        data = read_snapshot(path)
        assert len(data['groups'][0]['roots']) == (1 if mode == 'empty' else int(pc.nhost()))
        assert not os.path.exists(os.path.join(os.environ['BLENDERNEURON_CONFIG_DIR'], 'local-secret'))
        print(json.dumps({'time': h.t, 'roots': len(data['groups'][0]['roots'])}))
    pc.barrier()
    pc.done()


if __name__ == '__main__':
    main(sys.argv[-2], sys.argv[-1])
