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

    if rank == 0:
        node.start_mpi_coordinator()
        result = node.get_group_dicts(compressed=False)
        node.stop_mpi_coordinator()
    else:
        node.start_mpi_coordinator()
        result = None

    with open(os.path.join(output_dir, "rank-%d.json" % rank), "w") as destination:
        json.dump(result, destination)


if __name__ == "__main__":
    main(sys.argv[-1])
