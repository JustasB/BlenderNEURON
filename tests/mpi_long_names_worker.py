"""Long identical HOC names remain rank-aware through export and synapses."""
import json
import sys
from pathlib import Path
from collections import OrderedDict
from neuron import h
from blenderneuron.nrn.neuronnode import NeuronNode
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.neuronsection import NeuronSection

mode, directory = sys.argv[-2:]
pc = h.ParallelContext()
rank = int(pc.id())
name = 'GeneratedCell' + 'Hierarchy'*12
h('begintemplate %s\npublic soma\ncreate soma\nendtemplate %s' % (name, name))
cell = getattr(h, name)()
h.pt3dclear(sec=cell.soma)
h.pt3dadd(0, 0, 0, 2, sec=cell.soma)
h.pt3dadd(10, 0, 0, 2, sec=cell.soma)
group = NeuronRootGroup()
group.name = 'Long MPI'
root = NeuronSection()
root.from_nrn_section(cell.soma, group)
group.roots[root.name] = root
node = NeuronNode.__new__(NeuronNode)
node.groups = OrderedDict(((group.name, group),))
node.synapse_sets = {}
mpimap = None if mode == 'automatic' else {
    name + 'VisibleHierarchy'*24 + '[%d]' % r: {'name': name + '[0]', 'rank': r} for r in range(2)}
node.init_mpi(pc, mpimap)
group.node = node
if rank == 0:
    node.start_mpi_coordinator()
    groups = node.get_group_dicts(compressed=False)
    roots = groups[0]['roots']
    assert len(roots) == 2 and roots[0]['name'] != roots[1]['name']
    Path(directory, 'groups.json').write_text(json.dumps(groups))
    for root in roots:
        root['coords'] = [v + 7 for v in root['coords']]
    node.update_groups(groups)
    entry = json.loads(Path('tests/test_synset.json').read_text())['entries'][0]
    entry.update(source_section=roots[0]['name'], dest_section=roots[1]['name'],
                 source_seg_i=0, dest_seg_i=0, is_reciprocal=False, create_spine=False)
    node.create_synapses(dict(name='long_synapse', entries=[entry]))
    node.stop_mpi_coordinator()
else:
    node.start_mpi_coordinator()
assert h.x3d(0, sec=cell.soma) == 7
assert node.synapse_sets['long_synapse']
