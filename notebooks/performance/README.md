# Performance Figures A–H

The retained aggregate contains 195 measurements: 39 conditions, five fresh
Blender processes per condition. Dots are medians; bars span min–max. Axes are
linear, without jitter.

| Panels | Sweep | Fixed settings | Curves |
| --- | --- | --- | --- |
| A/B | 8, 16, 32, 64, 128, 256, 512 cells | 16 sections/cell; no animation | Cell, Section interaction |
| C/D | 32, 64, 128, 256, 512 sections/cell | 8 cells; no animation | Cell, Section interaction |
| E/F | 8, 16, 32, 64, 128 cells | 16 sections/cell; Cell interaction | Cell, Section, 3D Segment animation |

Top panels measure import/setup time; bottom panels measure additional Blender
process peak RSS above its pre-workflow high-water mark. This excludes the
NEURON subprocess and dedicated GPU VRAM. Timing includes live NEURON startup,
construction, simulation when animated, transfer, and Blender import/setup;
it excludes Blender startup and exit. No render timing is included.

Cells are constructed in NEURON before connecting to BlenderNEURON, then
imported through production add-on operators. Each has a soma, one trunk, and
breadth-first binary branching; five segments and three 3D points per section.
The soma is 10 µm long/diameter; dendrites are 100 µm long and 2 µm in diameter.
All sections have passive and HH mechanisms. Animation uses a 1 nA soma clamp
from 5–15 ms, simulation 0–25 ms, sampling every 0.1 ms, and 10 frames/ms.

## Regenerate the figure without rerunning benchmarks

With matplotlib installed:

```sh
python notebooks/performance/plot_figures_a_to_h.py
```

Alternatively open `performance_evaluation.ipynb` and run its cells. The final
cell produces `figures/figures_a_to_h.png`, `.svg`, and `.pdf`.

## Rerun measurements

Build and start the Docker environment from the repository root:

```sh
./scripts/build.sh
docker run -d --init --name blenderneuron-performance \
  -v "$PWD:/BlenderNEURON" -w /BlenderNEURON \
  blenderneuron:latest sh -c 'cd /; ./link_addon.sh; ./start_vnc.sh'
sleep 10
docker exec blenderneuron-performance python notebooks/performance/rerun_figures_a_f_minmax.py
docker rm -f blenderneuron-performance
```

The runner resumes the aggregate in
`results/production_optimized_a_f_minmax/results.json`. To measure the current
code afresh, move that file aside before running. Five sequential blocks use
shuffle seeds 1051–1055; each process has a 300-second deadline. Coverage is
disabled. The retained measurements used Docker / Blender 4.0.2; rebuilding
with different software/hardware can change results. New per-run logs/JSON are
diagnostic only; the aggregate alone is sufficient to plot and resume.

`performance_eval.py` and `neuron_benchmark_server.py` retain the original shared
measurement/workload implementation unchanged to preserve measurement provenance.
Their older optional probes are not used by this runner.

## G–H: Native EEVEE Rendering

G/H use 8, 16, 32, 64, 128 cells with 16 sections each, Cell interaction,
and Cell, Section, or 3D Segment animation. The retained aggregate has 75
measurements (five independent processes per condition):
`results/eevee_g_h_native_minmax/results.json`. The original first repeat came
from the first native sweep; four further fresh repeats completed the five.

The reference system was Apple M1 Max, 32 GiB RAM, macOS 15.6, Blender 5.2.0
LTS with Metal. A–F used Docker / Blender 4.0.2, so these are separate workflow
measurements, not a controlled backend comparison.

Each run times an initial render at frame 66 separately, then averages twelve
warmed frames: 0, 36, 66, 68, 70, 71, 72, 107, 143, 179, 214, 250. Rendering
includes the add-on neon compositor but excludes frame changes and saving PNGs.
The camera is orthogonal to the tree plane and verified to frame every cell.
Resolution is 1800 × 900 at 100%, with 64 EEVEE samples. Memory is peak current
process RSS sampled every 10 ms across the initial and warmed renders, minus
pre-render current RSS; not VRAM. This differs from A–F's high-water-mark metric.
All runs, including slower repeats, are retained without outlier removal.

To rerun, start the Docker container above, but leave it running for scene
export. Then, from a native macOS Python environment with the repository's
dependencies installed:

```sh
python notebooks/performance/rerun_native_g_h.py --repeats 5 \
  --export-container blenderneuron-performance \
  --results-dir notebooks/performance/results/eevee_g_h_native_minmax
docker rm -f blenderneuron-performance
```

The default Blender executable is `/Applications/Blender.app/Contents/MacOS/Blender`;
override with `--blender`. Native rendering is controlled through private,
authenticated BlenderNEURON RPC, not screen automation. The runner exports
missing scenes through Docker using the production live NEURON/import path.
Saved scenes are caches, not required inputs, and are intentionally omitted.
The runner resumes the aggregate; move it aside first for fresh measurements.
Per-run JSON/logs and regenerated `.blend` caches can be discarded afterward.
