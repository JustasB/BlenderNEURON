"""Create benchmark cells in NEURON, then expose them through BlenderNEURON."""

import argparse
from collections import deque
import json
import math
import os
import sys
import time
import zlib

from neuron import h
from blenderneuron.commnode import xmlrpclib
from blenderneuron.nrn.neuronnode import NeuronNode
from blenderneuron.nrn.neuronsection import NeuronSection
from blenderneuron.utils import serialize


# The animation benchmark deliberately uses a small, standard current-clamp
# experiment rather than synthetic voltage values.  NEURON time is in ms and
# current is in nA.  Each amplitude is the smallest 0.01 nA increment that
# produced a soma action potential for the corresponding morphology size.
SIMULATION_TSTOP_MS = 25.0
RECORDING_PERIOD_MS = 1.0
STIMULUS_DELAY_MS = 5.0
STIMULUS_DURATION_MS = 10.0
AP_THRESHOLD_CURRENT_NA = {
    16: 0.63,
    128: 0.76,
    256: 0.77,
    384: 0.77,
    512: 0.77,
}
# The animation uses a visible single-spike drive rather than the first
# 0 mV-crossing current. It is intentionally above every calibrated
# threshold so the soma and propagating dendritic signal are legible.
ROBUST_AP_CURRENT_NA = 1.0


def instrument_segment_collection(profile):
    """Time production methods, without duplicating the collection algorithm.

    Installed only in the dedicated phase-profile server. Uninstrumented runs
    execute the untouched production methods. Counts and bytes are metrics,
    separated from durations by the benchmark client.
    """
    build = NeuronSection._build_segment_midpoints
    collect = NeuronSection.collect_segments_recursive

    def timed_build(section):
        start = time.perf_counter()
        result = build(section)
        profile["neuron_segment_geometry_cache_build"] = (
            profile.get("neuron_segment_geometry_cache_build", 0.0)
            + time.perf_counter() - start
        )
        midpoints = section._segment_midpoints
        for key, value in (
            ("segment_cache_builds", 1),
            ("segment_cache_midpoints_built", len(midpoints)),
            ("segment_cache_n3d_calls", 1),
            ("segment_cache_arc3d_calls", 2 * len(midpoints)),
            ("segment_cache_allocated_bytes", sys.getsizeof(midpoints)
             + sum(sys.getsizeof(x) for x in midpoints)),
        ):
            profile[key] = profile.get(key, 0) + value
        return result

    def timed_collect(section):
        start = time.perf_counter()
        result = collect(section)
        profile["neuron_segment_collection_total"] = (
            profile.get("neuron_segment_collection_total", 0.0)
            + time.perf_counter() - start
        )
        return result

    NeuronSection._build_segment_midpoints = timed_build
    NeuronSection.collect_segments_recursive = timed_collect


def stimulus_amplitude_for_sections(sections):
    """Return the robust, suprathreshold soma-clamp amplitude for animation."""
    # Static-import sweeps do not run a simulation, so a calibrated threshold
    # is not required there.  Keep the same robust drive for small exploratory
    # morphologies while only treating the listed large sizes as calibrated.
    return ROBUST_AP_CURRENT_NA


SECTION_NSEG = 5
SECTION_3D_POINTS = 3
SOMA_LENGTH_UM = 10.0
SOMA_DIAMETER_UM = 10.0
DENDRITE_LENGTH_UM = 100.0
DENDRITE_DIAMETER_UM = 2.0
BRANCH_HORIZONTAL_STEP_UM = 80.0
CELL_COLUMN_SPACING_UM = 450.0
CELL_ROW_SPACING_UM = 800.0


def binary_tree_parent_index(section_index):
    """Return the parent in a soma → trunk → binary-tree breadth-first layout."""
    if section_index == 0:
        return None
    if section_index == 1:
        return 0
    return 1 + (section_index - 2) // 2


def _branch_direction(side, branch_depth):
    """Return an upward child direction for a clearly legible binary tree.

    The first split has the widest horizontal separation. Each later level
    halves that step, so endpoints remain distinct while every dendrite is
    exactly 100 µm long and all branches point upward from the soma.
    """
    horizontal = side * BRANCH_HORIZONTAL_STEP_UM / (2 ** branch_depth)
    vertical = math.sqrt(DENDRITE_LENGTH_UM ** 2 - horizontal ** 2)
    return vertical / DENDRITE_LENGTH_UM, 0.0, horizontal / DENDRITE_LENGTH_UM


def _set_three_point_geometry(section, start, direction, diameter, length):
    """Give a section three collinear 3D points over its requested length."""
    h.pt3dclear(sec=section)
    for fraction in (0.0, 0.5, 1.0):
        point = tuple(
            start[axis] + fraction * length * direction[axis]
            for axis in range(3)
        )
        h.pt3dadd(*point, diameter, sec=section)
    return tuple(start[axis] + length * direction[axis] for axis in range(3))


def _add_passive_and_hh(section):
    """Use a stable -65 mV passive rest alongside the HH membrane model."""
    section.insert("pas")
    # NEURON's default e_pas is 0 mV.  Leaving it there makes this otherwise
    # quiescent morphology depolarize and fire before the intended clamp.
    section.e_pas = -65.0
    section.insert("hh")


def cell_origin(cell_index, cell_count):
    """Place multi-cell scenes in a compact, camera-readable grid.

    A long horizontal row makes each cell too short in a wide publication
    panel.  Two cells remain side by side; larger scenes use at most two rows
    so every soma-to-terminal tree stays legible in the same camera view.
    """
    columns = 2 if cell_count <= 2 else math.ceil(cell_count / 2)
    if os.environ.get("BLENDERNEURON_BENCH_LAYOUT") == "render_grid":
        # Preserve the approved 8/16-cell previews, then wrap larger scenes
        # rather than squeezing 64 columns into the publication camera.
        columns = min(columns, math.ceil(math.sqrt(
            cell_count * 2 * CELL_ROW_SPACING_UM / CELL_COLUMN_SPACING_UM)))
    rows = math.ceil(cell_count / columns)
    column = cell_index % columns
    row = cell_index // columns
    # Numerical round-trip controls vary spatial extent independently of cell
    # count. Default import/render benchmark layouts remain unchanged.
    x_extent = os.environ.get("BLENDERNEURON_BENCH_X_EXTENT_UM")
    column_spacing = (float(x_extent) / max(1, columns - 1)
                      if x_extent is not None else CELL_COLUMN_SPACING_UM)
    return (
        column * column_spacing,
        0.0,
        (row - (rows - 1) / 2) * CELL_ROW_SPACING_UM,
    )


def build_cells(cells, sections):
    """Build connected cells with passive and HH membrane dynamics.

    Every morphology section receives ``pas`` and ``hh`` so all imported
    voltage traces come from NEURON's mechanisms.  The current clamp is kept
    alive alongside the sections and is applied at the centre of each soma.
    """
    # Keep references alive for the lifetime of the NEURON server.
    built = []
    clamps = []
    if sections < 1:
        raise ValueError("A benchmark cell must contain at least its soma section")

    for cell in range(cells):
        soma = h.Section(name="Cell[%d].soma" % cell)
        soma.nseg = SECTION_NSEG
        _add_passive_and_hh(soma)
        # The entire tree lies in Blender's x/z image plane. A camera on the
        # y axis therefore sees the soma on the left and the branching tree
        # extending toward the right.
        soma_start = cell_origin(cell, cells)
        soma_direction = (1.0, 0.0, 0.0)
        soma_end = _set_three_point_geometry(
            soma, soma_start, soma_direction, SOMA_DIAMETER_UM, SOMA_LENGTH_UM
        )
        built.append(soma)
        clamp = h.IClamp(soma(0.5))
        clamp.delay = STIMULUS_DELAY_MS
        clamp.dur = STIMULUS_DURATION_MS
        clamp.amp = stimulus_amplitude_for_sections(sections)
        clamps.append(clamp)
        # The soma has one trunk child.  All subsequent queued sections split
        # into two children.  Queue order makes construction breadth-first and
        # stopping at the target count gives a predictable partial final level.
        trunk = None
        next_section_index = 1
        if next_section_index < sections:
            trunk = h.Section(name="Cell[%d].dend[0]" % cell)
            trunk.nseg = SECTION_NSEG
            _add_passive_and_hh(trunk)
            trunk.connect(soma(1.0), 0.0)
            trunk_end = _set_three_point_geometry(
                trunk, soma_end, soma_direction, DENDRITE_DIAMETER_UM, DENDRITE_LENGTH_UM
            )
            built.append(trunk)
            next_section_index += 1
        queue = deque([(trunk, trunk_end, 0)] if trunk is not None else [])
        while queue and next_section_index < sections:
            parent, parent_end, branch_depth = queue.popleft()
            for side in (-1, 1):
                if next_section_index >= sections:
                    break
                dend = h.Section(name="Cell[%d].dend[%d]" % (cell, next_section_index - 1))
                dend.nseg = SECTION_NSEG
                _add_passive_and_hh(dend)
                dend.connect(parent(1.0), 0.0)
                direction = _branch_direction(side, branch_depth)
                endpoint = _set_three_point_geometry(
                    dend, parent_end, direction, DENDRITE_DIAMETER_UM, DENDRITE_LENGTH_UM
                )
                built.append(dend)
                queue.append((dend, endpoint, branch_depth + 1))
                next_section_index += 1
    return built, clamps


class BenchmarkNeuronNode(NeuronNode):
    """NeuronNode with opt-in, benchmark-only phase timing."""

    def __init__(self):
        self.benchmark_profile = {}
        if os.environ.get("BLENDERNEURON_BENCH_PROFILE_PATH"):
            instrument_segment_collection(self.benchmark_profile)
        super().__init__()

    def _write_benchmark_profile(self):
        path = os.environ.get("BLENDERNEURON_BENCH_PROFILE_PATH")
        if not path:
            return
        temporary = path + ".tmp"
        with open(temporary, "w") as destination:
            json.dump(self.benchmark_profile, destination)
        os.replace(temporary, path)

    def initialize_groups(self, blender_groups, send_back=True):
        start = time.perf_counter()
        cprofile_path = os.environ.get("BLENDERNEURON_BENCH_CPROFILE_PATH")
        if cprofile_path is None:
            result = super().initialize_groups(blender_groups, send_back=send_back)
        else:
            import cProfile
            profiler = cProfile.Profile()
            profiler.enable()
            try:
                result = super().initialize_groups(blender_groups, send_back=send_back)
            finally:
                profiler.disable()
                profiler.dump_stats(cprofile_path)
        self.benchmark_profile["neuron_initialize_groups"] = time.perf_counter() - start
        self._write_benchmark_profile()
        return result

    def compress(self, obj):
        """Production-equivalent compression with separately timed stages."""
        start = time.perf_counter()
        serialized = serialize(obj)
        self.benchmark_profile["neuron_iterative_serialize"] = time.perf_counter() - start
        self.benchmark_profile["uncompressed_bytes"] = len(serialized.encode("utf-8"))

        start = time.perf_counter()
        compressed = zlib.compress(serialized.encode("utf-8"), 2)
        self.benchmark_profile["neuron_zlib_compress"] = time.perf_counter() - start
        return xmlrpclib.Binary(compressed)

    def get_group_dicts(self, compressed=True):
        profile = self.benchmark_profile
        start = time.perf_counter()
        if any(group.record_activity for group in self.groups.values()):
            h.run()
        profile["neuron_simulation_and_collection"] = time.perf_counter() - start

        start = time.perf_counter()
        result = [group.to_dict(
            include_activity=group.record_activity,
            include_root_children=True,
            include_coords_and_radii=True,
        ) for group in self.groups.values()]
        profile["neuron_group_serialization"] = time.perf_counter() - start

        if compressed:
            start = time.perf_counter()
            result = self.compress(result)
            profile["neuron_compression"] = time.perf_counter() - start
            profile["compressed_bytes"] = len(result.data)
        return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", type=int, default=int(os.environ["BLENDERNEURON_BENCH_CELLS"]))
    parser.add_argument("--sections", type=int, default=int(os.environ["BLENDERNEURON_BENCH_SECTIONS"]))
    # nrniv leaves its own ``-python -c`` arguments in sys.argv.
    args, _ = parser.parse_known_args()
    h.load_file("stdrun.hoc")
    h.tstop = SIMULATION_TSTOP_MS
    h.dt = 0.025
    # Start from the HH resting potential.  Without an explicit v_init, the
    # first integration step can create an initialization transient that looks
    # like a spike before the intended 5 ms current pulse.
    h.v_init = -65.0
    built, clamps = build_cells(args.cells, args.sections)
    # Deliberately create the live node only after morphology construction.
    # The subclass exposes timing through an additional benchmark-only RPC.
    node = BenchmarkNeuronNode()
    while built and clamps:
        time.sleep(1)


if __name__ == "__main__":
    main()
