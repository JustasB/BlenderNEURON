"""Compare targeted and broadcast creation in separate three-rank processes."""
import copy
import json
import sys
from pathlib import Path
from neuron import h
from blenderneuron.nrn.neuronnode import NeuronNode

pc = h.ParallelContext()
rank = int(pc.id())
h.load_file('stdrun.hoc')
h.load_file('tests/TestCell.hoc')
cell = h.TestCell()
node = NeuronNode.__new__(NeuronNode)
node.synapse_sets = {}
node.init_mpi(pc)
node.update_section_index()
mode, directory = sys.argv[-2:]
base = json.loads(Path('tests/test_synset.json').read_text())['entries'][0]
entries = []
for i, (source, dest, reciprocal, spine) in enumerate([
        (0, 0, False, False), (0, 1, False, False), (1, 0, True, True)]):
    entry = dict(base, source_section='TestCell_rank%d[0].dendrites[%d]' % (source, i),
                 dest_section='TestCell_rank%d[0].dendrites[%d]' % (dest, i + 3),
                 is_reciprocal=reciprocal, create_spine=spine)
    entries.append(entry)
payload = dict(name='partition_test', entries=entries)
received = []
apply = node._create_synapses_local

def capture(value):
    if mode == 'targeted' and not received:
        assert not node.synapse_sets
        assert len(list(h.allsec())) == len(node.section_index)
    received.append(copy.deepcopy(value))
    return apply(value)
node._create_synapses_local = capture
if rank == 0:
    node.start_mpi_coordinator()
    if mode == 'targeted':
        # Missing remote section must fail before any set or GID is created.
        bad = copy.deepcopy(payload)
        bad['entries'][2]['dest_section'] = 'TestCell_rank1[0].missing'
        try:
            node.create_synapses(bad)
        except RuntimeError as error:
            assert 'entry 2' in str(error) and 'rank 1' in str(error)
        else:
            raise AssertionError('Missing section accepted')
        assert not node.synapse_sets
        node.create_synapses(payload)
    else:
        node._mpi_request('create_synapses', payload)
    node.stop_mpi_coordinator()
else:
    node.start_mpi_coordinator()

refs = node.synapse_sets['partition_test']
# Broadcast retains empty placeholders on unrelated ranks; targeted retains
# only actual endpoint entries. Compare every actual retained component.
components = []
for nc, syn, neck, head, back_nc, back_syn in refs:
    if all(v is None for v in (nc, syn, neck, head, back_nc, back_syn)):
        continue
    def netcon(n):
        return None if n is None else [n.delay, n.weight[0], n.threshold]
    def process(s):
        return None if s is None else [s.get_segment().sec.name(), s.tau, s.e]
    components.append([netcon(nc), process(syn),
                       None if neck is None else neck.name(),
                       None if head is None else head.name(),
                       netcon(back_nc), process(back_syn)])
gids = []
for entry in entries:
    for field, seg, spine in [('source_section', 'source_seg_i', entry['create_spine']),
                               ('dest_section', 'dest_seg_i', False)]:
        gid = node.segment_gid(entry[field], entry[seg], spine)
        gids.append(int(pc.gid_exists(gid)))
Path(directory, '%s-%d.json' % (mode, rank)).write_text(json.dumps(
    dict(components=components, gids=gids, received=received[0]['entries'])))

# Force a rank-local application failure, then verify the coordinator recovers.
original = node._create_synapses_local
def fail(value):
    if rank == 1:
        raise RuntimeError('intentional synapse failure')
    return original(dict(value, entries=[]))
node._create_synapses_local = fail
if rank == 0:
    node.start_mpi_coordinator()
    try:
        node.create_synapses(payload)
    except RuntimeError as error:
        assert 'MPI rank 1 failed create_synapses' in str(error)
        assert 'Traceback' in str(error)
    else:
        raise AssertionError('Expected remote failure')
    assert len(node.get_roots()) == 3
    node.stop_mpi_coordinator()
else:
    node.start_mpi_coordinator()
