"""Small, reproducible BlenderNEURON performance probes.

The quick profile is intentionally conservative.  It is for discovering the
shape of the scaling curves, not for reporting publication numbers.  Run it
inside the project's Docker image, where Blender is available::

    blender --background --python notebooks/performance/performance_eval.py -- --quick

The module is also importable by the figure measurement runners. Blender is
imported lazily so the notebook can load and plot already-recorded JSON on a
normal Python kernel.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
WORKFLOW_RESULTS = RESULTS_DIR / "workflow_results.json"
DEFAULT_RESULTS = WORKFLOW_RESULTS

# The reader-facing workflow figure begins beyond small fixed-cost effects and
# doubles through a detailed morphology.
WORKFLOW_SECTIONS = (128, 256, 384, 512)
WORKFLOW_CELLS = (2, 4, 8)
REPEATS = 3
_RENDER_WARMED = False

# Animation data come from the live NEURON process.  At the add-on default of
# At 10 Blender frames per ms and a 0.1 ms collector period, each sampled
# voltage lands on its own animation frame through the 25 ms simulation.
ANIMATION_START_MS = 0.0
ANIMATION_END_MS = 25.0
ANIMATION_PERIOD_MS = 0.1
ANIMATION_FRAMES_PER_MS = 10.0
ANIMATION_FPS = 24
ANIMATION_FOCUS_FRAME = 80
# A 6 x 3 inch wide figure panel at 300 dpi.  This is intentionally a
# publication-oriented render workload rather than a low-resolution preview:
# BlenderNEURON is being evaluated for making final scientific figures.
RENDER_WIDTH_PX = 1800
RENDER_HEIGHT_PX = 900
# Representative, uniformly distributed animation frames used for the render
# time distribution.  The full 250-frame sequence has one voltage sample per
# frame; timing every frame for every morphology/cell-count/granularity would
# turn an exploratory sweep into a multi-hour run without adding independent
# scene states.  Twelve samples include baseline and AP-propagation states.
RENDER_TIMING_FRAME_COUNT = 12


def _bpy():
    import bpy
    import mathutils

    return bpy, mathutils


def _now() -> float:
    return time.perf_counter()


def _rss_mib() -> float:
    """Return the current resident process footprint in MiB."""
    if sys.platform.startswith("linux"):
        # Unlike ru_maxrss, this is the current resident set and can therefore
        # be compared before and after a particular workflow.
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
    # macOS reports bytes.  This is a high-water mark there, so it remains an
    # advisory value for the exploratory pass.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


def _peak_rss_mib() -> float:
    """Return the process high-water resident footprint in MiB."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; macOS reports bytes.
    return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


@contextmanager
def profile_blender_import(phases):
    """Time the live import's Blender phases without changing its behavior."""
    from blenderneuron.blender.blendernode import BlenderNode
    from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
    from blenderneuron.blender.views.curvecontainer import CurveContainer
    from blenderneuron.blender.views.objectview import ObjectViewAbstract
    from blenderneuron.utils import deserialize
    import zlib

    originals = []

    def wrap(owner, name, phase):
        original = getattr(owner, name)
        originals.append((owner, name, original))

        def timed(*args, **kwargs):
            start = _now()
            try:
                return original(*args, **kwargs)
            finally:
                phases[phase] = phases.get(phase, 0.0) + _now() - start

        setattr(owner, name, timed)

    wrap(BlenderNode, "get_group_data_from_neuron", "blender_rpc_and_decode")

    # The benchmark server records the matching encode-side split.  Override
    # only this process's inherited method so the normal add-on transport and
    # its support for arbitrarily deep, iterative data stay unchanged.
    original_decompress = BlenderNode.decompress

    def timed_decompress(_self, compressed):
        start = _now()
        uncompressed = zlib.decompress(compressed.data).decode("utf-8")
        phases["blender_zlib_decompress"] = (
            phases.get("blender_zlib_decompress", 0.0) + _now() - start
        )
        start = _now()
        result = deserialize(uncompressed)
        phases["blender_iterative_deserialize"] = (
            phases.get("blender_iterative_deserialize", 0.0) + _now() - start
        )
        return result

    BlenderNode.decompress = timed_decompress
    wrap(BlenderRootGroup, "from_full_NEURON_group", "blender_group_hydration")
    wrap(BlenderRootGroup, "show", "blender_display_total")
    wrap(CurveContainer, "create_section_material", "blender_material_creation")
    wrap(CurveContainer, "add_spline", "blender_spline_creation")
    wrap(ObjectViewAbstract, "animate_activity", "blender_keyframe_creation")
    wrap(ObjectViewAbstract, "link_containers", "blender_link_containers")
    try:
        yield
    finally:
        BlenderNode.decompress = original_decompress
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def _record(records, benchmark, sections, cells, seconds, **extra):
    record = {
        "benchmark": benchmark,
        "sections": sections,
        "cells": cells,
        "points": sections * cells * 3,
        "seconds": seconds,
        "rss_mib": _rss_mib(),
    }
    record.update(extra)
    if "rss_before_mib" in record:
        record["rss_delta_mib"] = record["rss_mib"] - record["rss_before_mib"]
    if "rss_peak_before_mib" in record:
        record["rss_peak_mib"] = _peak_rss_mib()
        record["rss_peak_delta_mib"] = (
            record["rss_peak_mib"] - record["rss_peak_before_mib"]
        )
    records.append(record)


def synthetic_morphology(cells: int, sections: int):
    """Return a deterministic, lightly branched morphology dictionary.

    Each section has three points.  This deliberately controls topology and
    point count independently of NEURON's nseg discretisation.
    """
    roots = []

    def section(name, coords, radii, children):
        # This is the full section dictionary consumed by BlenderSection, so
        # the benchmark can exercise the add-on's ordinary view classes.
        activity = {"times": [0.0, 1.0], "values": [-85.0, 20.0]}
        return {
            "name": name,
            "nseg": 1,
            "point_count": len(radii),
            "coords": coords,
            "radii": radii,
            "parent_connection_loc": 1.0,
            "connection_end": 0.0,
            "activity": activity,
            "segment_activity": {str(index): activity for index in range(len(radii) - 1)},
            "children": children,
        }

    for cell in range(cells):
        children = []
        for sec in range(sections - 1):
            x = cell * 35.0 + sec * 1.2
            children.append(section(
                "Cell[%d].dend[%d]" % (cell, sec),
                [x, 0.0, 0.0, x + 0.5, 1.0, 0.2, x + 1.0, 2.0, 0.0],
                [0.5, 0.35, 0.2], [],
            ))
        roots.append(section(
            "Cell[%d].soma" % cell,
            [cell * 35.0, 0.0, 0.0, cell * 35.0, 1.0, 0.0, cell * 35.0, 2.0, 0.0],
            [1.0, 1.0, 1.0], children,
        ))
    return {"name": "benchmark", "roots": roots}


def neuron_export_morphology(cells: int, sections: int, recording="Cell", record_activity=False):
    """Build a morphology in NEURON and export it through BlenderNEURON's model classes.

    This is the workflow used by the reader-facing benchmark: NEURON owns the
    sections and pt3d geometry, then NeuronSection/NeuronRootGroup produce the
    same full group dictionary consumed by BlenderRootGroup.
    """
    from neuron import h
    from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
    from blenderneuron.nrn.neuronsection import NeuronSection

    group = NeuronRootGroup()
    group.name = "benchmark"
    group.record_activity = record_activity
    group.recording_granularity = recording
    group.record_variable = "v"
    group.recording_period = 1.0
    group.recording_time_start = 0.0
    group.recording_time_end = 1.0

    # Keep Python references until serialization has completed.  Each cell has
    # one soma and ``sections - 1`` dendrites connected directly to that soma.
    nrn_sections = []
    for cell in range(cells):
        soma = h.Section(name="Cell[%d].soma" % cell)
        soma.nseg = 1
        h.pt3dclear(sec=soma)
        for y in (0.0, 1.0, 2.0):
            h.pt3dadd(cell * 35.0, y, 0.0, 2.0, sec=soma)
        nrn_sections.append(soma)

        for sec in range(sections - 1):
            dend = h.Section(name="Cell[%d].dend[%d]" % (cell, sec))
            dend.nseg = 1
            dend.connect(soma(1.0), 0.0)
            x = cell * 35.0 + sec * 1.2
            h.pt3dclear(sec=dend)
            h.pt3dadd(x, 0.0, 0.0, 1.0, sec=dend)
            h.pt3dadd(x + 0.5, 1.0, 0.2, 0.7, sec=dend)
            h.pt3dadd(x + 1.0, 2.0, 0.0, 0.4, sec=dend)
            nrn_sections.append(dend)

        root = NeuronSection()
        root.from_nrn_section(soma, group)
        group.roots[root.name] = root

    if record_activity:
        # Exercise the add-on's own collector/export path with two sampled
        # simulation times.  Passive sections are sufficient for animation
        # setup; this benchmark measures data handling, not electrophysiology.
        h.load_file("stdrun.hoc")
        group.fih = h.FInitializeHandler(group.clear_activity)
        group.create_collector()
        old_tstop, old_dt = h.tstop, h.dt
        h.tstop, h.dt = 1.0, 1.0
        h.run()
        h.tstop, h.dt = old_tstop, old_dt

    return group.to_dict(
        include_activity=record_activity,
        include_root_children=True,
        include_coords_and_radii=True,
    )


def import_live_neuron_group(cells: int, sections: int, interaction: str,
                             recording: str, record_activity: bool, phases=None,
                             phase_metrics=None, cprofile_prefix=None, after_import=None):
    """Use the add-on's live NEURON-to-Blender import operator.

    The helper process builds ``h.Section`` objects before importing
    ``neuronstart``.  Blender then creates a normal ``BlenderNode`` and calls
    ``blenderneuron.import_groups``; all NeuronRootGroup/NeuronSection work is
    consequently performed by the existing add-on code over its RPC channel.
    """
    import bpy
    import blenderneuron
    from blenderneuron.blender.blendernode import BlenderNode
    from blenderneuron import connection

    address = connection.config_directory() / "BlenderNEURON-NEURON.address"
    address.unlink(missing_ok=True)
    server_env = os.environ.copy()
    server_env["BLENDERNEURON_BENCH_CELLS"] = str(cells)
    server_env["BLENDERNEURON_BENCH_SECTIONS"] = str(sections)
    profile_path = None
    if phases is not None:
        profile_path = Path(tempfile.gettempdir()) / "BlenderNEURON-NEURON-profile.json"
        profile_path.unlink(missing_ok=True)
        server_env["BLENDERNEURON_BENCH_PROFILE_PATH"] = str(profile_path)
    if cprofile_prefix is not None:
        cprofile_prefix = Path(cprofile_prefix).resolve()
        cprofile_prefix.parent.mkdir(parents=True, exist_ok=True)
        server_env["BLENDERNEURON_BENCH_CPROFILE_PATH"] = str(cprofile_prefix) + "_neuron.pstats"
    server_script = repr(str(HERE / "neuron_benchmark_server.py"))
    launch_start = _now()
    server = subprocess.Popen([
        "nrniv", "-python", "-c",
        "exec(compile(open(%s).read(), %s, 'exec'))" % (server_script, server_script),
    ], env=server_env)
    node = None
    try:
        deadline = _now() + 30.0
        while not address.exists():
            if server.poll() is not None:
                raise RuntimeError("NEURON benchmark server exited during startup")
            if _now() >= deadline:
                raise TimeoutError("NEURON benchmark server did not publish its address")
            time.sleep(0.05)
        if phases is not None:
            phases["neuron_server_startup"] = _now() - launch_start

        if not hasattr(bpy.context.scene, "BlenderNEURON"):
            blenderneuron.register()
        node = BlenderNode()
        bpy.types.Object.BlenderNEURON_node = node
        if node.client is None:
            node.try_setup_client()
        if node.client is None:
            raise RuntimeError("Blender node could not connect to the NEURON benchmark server")
        group = node.add_group(name="benchmark")
        # ``add_group`` selects the new live group.  Do not touch the UI
        # mirror here: its update callback sends a simulation-settings RPC,
        # which can race the import RPC for large animated scenes.
        group.interaction_granularity = interaction
        group.recording_granularity = recording
        group.record_activity = record_activity
        group.record_variable = "v"
        group.recording_period = ANIMATION_PERIOD_MS
        group.recording_time_start = ANIMATION_START_MS
        group.recording_time_end = ANIMATION_END_MS
        group.frames_per_ms = ANIMATION_FRAMES_PER_MS
        def run_import_operator():
            if phases is None:
                bpy.ops.blenderneuron.import_groups()
            else:
                with profile_blender_import(phases):
                    start = _now()
                    bpy.ops.blenderneuron.import_groups()
                    phases["blender_import_operator_total"] = _now() - start

        if cprofile_prefix is None:
            run_import_operator()
        else:
            import cProfile
            profiler = cProfile.Profile()
            profiler.enable()
            try:
                run_import_operator()
            finally:
                profiler.disable()
                profiler.dump_stats(str(cprofile_prefix) + "_blender.pstats")

        if phases is not None:
            remote_profile = json.loads(profile_path.read_text())
            compressed_bytes = remote_profile.pop("compressed_bytes", None)
            for key in list(remote_profile):
                if key.startswith("segment_cache_"):
                    value = remote_profile.pop(key)
                    if phase_metrics is not None:
                        phase_metrics[key] = value
            phases.update(remote_profile)
            if phase_metrics is not None and compressed_bytes is not None:
                phase_metrics["compressed_bytes"] = compressed_bytes
        if record_activity:
            scene = bpy.context.scene
            scene.frame_start = int(round(ANIMATION_START_MS * ANIMATION_FRAMES_PER_MS))
            scene.frame_end = int(round(ANIMATION_END_MS * ANIMATION_FRAMES_PER_MS))
            scene.render.fps = ANIMATION_FPS
        # Benchmark extensions that need a live round trip run before cleanup.
        if after_import is not None:
            after_import(group, node)
        return group
    finally:
        if node is not None:
            node.stop_server()
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=5)
        address.unlink(missing_ok=True)
        if profile_path is not None:
            profile_path.unlink(missing_ok=True)


def walk_sections(section):
    yield section
    for child in section["children"]:
        yield from walk_sections(child)


def all_sections(morphology):
    return [section for root in morphology["roots"] for section in walk_sections(root)]


def clear_scene():
    bpy, _ = _bpy()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.curves, bpy.data.materials, bpy.data.meshes):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def build_scene(morphology, interaction, recording, animate=True):
    """Use BlenderNEURON's own group and view classes to display morphology."""
    from blenderneuron.blender.blenderroot import BlenderSection
    from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
    import numpy as np

    group = BlenderRootGroup("benchmark", node=None)
    group.interaction_granularity = interaction
    group.recording_granularity = recording
    group.animate_brightness = animate
    group.animate_color = False
    for root_dict in morphology["roots"]:
        root = BlenderSection()
        root.from_full_NEURON_section_dict(root_dict)
        group.roots[root.name] = root

        stack = [root]
        while stack:
            section = stack.pop()
            section.activity.times = np.asarray(section.activity.times)
            section.activity.values = np.asarray(section.activity.values)
            for activity in section.segment_activity.values():
                activity.times = np.asarray(activity.times)
                activity.values = np.asarray(activity.values)
            stack.extend(section.children)
    group.show()
    return group


def benchmark_transport(records, morphology, sections, cells):
    # This is deliberately a local serialization proxy in the quick profile.
    # The final profile replaces it with separate live NEURON/Blender RPC timers.
    import zlib

    start = _now()
    payload = json.dumps(morphology, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(payload)
    json.loads(zlib.decompress(compressed).decode("utf-8"))
    _record(records, "morphology_transport_proxy", sections, cells, _now() - start,
            payload_mib=len(compressed) / (1024 * 1024))


def benchmark_scene(records, morphology, sections, cells):
    for interaction in ("Cell", "Section"):
        for recording in ("Cell", "Section", "3D Segment"):
            clear_scene()
            rss_before = _rss_mib()
            start = _now()
            build_scene(morphology, interaction, recording)
            _bpy()[0].context.view_layer.update()
            objects = len(_bpy()[0].context.scene.objects)
            splines = sum(len(obj.data.splines) for obj in _bpy()[0].context.scene.objects if obj.type == "CURVE")
            _record(records, "scene_construction", sections, cells, _now() - start,
                    interaction=interaction, recording=recording,
                    object_count=objects, spline_count=splines, rss_before_mib=rss_before)


def benchmark_export_readback(records, morphology, sections, cells):
    clear_scene()
    build_scene(morphology, "Cell", "3D Segment")
    bpy, _ = _bpy()
    start = _now()
    point_count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "CURVE":
            continue
        for spline in obj.data.splines:
            coords = [0.0] * (3 * len(spline.bezier_points))
            spline.bezier_points.foreach_get("co", coords)
            point_count += len(coords) // 3
    _record(records, "curve_readback", sections, cells, _now() - start, read_points=point_count)


def _plane(name, z):
    bpy, _ = _bpy()
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-100, -100, z), (100, -100, z), (100, 100, z), (-100, 100, z)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def benchmark_confinement(records, morphology, sections, cells):
    from blenderneuron.blender.views.vectorconfinerview import VectorConfinerView

    clear_scene()
    build_scene(morphology, "Section", "Cell")
    start_mesh, end_mesh = _plane("benchmark_start", -2), _plane("benchmark_end", 8)
    bpy, _ = _bpy()
    curves = [obj for obj in bpy.context.scene.objects if obj.type == "CURVE"]
    start = _now()
    for curve in curves:
        VectorConfinerView.confine_between_meshes(curve, start_mesh, end_mesh, 0.0, 0.5, 15.0)
    _record(records, "two_surface_confinement", sections, cells, _now() - start,
            curve_count=len(curves), boundary="planes")


def benchmark_synapse_search(records, sections, cells):
    _, mathutils = _bpy()
    random.seed(1)
    count = sections * cells * 3
    destination = [(random.random() * 60, random.random() * 10, random.random() * 4) for _ in range(count)]
    source = [(point[0] + 0.3, point[1], point[2]) for point in destination]
    start = _now()
    tree = mathutils.kdtree.KDTree(count)
    for index, point in enumerate(destination):
        tree.insert(point, index)
    tree.balance()
    _record(records, "synapse_kdtree_build", sections, cells, _now() - start, destination_points=count)
    start = _now()
    hits = sum(len(tree.find_range(point, 1.0)) for point in source)
    _record(records, "synapse_range_search", sections, cells, _now() - start,
            source_points=count, proximity_hits=hits)


def benchmark_animation(records, morphology, sections, cells):
    clear_scene()
    build_scene(morphology, "Cell", "3D Segment")
    bpy, _ = _bpy()
    materials = list(bpy.data.materials)
    frames = (1, 5, 10)
    start = _now()
    for material in materials:
        for frame in frames:
            material["benchmark_value"] = frame / 10.0
            material.keyframe_insert(data_path='["benchmark_value"]', frame=frame)
    _record(records, "animation_keyframes", sections, cells, _now() - start,
            materials=len(materials), frames=len(frames), keyframes=len(materials) * len(frames))


def benchmark_static_import(records, sections, cells, interactions=("Cell", "Section"),
                            phase_profile=False, cprofile_prefix=None):
    """Build/export from NEURON, then import static morphology in Blender."""
    for interaction in interactions:
        clear_scene()
        rss_before = _rss_mib()
        rss_peak_before = _peak_rss_mib()
        start = _now()
        phases = {} if phase_profile else None
        phase_metrics = {} if phase_profile else None
        # Cell recording is the non-animated/static representation.
        import_live_neuron_group(
            cells, sections, interaction, "Cell", record_activity=False,
            phases=phases, phase_metrics=phase_metrics,
            cprofile_prefix=cprofile_prefix,
        )
        bpy, _ = _bpy()
        bpy.context.view_layer.update()
        _record(records, "workflow_static_import", sections, cells, _now() - start,
                interaction=interaction, object_count=len(bpy.context.scene.objects),
                **({"phase_seconds": phases} if phases is not None else {}),
                **({"phase_metrics": phase_metrics} if phase_metrics is not None else {}),
                rss_before_mib=rss_before, rss_peak_before_mib=rss_peak_before)


def benchmark_animation_setup(records, sections, cells, recordings=("Cell", "Section", "3D Segment"),
                              phase_profile=False, cprofile_prefix=None):
    """Build/export from NEURON, import, and attach recording-level animation."""
    for recording in recordings:
        clear_scene()
        rss_before = _rss_mib()
        rss_peak_before = _peak_rss_mib()
        start = _now()
        phases = {} if phase_profile else None
        phase_metrics = {} if phase_profile else None
        group = import_live_neuron_group(
            cells, sections, "Cell", recording, record_activity=True,
            phases=phases, phase_metrics=phase_metrics,
            cprofile_prefix=cprofile_prefix,
        )
        bpy, _ = _bpy()
        bpy.context.view_layer.update()
        animation_times = group.activity.times
        _record(records, "workflow_animation_setup", sections, cells, _now() - start,
                recording=recording, materials=len(bpy.data.materials),
                animation_samples=len(animation_times),
                animation_first_frame=bpy.context.scene.frame_start,
                animation_last_frame=bpy.context.scene.frame_end,
                animation_fps=bpy.context.scene.render.fps,
                **({"phase_seconds": phases} if phases is not None else {}),
                **({"phase_metrics": phase_metrics} if phase_metrics is not None else {}),
                rss_before_mib=rss_before, rss_peak_before_mib=rss_peak_before)


def save_workbench_animation_preview(path, sections=16, cells=8, recording="3D Segment"):
    """Render one active animation frame with the benchmark's framing camera."""
    clear_scene()
    group = import_live_neuron_group(cells, sections, "Cell", recording, record_activity=True)
    bpy, _ = _bpy()
    _configure_cycles_camera_and_neon()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    # This is a composition check, not a performance render; disable the
    # compositor so its add-on neon effect does not obscure Workbench shading.
    scene.use_nodes = False
    scene.frame_set(ANIMATION_FOCUS_FRAME)
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print(f"Wrote Workbench animation preview {path}")
    return path


def render_animation_propagation_previews(directory, sections=16, cells=1,
                                          recording="3D Segment", frames=(66, 68, 70, 72),
                                          render_engine="CYCLES"):
    """Render a short sequence spanning soma spike onset and dendritic spread."""
    clear_scene()
    group = import_live_neuron_group(cells, sections, "Cell", recording, record_activity=True)
    bpy, _ = _bpy()
    _configure_cycles_camera_and_neon(render_engine=render_engine)
    scene = bpy.context.scene
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    # Print an auditable raw-data check alongside the images.  The initial
    # dendritic segment and soma should both cross the configured color range
    # during this single-spike protocol.
    first_root = next(iter(group.roots.values()))
    first_dendrite = first_root.children[0]
    soma_activity = first_root.segment_activity[0]
    dendrite_activity = first_dendrite.segment_activity[0]
    terminal = first_root
    while terminal.children:
        terminal = terminal.children[0]
    terminal_activity = terminal.segment_activity[0]
    soma_values = soma_activity.values
    dendrite_values = dendrite_activity.values
    soma_peak = max(range(len(soma_values)), key=lambda index: soma_values[index])
    dendrite_peak = max(range(len(dendrite_values)), key=lambda index: dendrite_values[index])
    terminal_peak = max(range(len(terminal_activity.values)),
                        key=lambda index: terminal_activity.values[index])
    print("AP raw voltage check: soma=[%.1f, %.1f] mV (peak %.2f ms), first dendrite=[%.1f, %.1f] mV (peak %.2f ms), terminal peak %.2f ms" % (
        min(soma_values), max(soma_values), soma_activity.times[soma_peak],
        min(dendrite_values), max(dendrite_values), dendrite_activity.times[dendrite_peak],
        terminal_activity.times[terminal_peak]
    ))
    for frame in frames:
        scene.frame_set(frame)
        path = directory / f"ap_propagation_frame_{frame:03d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs.append(path)
    print("Wrote AP propagation previews:", ", ".join(str(path) for path in outputs))
    return outputs


def save_imported_animation_scene(path, sections=128, cells=1,
                                  interaction="Cell", recording="Section",
                                  configure_render=False):
    """Import one live NEURON group and optionally save it render-ready."""
    clear_scene()
    group = import_live_neuron_group(
        cells, sections, interaction, recording, record_activity=True
    )
    bpy, _ = _bpy()
    camera_visible = None
    if configure_render:
        camera_visible = _configure_cycles_camera_and_neon()
        bpy.context.scene.frame_set(ANIMATION_FOCUS_FRAME)
    bpy.context.view_layer.update()
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(
        "Saved %s: %d cells, %d sections/cell, %s interaction, %s animation, %d samples, render_ready=%s"
        % (path, cells, sections, interaction, recording, len(group.activity.times), camera_visible)
    )
    return path


def _configure_cycles_camera_and_neon(render_engine="CYCLES"):
    """Use add-on glare and frame all displayed morphology in an ortho camera."""
    from blenderneuron.blender.blendernode import BlenderNode
    from bpy_extras.object_utils import world_to_camera_view

    bpy, mathutils = _bpy()
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    corners = []
    for obj in scene.objects:
        if obj.type == "CURVE":
            corners.extend(obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box)
    if not corners:
        raise RuntimeError("No morphology curves were created for the render benchmark")

    minimum = mathutils.Vector(tuple(min(corner[index] for corner in corners) for index in range(3)))
    maximum = mathutils.Vector(tuple(max(corner[index] for corner in corners) for index in range(3)))
    center = (minimum + maximum) / 2
    span = maximum - minimum
    # Trees lie in x/z. Ortho scale is the horizontal span for this landscape
    # output; account for its aspect ratio when fitting the vertical extent.
    # Fit both dimensions with the same margin, independent of cell-grid shape.
    padding = 1.2
    aspect = RENDER_WIDTH_PX / RENDER_HEIGHT_PX
    view_span = max(span.x, span.z * aspect, 10.0) * padding

    camera_data = bpy.data.cameras.new("benchmark_camera")
    camera = bpy.data.objects.new("benchmark_camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = view_span
    distance = max(span.length * 2, 100.0)
    camera.location = center + mathutils.Vector((0.0, -distance, 0.0))
    target = center
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.clip_start = 0.01
    camera_data.clip_end = distance * 2
    scene.camera = camera
    if render_engine == "EEVEE":
        engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
        scene.render.engine = ("BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines
                               else "BLENDER_EEVEE")
        eevee = getattr(scene, "eevee", None)
        if eevee is not None and hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = 64
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16
        scene.cycles.use_denoising = False
    scene.render.resolution_x = RENDER_WIDTH_PX
    scene.render.resolution_y = RENDER_HEIGHT_PX
    scene.render.resolution_percentage = 100
    # Call the add-on implementation directly so a regenerated benchmark uses
    # the same compositor glare configuration as the user-facing feature.
    BlenderNode.add_neon_effect(None)
    bpy.context.view_layer.update()

    projected = [world_to_camera_view(scene, camera, corner) for corner in corners]
    visible = all(0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0 and point.z > 0.0 for point in projected)
    projected_width = max(point.x for point in projected) - min(point.x for point in projected)
    projected_height = max(point.y for point in projected) - min(point.y for point in projected)
    if not visible or projected_width < 0.45 or projected_height < 0.4:
        raise RuntimeError(
            "Benchmark camera does not provide a readable front-on view "
            f"(visible={visible}, projected_width={projected_width:.3f}, "
            f"projected_height={projected_height:.3f})"
        )
    return True


def benchmark_workflow_render(records, sections, cells):
    """Measure average and tail render cost over the active AP animation."""
    global _RENDER_WARMED
    for recording in ("Cell", "Section", "3D Segment"):
        clear_scene()
        group = import_live_neuron_group(cells, sections, "Cell", recording, record_activity=True)
        bpy, _ = _bpy()
        camera_visible = _configure_cycles_camera_and_neon()
        if not _RENDER_WARMED:
            bpy.ops.render.render(write_still=False)
            _RENDER_WARMED = True
        rss_before = _rss_mib()
        frame_times = []
        first_frame = bpy.context.scene.frame_start + 1
        last_frame = bpy.context.scene.frame_end
        frame_numbers = tuple(sorted({
            round(first_frame + index * (last_frame - first_frame) /
                  (RENDER_TIMING_FRAME_COUNT - 1))
            for index in range(RENDER_TIMING_FRAME_COUNT)
        }))
        for frame in frame_numbers:
            bpy.context.scene.frame_set(frame)
            start = _now()
            bpy.ops.render.render(write_still=False)
            frame_times.append(_now() - start)
        ordered_times = sorted(frame_times)

        def percentile(percent):
            index = round((len(ordered_times) - 1) * percent / 100)
            return ordered_times[index]

        _record(records, "workflow_frame_render", sections, cells, statistics.mean(frame_times),
                recording=recording,
                render_resolution=f"{RENDER_WIDTH_PX}x{RENDER_HEIGHT_PX}",
                compositor="addon_neon_glare", camera_visible=camera_visible,
                rendered_frames=len(frame_times),
                p95_seconds=percentile(95), p99_seconds=percentile(99),
                animation_samples=len(group.activity.times),
                animation_first_frame=bpy.context.scene.frame_start,
                animation_last_frame=bpy.context.scene.frame_end,
                animation_fps=bpy.context.scene.render.fps,
                rss_before_mib=rss_before)


def benchmark_scene_section_recording(records, morphology, sections, cells):
    """High-scale scene construction without 3D-segment material explosion."""
    for interaction in ("Cell", "Section"):
        clear_scene()
        start = _now()
        build_scene(morphology, interaction, "Section")
        bpy, _ = _bpy()
        bpy.context.view_layer.update()
        _record(records, "scene_section_recording", sections, cells, _now() - start,
                interaction=interaction,
                object_count=len(bpy.context.scene.objects))


def benchmark_render(records, morphology, sections, cells):
    """Render one tiny Workbench frame for an early rendering-cost signal."""
    clear_scene()
    build_scene(morphology, "Cell", "3D Segment")
    bpy, mathutils = _bpy()
    camera_data = bpy.data.cameras.new("benchmark_camera")
    camera = bpy.data.objects.new("benchmark_camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (sections * cells, -120.0, 50.0)
    target = mathutils.Vector((sections * cells, 1.0, 0.0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    global _RENDER_WARMED
    if not _RENDER_WARMED:
        bpy.ops.render.render(write_still=False)
        _RENDER_WARMED = True
    start = _now()
    bpy.ops.render.render(write_still=False)
    _record(records, "render_workbench_frame", sections, cells, _now() - start,
            render_resolution=128)


def run_neuron_synapse_profile(section_sizes=(128, 256, 512), repeats=REPEATS):
    """Run from NEURON's ordinary Python interpreter, not Blender's Python."""
    from neuron import h

    records = []
    for cells in QUICK_CELLS:
        for sections in section_sizes:
            count = cells * sections
            source = [h.Section(name="bench_source_%d_%d" % (cells, index)) for index in range(count)]
            dest = [h.Section(name="bench_dest_%d_%d" % (cells, index)) for index in range(count)]
            for variant in ("netcon", "head_neck_spine"):
                for _ in range(repeats):
                    created = []
                    start = _now()
                    for index, (source_sec, dest_sec) in enumerate(zip(source, dest)):
                        source_sec.insert("pas")
                        dest_sec.insert("pas")
                        if variant == "head_neck_spine":
                            head = h.Section(name="bench_head_%d_%d" % (index, len(created)))
                            neck = h.Section(name="bench_neck_%d_%d" % (index, len(created)))
                            head.insert("pas")
                            neck.insert("pas")
                            neck.connect(source_sec(0.5), 0)
                            head.connect(neck(1.0), 0)
                            source_sec = head
                        syn = h.ExpSyn(dest_sec(0.5))
                        created.append((h.NetCon(source_sec(0.5)._ref_v, syn, sec=source_sec), syn))
                    _record(records, "neuron_synapse_creation", sections, cells, _now() - start,
                            variant=variant, synapses=count)
    return records


def run_profile(name, section_sizes, repeats=REPEATS, include_render=True):
    records = []
    for cells in QUICK_CELLS:
        for sections in section_sizes:
            morphology = synthetic_morphology(cells, sections)
            for _ in range(repeats):
                benchmark_transport(records, morphology, sections, cells)
                benchmark_scene(records, morphology, sections, cells)
                benchmark_export_readback(records, morphology, sections, cells)
                benchmark_confinement(records, morphology, sections, cells)
                benchmark_synapse_search(records, sections, cells)
                benchmark_animation(records, morphology, sections, cells)
                if include_render:
                    benchmark_render(records, morphology, sections, cells)
    return {
        "profile": name,
        "note": "Synthetic exploratory profile; not publication measurements.",
        "records": records,
    }


def run_quick_profile(repeats=REPEATS):
    return run_profile("quick", QUICK_SECTIONS, repeats)


def run_progressive_profile(repeats=REPEATS):
    # Rendering is scaled independently: a high-cardinality Workbench render
    # can exhaust headless GPU resources before the CPU-side curves complete.
    return run_profile("progressive", PROGRESSIVE_SECTIONS, repeats, include_render=False)


def run_isolated_high_scale_profile(repeats=REPEATS):
    """Scale CPU-side workflows independently of 3D-segment rendering."""
    records = []
    for cells in QUICK_CELLS:
        for sections in ISOLATED_SECTIONS:
            morphology = synthetic_morphology(cells, sections)
            for _ in range(repeats):
                benchmark_scene_section_recording(records, morphology, sections, cells)
                benchmark_confinement(records, morphology, sections, cells)
                benchmark_synapse_search(records, sections, cells)
    return {
        "profile": "isolated_high_scale",
        "note": "High-scale isolated CPU-side probes; excludes 3D-segment animation and rendering.",
        "records": records,
    }


def run_workflow_profile(section_sizes=WORKFLOW_SECTIONS, cell_sizes=WORKFLOW_CELLS,
                         repeats=REPEATS, components=("static", "setup", "render")):
    """Collect the eight panels of the reader-facing 2×4 workflow figure."""
    records = []
    for cells in cell_sizes:
        for sections in section_sizes:
            for _ in range(repeats):
                if "static" in components:
                    benchmark_static_import(records, sections, cells)
                if "setup" in components:
                    benchmark_animation_setup(records, sections, cells)
                if "render" in components:
                    benchmark_workflow_render(records, sections, cells)
    return {
        "profile": "workflow",
        "note": (
            "NEURON-built, low-count workflow profile. Time is per workflow; "
            "memory is current process RSS after that workflow; "
            "repeats=%d; components=%s." % (repeats, ",".join(components))
        ),
        "records": records,
    }


def save_results(results, path=DEFAULT_RESULTS):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, sort_keys=True))
    return path


def load_results(path=DEFAULT_RESULTS):
    return json.loads(Path(path).read_text())


def _parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", action="store_true", help="run the 2x4 import/animation/render workflow sweep")
    parser.add_argument("--workflow-sections", help="comma-separated workflow section counts")
    parser.add_argument("--workflow-cells", help="comma-separated workflow cell counts")
    parser.add_argument("--workflow-repeats", type=int, default=REPEATS,
                        help="repetitions per workflow configuration")
    parser.add_argument("--workflow-components",
                        help="comma-separated workflow components: static,setup,render")
    parser.add_argument("--static-import", action="store_true",
                        help="run one static live-NEURON import measurement")
    parser.add_argument("--static-sections", type=int, default=16)
    parser.add_argument("--static-cells", type=int, default=1)
    parser.add_argument("--static-interaction", choices=("Cell", "Section"), default="Cell")
    parser.add_argument("--static-phase-profile", action="store_true",
                        help="record live NEURON and Blender static-import phase timings")
    parser.add_argument("--static-cprofile-prefix", type=Path,
                        help="write detailed <prefix>_neuron.pstats and <prefix>_blender.pstats")
    parser.add_argument("--animation-setup", action="store_true",
                        help="run one animated live-NEURON import/setup measurement")
    parser.add_argument("--animation-sections", type=int, default=16)
    parser.add_argument("--animation-cells", type=int, default=8)
    parser.add_argument("--animation-recording", choices=("Cell", "Section", "3D Segment"), default="Cell")
    parser.add_argument("--animation-phase-profile", action="store_true",
                        help="record live NEURON and Blender animation-import phase timings")
    parser.add_argument("--animation-cprofile-prefix", type=Path,
                        help="write detailed <prefix>_neuron.pstats and <prefix>_blender.pstats")
    parser.add_argument("--save-workbench-preview", type=Path,
                        help="import active animation data and render one orthographic Workbench preview")
    parser.add_argument("--render-ap-preview-dir", type=Path,
                        help="render neon frames spanning AP propagation")
    parser.add_argument("--preview-render-engine", choices=("CYCLES", "EEVEE"), default="CYCLES")
    parser.add_argument("--save-imported-blend", type=Path,
                        help="import one animated live NEURON group and save a .blend file")
    parser.add_argument("--import-sections", type=int, default=128)
    parser.add_argument("--import-cells", type=int, default=1)
    parser.add_argument("--import-interaction", choices=("Cell", "Section"), default="Cell")
    parser.add_argument("--import-recording", choices=("Cell", "Section", "3D Segment"),
                        default="Section")
    parser.add_argument("--configure-render", action="store_true",
                        help="add the benchmark's Cycles camera and neon/glare compositor before saving")
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    return parser.parse_args(argv)


def main(argv=None):
    command_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    args = _parse_args(argv if argv is not None else command_args)
    if args.save_imported_blend:
        save_imported_animation_scene(
            args.save_imported_blend,
            sections=args.import_sections,
            cells=args.import_cells,
            interaction=args.import_interaction,
            recording=args.import_recording,
            configure_render=args.configure_render,
        )
    elif args.render_ap_preview_dir:
        render_animation_propagation_previews(
            args.render_ap_preview_dir, args.animation_sections,
            args.animation_cells, args.animation_recording,
            render_engine=args.preview_render_engine,
        )
    elif args.save_workbench_preview:
        save_workbench_animation_preview(
            args.save_workbench_preview, args.animation_sections,
            args.animation_cells, args.animation_recording,
        )
    elif args.animation_setup:
        records = []
        benchmark_animation_setup(
            records, args.animation_sections, args.animation_cells,
            recordings=(args.animation_recording,), phase_profile=args.animation_phase_profile,
            cprofile_prefix=args.animation_cprofile_prefix,
        )
        output = save_results({
            "profile": "animation_setup_point",
            "note": "One live NEURON-to-Blender animated import/setup; Cell interaction.",
            "records": records,
        }, args.output)
        print("Wrote", output)
    elif args.static_import:
        records = []
        benchmark_static_import(
            records, args.static_sections, args.static_cells,
            interactions=(args.static_interaction,),
            phase_profile=args.static_phase_profile,
            cprofile_prefix=args.static_cprofile_prefix,
        )
        output = save_results({
            "profile": "static_import_point",
            "note": "One live NEURON-to-Blender static import; no animation.",
            "records": records,
        }, args.output)
        print("Wrote", output)
    elif args.workflow:
        section_sizes = (tuple(int(value) for value in args.workflow_sections.split(","))
                         if args.workflow_sections else WORKFLOW_SECTIONS)
        cell_sizes = (tuple(int(value) for value in args.workflow_cells.split(","))
                      if args.workflow_cells else WORKFLOW_CELLS)
        components = (tuple(args.workflow_components.split(","))
                      if args.workflow_components else ("static", "setup", "render"))
        results = run_workflow_profile(section_sizes, cell_sizes, args.workflow_repeats, components)
        output = save_results(results, args.output)
        print("Wrote", output)
    else:
        raise SystemExit("Choose --workflow or --save-imported-blend.")


if __name__ == "__main__":
    main()
