"""EEVEE measurement helpers for final panels I–J; use inside the test image.

Run this file with Python to orchestrate, or Blender --python ... -- --worker
to measure one condition. Plot results only with plot_figures_a_to_j.py.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import threading
import time
import traceback

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "eevee_g_h"
LEVELS = ("Cell", "Section", "3D Segment")
COUNTS = (8, 16, 32, 64, 128)
# Eight frames spanning 0–25 ms plus four around the verified AP propagation.
FRAMES = sorted(set(round(i * 250 / 7) for i in range(8)) | {66, 68, 70, 72})


def prepare_scene(cells, level):
    """Shared scene construction for measured renders and saved artifacts."""
    import bpy
    sys.path.insert(0, str(HERE))
    import performance_eval as perf

    os.environ["BLENDERNEURON_BENCH_LAYOUT"] = "render_grid"
    perf.clear_scene()
    group = perf.import_live_neuron_group(cells, 16, "Cell", level, True)
    visible = perf._configure_cycles_camera_and_neon(render_engine="EEVEE")
    scene = bpy.context.scene
    scene.frame_set(66)
    bpy.context.view_layer.update()
    return group, visible


def save_scene(args):
    import bpy
    group, visible = prepare_scene(args.cells, args.level)
    scene = bpy.context.scene
    scene.frame_set(70)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = "//renders/benchmark_"
    scene["benchmark_cells"] = args.cells
    scene["benchmark_sections_per_cell"] = 16
    scene["benchmark_interaction"] = "Cell"
    scene["benchmark_animation_granularity"] = args.level
    scene["benchmark_render_frames"] = FRAMES
    scene["benchmark_first_render_frame"] = 66
    scene["benchmark_frames_per_ms"] = 10.0
    scene["benchmark_camera_verified"] = visible
    scene["benchmark_animation_samples"] = len(group.activity.times)
    for frame in FRAMES:
        scene.timeline_markers.new(f"Benchmark {frame / 10:g} ms", frame=frame)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    args.save_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.save_blend.resolve()))


def worker(args):
    group, visible = prepare_scene(args.cells, args.level)
    return measure_render_scene(args.cells, args.level, group, visible)


def measure_render_scene(cells, level, group, visible, rss_reader=None):
    """Measure an already prepared scene, including saved native artifacts."""
    import bpy
    import performance_eval as perf
    scene = bpy.context.scene
    read_rss = rss_reader or perf._rss_mib
    baseline = read_rss()
    peak = [baseline]
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], read_rss())
            stop.wait(0.01)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        start = time.perf_counter()
        bpy.ops.render.render(write_still=False)
        cold_seconds = time.perf_counter() - start
        cold_peak = peak[0]
        frames = []
        for frame in FRAMES:
            scene.frame_set(frame)
            start = time.perf_counter()
            bpy.ops.render.render(write_still=False)
            frames.append(dict(frame=frame, simulation_ms=frame / 10,
                               seconds=time.perf_counter() - start))
        peak[0] = max(peak[0], read_rss())
    finally:
        stop.set()
        sampler.join(timeout=2)
    times = [frame["seconds"] for frame in frames]
    import gpu
    return dict(status="ok", cells=cells, sections=16, interaction="Cell",
                graphics_vendor=gpu.platform.vendor_get(),
                graphics_renderer=gpu.platform.renderer_get(),
                graphics_version=gpu.platform.version_get(),
                recording=level, engine=scene.render.engine,
                blender=bpy.app.version_string, resolution=[1800, 900], samples=64,
                compositor="addon_neon_glare", camera_visible=visible,
                frames=frames, seconds=statistics.mean(times),
                min_seconds=min(times), max_seconds=max(times),
                first_render_seconds=cold_seconds,
                rss_before_render_mib=baseline, rss_render_peak_mib=peak[0],
                rss_render_peak_delta_mib=max(0, peak[0] - baseline),
                first_render_peak_delta_mib=max(0, cold_peak - baseline),
                memory_sampling_period_seconds=0.01,
                animation_samples=len(group.activity.times))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--save-blend", type=Path,
                        help="save the exact benchmark scene instead of timing renders")
    parser.add_argument("--cells", type=int, default=8)
    parser.add_argument("--level", choices=LEVELS, default="Cell")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--results-dir", type=Path, default=OUT)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    if args.save_blend:
        save_scene(args)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    if args.worker:
        try:
            result = worker(args)
        except Exception:
            result = dict(status="error", error=traceback.format_exc())
        args.output.write_text(json.dumps(result, indent=2))
        sys.stdout.flush()
        sys.stderr.flush()
        # The helper already stopped NEURON; avoid unrelated Blender teardown.
        os._exit(0 if result["status"] == "ok" else 1)
    directory = args.results_dir
    directory.mkdir(parents=True, exist_ok=True)
    conditions = [(cells, level) for cells in COUNTS for level in LEVELS]
    random.Random(233).shuffle(conditions)
    rows = []
    for index, (cells, level) in enumerate(conditions, 1):
        path = directory / f"c{cells:03d}_{level.lower().replace(' ', '_')}.json"
        if not path.exists() or json.loads(path.read_text()).get("status") != "ok":
            env = os.environ.copy()
            env.pop("COVERAGE_PROCESS_START", None)
            cmd = ["blender", "--background", "--python-exit-code", "1", "--python", str(Path(__file__).resolve()),
                   "--", "--worker", "--cells", str(cells), "--level", level, "--output", str(path)]
            print(f"[{index}/15] Rendering {cells} cells / {level}", flush=True)
            with path.with_suffix(".log").open("w") as log:
                subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT,
                               check=True, timeout=1200)
        row = json.loads(path.read_text())
        if row["status"] != "ok":
            raise RuntimeError(row)
        rows.append(row)
        (directory / "results.json").write_text(json.dumps(dict(
            records=rows, note="One isolated scene per condition; 12 warmed frames. "
            "Memory is sampled process RSS peak including first render minus pre-render RSS. "
            "Not GPU VRAM. Render time includes compositor, excludes frame_set and PNG saving. "
            "First render reported separately; no reliable tail percentiles from 12 frames."), indent=2))
        print(f"[{index}/15] Done: {row['seconds']:.3f} s/frame; "
              f"{row['rss_render_peak_delta_mib']:.1f} MiB additional", flush=True)


if __name__ == "__main__":
    main()
