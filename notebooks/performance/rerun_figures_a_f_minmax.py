"""Measure static imports and animation setup for the final A–J figure."""

import json
import os
import random
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "results/production_optimized_a_f_minmax"


def command_for(condition, output):
    base = ["blender", "--background", "--python", str(HERE / "performance_eval.py"), "--"]
    if condition["workflow"] == "static":
        return base + ["--static-import", "--static-sections", str(condition["sections"]),
                       "--static-cells", str(condition["cells"]),
                       "--static-interaction", condition["level"], "--output", str(output)]
    return base + ["--animation-setup", "--animation-sections", str(condition["sections"]),
                   "--animation-cells", str(condition["cells"]),
                   "--animation-recording", condition["level"], "--output", str(output)]


def completed_row(path, condition):
    if not path.exists():
        return None
    rows = json.loads(path.read_text())["records"]
    benchmark = "workflow_static_import" if condition["workflow"] == "static" else "workflow_animation_setup"
    label_key = "interaction" if condition["workflow"] == "static" else "recording"
    matches = [row for row in rows if row["benchmark"] == benchmark
               and row["sections"] == condition["sections"]
               and row["cells"] == condition["cells"]
               and row[label_key] == condition["level"]]
    return matches[0] if len(matches) == 1 else None


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    conditions = []
    for cells in (8, 16, 32, 64, 128, 256, 512):
        for level in ("Cell", "Section"):
            conditions.append(dict(figure="A/B", workflow="static", cells=cells, sections=16, level=level))
    for sections in (32, 64, 128, 256, 512):
        for level in ("Cell", "Section"):
            conditions.append(dict(figure="C/D", workflow="static", cells=8, sections=sections, level=level))
    for cells in (8, 16, 32, 64, 128):
        for level in ("Cell", "Section", "3D Segment"):
            conditions.append(dict(figure="E/F", workflow="animation", cells=cells, sections=16, level=level))
    env = os.environ.copy()
    env.pop("COVERAGE_PROCESS_START", None)
    # The aggregate is sufficient to resume; individual logs/JSON are disposable.
    aggregate = OUTPUT / "results.json"
    previous = json.loads(aggregate.read_text())["records"] if aggregate.exists() else []
    records = []
    for repeat in range(1, 6):
        block = list(conditions)
        random.Random(1050 + repeat).shuffle(block)
        for condition in block:
            slug = (f"{condition['figure'].replace('/', '_')}_c{condition['cells']:03d}"
                    f"_s{condition['sections']:03d}_{condition['level'].replace(' ', '_')}_r{repeat:02d}")
            path = OUTPUT / (slug + ".json")
            saved = [r for r in previous if all(r.get(k) == v for k, v in condition.items())
                     and r["repeat"] == repeat]
            row = saved[0] if len(saved) == 1 else completed_row(path, condition)
            if row is None:
                started = time.time()
                with (OUTPUT / (slug + ".log")).open("w") as log:
                    subprocess.run(command_for(condition, path), stdout=log, stderr=subprocess.STDOUT,
                                   env=env, check=True, timeout=300)
                row = completed_row(path, condition)
                if row is None:
                    raise RuntimeError(f"Missing or invalid measurement: {slug}")
                print(f"[{len(records)+1}/195] {slug}: {row['seconds']:.3f}s "
                      f"({time.time()-started:.1f}s wall)", flush=True)
            else:
                print(f"[{len(records)+1}/195] Reusing completed {slug}", flush=True)
            records.append({**row, **condition, "repeat": repeat, "source_file": path.name})
            (OUTPUT / "results.json").write_text(json.dumps({
                "repeats": 5, "coverage_disabled": True,
                "ordering": "Five sequential blocks, shuffled with seeds 1051–1055",
                "platform": "Docker / Blender 4.0.2", "records": records,
            }, indent=2))


if __name__ == "__main__":
    main()
