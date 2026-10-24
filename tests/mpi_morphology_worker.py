"""Exercises automatic mapping for identical HOC cell names on two ranks."""

import json
import os
import sys
from collections import OrderedDict

from neuron import h

from blenderneuron.nrn.neuronnode import NeuronNode
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.neuronsection import NeuronSection


def main(output_dir):
    pc = h.ParallelContext()
    rank = int(pc.id())
    h.load_file("stdrun.hoc")
    h.load_file("tests/TestCell.hoc")
    cell = h.TestCell()  # Every rank deliberately creates TestCell[0].

    group = NeuronRootGroup()
    group.name = "Duplicate HOC cells"
    root = NeuronSection()
    root.from_nrn_section(cell.soma, group)
    group.roots[root.name] = root

    node = NeuronNode.__new__(NeuronNode)
    node.groups = OrderedDict(((group.name, group),))
    node.synapse_sets = {}
    node.init_mpi(pc)
    group.node = node

    original_soma = cell.soma
    original_nseg = cell.soma.nseg
    received = []
    apply = node._update_groups_local
    def capture(payload):
        received.append(payload)
        return apply(payload)
    node._update_groups_local = capture

    if rank == 0:
        node.start_mpi_coordinator()
        result = node.get_group_dicts(compressed=False)
        for exported in result[0]['roots']:
            exported['coords'] = [v + 10 for v in exported['coords']]
            exported['radii'] = [v * 2 for v in exported['radii']]
        node.update_groups(result)
        assert len(node.get_roots()) == 2
        broken = __import__('copy').deepcopy(result)
        broken[0]['roots'][1]['name'] = 'TestCell_rank1[0].missing'
        try:
            node.update_groups(broken)
        except RuntimeError as error:
            assert 'MPI rank 1 failed update_groups' in str(error), str(error)
            assert 'Traceback' in str(error)
        else:
            raise AssertionError('Remote update unexpectedly succeeded')
        assert len(node.get_roots()) == 2
        node.stop_mpi_coordinator()
    else:
        node.start_mpi_coordinator()
        result = None

    with open(os.path.join(output_dir, "rank-%d.json" % rank), "w") as destination:
        assert cell.soma == original_soma
        assert cell.soma.nseg == original_nseg
        own = received[0][0]['roots']
        assert len(own) == 1
        assert own[0]['name'] == 'TestCell_rank%d[0].soma' % rank
        assert abs(h.x3d(0, sec=cell.soma) - own[0]['coords'][0]) < 1e-5
        assert abs(h.diam3d(0, sec=cell.soma) - 2 * own[0]['radii'][0]) < 1e-5
        json.dump(received[0], destination)


if __name__ == "__main__":
    main(sys.argv[-1])
