"""Measure export timing and numerical fidelity for the final A–J figure.

Controller: python export_roundtrip.py
Plot saved measurements with plot_figures_a_to_j.py.
Workers run in Blender inside the repository Docker environment.
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results/export_roundtrip_fixed_width_length_minmax"
sys.path.insert(0, str(HERE))


def neuron_snapshot():
    """Executed via the authenticated NEURON node, never inside the timer."""
    from neuron import h
    result = {}
    for sec in h.allsec():
        ref = h.SectionRef(sec=sec)
        result[sec.name()] = {
            "points": [[h.x3d(i, sec=sec), h.y3d(i, sec=sec), h.z3d(i, sec=sec)]
                       for i in range(int(h.n3d(sec=sec)))],
            "diameters": [h.diam3d(i, sec=sec) for i in range(int(h.n3d(sec=sec)))],
            "area": sum(seg.area() for seg in sec),
            "volume": sum(seg.volume() for seg in sec),
            "length": float(sec.L),
            "nseg": int(sec.nseg), "n3d": int(h.n3d(sec=sec)),
            "parent": ref.parent.name() if ref.has_parent() else None,
        }
    return result


def remote_snapshot(node):
    return node.client.run_command(
        "import sys; sys.path.insert(0, %r); "
        "from export_roundtrip import neuron_snapshot; return_value = neuron_snapshot()" % str(HERE))


def worker(args):
    import bpy
    import numpy as np
    from mathutils import Matrix, Vector
    import performance_eval as perf

    result = {}

    def roundtrip(group, node):
        before = remote_snapshot(node)
        # Record independent double-precision expectations from NEURON, not
        # from the same add-on extraction routine that export will exercise.
        c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
        rotation = np.array([[c, 0., s], [0., 1., 0.], [-s, 0., c]])
        pivots = {}
        roots = list(group.roots.values())
        for root in roots:
            pts = np.array(before[root.name]["points"])
            pivot = (pts[0] + pts[-1]) / 2
            pivots[root.name.split(".")[0]] = pivot
            ob = group.view.containers[root.name].get_object()
            if ob.parent is not None:
                raise AssertionError("A cell root must not have a parent")
            p = Vector(pivot)
            transform = (Matrix.Translation(Vector((100., 0., 0.))) @
                         Matrix.Translation(p) @ Matrix.Rotation(math.pi / 4, 4, "Y") @
                         Matrix.Translation(-p))
            ob.matrix_world = transform @ ob.matrix_world
        bpy.context.view_layer.update()

        expected = {}
        blender_expected = {}
        for container in group.view.containers.values():
            ob = container.get_object()
            # Read Blender spline vertices directly, independently of add-on
            # get_spline_3d_data / to_global; discard synthetic end caps.
            for name, index in container.name2spline_index.items():
                spline = ob.data.splines[index]
                points = list(spline.bezier_points)
                if container.closed_ends:
                    points = points[1:-1]
                blender_expected[name] = np.array([tuple(ob.matrix_world @ pt.co) for pt in points])
        for name, sec in before.items():
            pivot = pivots[name.split(".")[0]]
            expected[name] = (np.array(sec["points"]) - pivot) @ rotation.T + pivot + [100., 0., 0.]
        assert set(blender_expected) == set(before)

        start = time.perf_counter()
        assert bpy.ops.blenderneuron.update_groups_with_view_data() == {"FINISHED"}
        assert bpy.ops.blenderneuron.export_groups() == {"FINISHED"}
        elapsed = time.perf_counter() - start
        after = remote_snapshot(node)
        assert set(before) == set(after)
        assert all(before[n]["parent"] == after[n]["parent"] for n in before)
        metrics = {}
        for key in ("area", "volume", "nseg", "n3d"):
            pre = sum(sec[key] for sec in before.values())
            post = sum(sec[key] for sec in after.values())
            metrics[key] = {"before": pre, "after": post, "delta": post-pre,
                            "relative_delta_percent": 100*(post-pre)/pre}
        max_section_errors = {
            key: max(abs(100*(after[n][key]-before[n][key])/before[n][key]) for n in before)
            for key in ("area", "volume", "length")
        }
        worst_length_section = max(before, key=lambda n:
            abs((after[n]["length"]-before[n]["length"])/before[n]["length"]))
        distances = [float(np.linalg.norm(np.array(after[n]["points"]) - blender_expected[n], axis=1).max())
                     for n in before]
        analytic_errors = [float(np.linalg.norm(np.array(after[n]["points"]) - expected[n], axis=1).max())
                           for n in before]
        edit_errors = [float(np.linalg.norm(blender_expected[n] - expected[n], axis=1).max()) for n in before]
        diameter_error = max(abs(a-b) for n in before for a, b in
                             zip(before[n]["diameters"], after[n]["diameters"]))
        assert all(before[n][k] == after[n][k] for n in before for k in ("nseg", "n3d"))
        # Coordinate magnitudes grow with the cell grid. Bound accumulated
        # float32 Blender matrix/NEURON pt3d rounding independently of the
        # observed errors; retain the actual errors without clipping them.
        scale = max(1., max(float(np.abs(p).max()) for p in expected.values()))
        tolerance = max(.01, 32 * np.finfo(np.float32).eps * scale)
        assert max(edit_errors) < tolerance, "Root edits did not transform all descendant geometry correctly"
        assert max(analytic_errors) < tolerance, "Export did not apply the expected rigid transform"
        assert diameter_error < 1e-5
        result.update(cells=args.cells, sections=16, interaction=args.level, seconds=elapsed,
                      metrics=metrics, max_point_error_um=max(distances),
                      max_section_relative_error_percent=max_section_errors,
                      worst_length_section={"name": worst_length_section,
                                            "before_um": before[worst_length_section]["length"],
                                            "after_um": after[worst_length_section]["length"]},
                      max_analytic_point_error_um=max(analytic_errors),
                      max_blender_transform_error_um=max(edit_errors),
                      max_diameter_error_um=diameter_error, topology_unchanged=True,
                      coordinate_validation_tolerance_um=tolerance,
                      layout_x_extent_um=os.environ.get("BLENDERNEURON_BENCH_X_EXTENT_UM"),
                      section_counts_unchanged=True, transformed_root_objects=len(roots),
                      rotation_axis="Y", rotation_degrees=45, translation_um=[100, 0, 0],
                      pivot="Soma midpoint", blender=bpy.app.version_string, status="ok")

    perf.clear_scene()
    perf.import_live_neuron_group(args.cells, 16, args.level, "Cell", False, after_import=roundtrip)
    args.output.write_text(json.dumps(result, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--cells", type=int, default=8)
    p.add_argument("--level", choices=("Cell", "Section"), default="Cell")
    p.add_argument("--output", type=Path)
    p.add_argument("--results-dir", type=Path, default=OUT)
    p.add_argument("--x-extent-um", type=float, default=3150.)
    p.add_argument("--repeats", type=int, default=5)
    args = p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None)
    if args.worker:
        worker(args)
    else:
        if args.x_extent_um <= 0 or args.repeats < 1:
            p.error("--x-extent-um and --repeats must be positive")
        directory = args.results_dir
        directory.mkdir(parents=True, exist_ok=True)
        worker_env = os.environ.copy()
        worker_env.pop("COVERAGE_PROCESS_START", None)
        worker_env["BLENDERNEURON_BENCH_X_EXTENT_UM"] = str(args.x_extent_um)
        aggregate = directory / "results.json"
        previous = json.loads(aggregate.read_text())["records"] if aggregate.exists() else []
        conditions = [(n, l) for n in (8, 16, 32, 64, 128, 256, 512) for l in ("Cell", "Section")]
        jobs = []
        for repeat in range(1, args.repeats+1):
            block = list(conditions)
            if args.repeats > 1:
                random.Random(2150+repeat).shuffle(block)
            jobs.extend((repeat, count, level) for count, level in block)
        rows = []
        for repeat, count, level in jobs:
            suffix = f"_r{repeat:02d}" if args.repeats > 1 else ""
            path = directory / f"c{count:03d}_{level.lower()}{suffix}.json"
            saved = [r for r in previous if r["cells"] == count and r["interaction"] == level
                     and r.get("repeat", 1) == repeat]
            if saved:
                assert len(saved) == 1
                measurement = saved[0]
            elif path.exists():
                measurement = json.loads(path.read_text())
            else:
                with path.with_suffix(".log").open("w") as log:
                    subprocess.run(["blender", "--background", "--python-exit-code", "1",
                                    "--python", str(Path(__file__).resolve()), "--", "--worker",
                                    "--cells", str(count), "--level", level, "--output", str(path)],
                                   env=worker_env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
                measurement = json.loads(path.read_text())
            if float(measurement.get("layout_x_extent_um") or -1) != args.x_extent_um:
                raise RuntimeError("Saved measurement has a different layout; use a new --results-dir")
            if "length" not in measurement.get("max_section_relative_error_percent", {}):
                raise RuntimeError("Saved measurement predates length validation; use a fresh --results-dir")
            rows.append({**measurement, "repeat": repeat})
            aggregate.write_text(json.dumps({"repeats": args.repeats, "records": rows}, indent=2))
            print(f"[{len(rows)}/{len(jobs)}] {count} cells, {level}, run {repeat}: "
                  f"{measurement['seconds']:.4f}s", flush=True)


if __name__ == "__main__":
    main()
