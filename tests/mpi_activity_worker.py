"""Two-rank NEURON activity-collection fixture, launched by ``test_mpi``."""

import json
import os
import sys
from copy import deepcopy

from neuron import h

from collections import OrderedDict

from blenderneuron.nrn.neuronnode import NeuronNode
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.neuronsection import NeuronSection


def skeletal_group():
    return {
        "name": "MPI group",
        "roots": [
            {"name": "Cell[0].soma", "children": []},
            {"name": "Cell[1].soma", "children": []},
        ],
        "import_synapses": False,
        "interaction_granularity": "Cell",
        "record_activity": False,
        "recording_granularity": "Cell",
        "record_variable": "v",
        "recording_period": 0.1,
        "recording_time_start": 0.0,
        "recording_time_end": 0.0,
    }


def synapse_set():
    return {
        "name": "MPI synapses",
        # This validates coordinator distribution without changing the model;
        # cross-rank NetCon behaviour has dedicated tests elsewhere.
        "entries": [],
    }


def main(output_dir):
    pc = h.ParallelContext()
    rank = int(pc.id())
    if int(pc.nhost()) != 2:
        raise RuntimeError("Expected exactly two MPI ranks")

    h.load_file("stdrun.hoc")
    section = h.Section(name="Cell[%d].soma" % rank)
    section.L = 20
    section.diam = 2
    h.pt3dclear(sec=section)
    h.pt3dadd(0, 0, 0, 2, sec=section)
    h.pt3dadd(10, 0, 0, 2, sec=section)
    h.pt3dadd(20, 0, 0, 2, sec=section)

    # Register one local cell per rank.  ParallelContext.psolve requires this
    # ownership information even though this fixture has no cross-rank synapse.
    pc.set_gid2node(rank, rank)
    spike_detector = h.NetCon(section(0.5)._ref_v, None, sec=section)
    pc.cell(rank, spike_detector)

    group = NeuronRootGroup()
    group.record_activity = True
    group.recording_granularity = "3D Segment"
    group.record_variable = "v"
    group.recording_period = 0.1
    group.recording_time_start = 0.0
    group.recording_time_end = 1.0
    root = NeuronSection()
    root.from_nrn_section(section, group)
    group.roots[root.name] = root
    group.create_collector()
    cache_builds = []
    build_midpoints = root._build_segment_midpoints

    def track_local_cache():
        assert root.nrn_section is section
        build_midpoints()
        cache_builds.append(root._segment_midpoints)

    root._build_segment_midpoints = track_local_cache

    # Use the production aggregation path with an automatically discovered
    # name-to-rank map, as an MPI user does for uniquely named local cells.
    node = NeuronNode.__new__(NeuronNode)
    node.groups = OrderedDict((("MPI activity", group),))
    node.synapse_sets = {}
    node.init_mpi(pc)
    group.node = node

    h.dt = 0.025
    h.tstop = 1.0
    pc.set_maxstep(10)
    if rank == 0:
        node.start_mpi_coordinator()
        merged_groups = node.get_group_dicts(compressed=False)
        # Each rank must clear traces and rebuild exactly once on the next run.
        assert node.get_group_dicts(compressed=False) == merged_groups

        roots = node.get_roots()
        node.set_sim_params({"tstop": 2.0, "dt": 0.05, "atol": 0.001,
                             "celsius": 33.0, "cvode": "0"})
        initialized_groups = node.decompress(node.initialize_groups([skeletal_group()]))
        updated_group = deepcopy(initialized_groups[0])
        for updated_root in updated_group["roots"]:
            updated_root["coords"][0] += 100.0
        node.update_groups([updated_group])
        node.create_synapses(synapse_set())
        node.stop_mpi_coordinator()
    else:
        node.start_mpi_coordinator()
        merged_groups = None
        roots = None
        initialized_groups = None
    assert cache_builds == [(0.25, 0.75), (0.25, 0.75)], cache_builds
    result = {
        "rank": rank,
        "groups": merged_groups,
        "roots": roots,
        "initialized_groups": initialized_groups,
        "tstop": h.tstop,
        "dt": h.dt,
        "celsius": h.celsius,
        "first_x": h.x3d(0, sec=section),
        "synapse_count": len(node.synapse_sets["MPI synapses"]),
    }
    with open(os.path.join(output_dir, "rank-%d.json" % rank), "w") as destination:
        json.dump(result, destination)


if __name__ == "__main__":
    # nrniv retains its own command-line flags in sys.argv.
    main(sys.argv[-1])
