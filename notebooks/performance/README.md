# Performance Figures A–J

The three retained aggregates contain 340 measurements: 68 conditions, five
independent Blender processes per condition. Dots/bar heights are medians;
error bars span min–max. Time/size axes are linear, without jitter.
All x-axes use numeric linear spacing. A/B and E/F omit 8 and 16 cells from
the figure to avoid crowding; their measurements remain in the aggregates.

| Panels | Sweep | Fixed settings | Curves |
| --- | --- | --- | --- |
| A/B | 8, 16, 32, 64, 128, 256, 512 cells | 16 sections/cell; no animation | Cell, Section interaction |
| C/D | 32, 64, 128, 256, 512 sections/cell | 8 cells; no animation | Cell, Section interaction |
| E/F | 8, 16, 32, 64, 128, 256, 512 cells | 16 sections/cell; 3.15 mm soma layout X span; edited cells; no animation | Cell, Section interaction |
| G/H | 8, 16, 32, 64, 128 cells | 16 sections/cell; Cell interaction | Cell, Section, 3D Segment animation |
| I/J | 8, 16, 32, 64, 128 cells | 16 sections/cell; Cell interaction; EEVEE + neon | Cell, Section, 3D Segment animation |

Top panels measure workflow time. B, D, and H measure additional Blender
process peak RSS above its pre-workflow high-water mark. This excludes the
NEURON subprocess and dedicated GPU VRAM. Timing includes live NEURON startup,
construction, simulation when animated, transfer, and Blender import/setup;
it excludes Blender startup and exit. Export and render timings are defined below.

Cells are constructed in NEURON before connecting to BlenderNEURON, then
imported through production add-on operators. Each has a soma, one trunk, and
breadth-first binary branching; five segments and three 3D points per section.
The soma is 10 µm long/diameter; dendrites are 100 µm long and 2 µm in diameter.
All sections have passive and HH mechanisms. Animation uses a 1 nA soma clamp
from 5–15 ms, simulation 0–25 ms, sampling every 0.1 ms, and 10 frames/ms.

## Regenerate the figure without rerunning benchmarks

With matplotlib installed:

```sh
python notebooks/performance/plot_figures_a_to_j.py
```

Alternatively open `performance_evaluation.ipynb` and run its cells. The final
cell produces `figures/figures_a_to_j.png`, `.svg`, and `.pdf`, embedding the
PNG in the notebook for GitHub viewing.

## Rerun measurements

Build and start the Docker environment from the repository root:

```sh
./scripts/build.sh
docker run -d --init --name blenderneuron-performance \
  -v "$PWD:/BlenderNEURON" -w /BlenderNEURON \
  blenderneuron:latest sh -c 'cd /; ./link_addon.sh; ./start_vnc.sh'
sleep 10
docker exec blenderneuron-performance python notebooks/performance/rerun_figures_a_f_minmax.py
docker exec blenderneuron-performance python notebooks/performance/export_roundtrip.py \
  --repeats 5 --results-dir notebooks/performance/results/export_roundtrip_fixed_width_length_minmax
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

## E–F: Edited-Cell Export

All 70 measurements are retained in
`results/export_roundtrip_fixed_width_length_minmax/results.json`. Each fresh worker
builds/imports live NEURON cells, rotates only each cell's root object 45° about
Y around its soma midpoint, then translates +100 µm along X. Section interaction
uses existing Blender parenting to carry descendants. The soma layout width
is fixed at 3.15 mm, independent of cell count, to control coordinate precision.
Only the export workload uses this layout setting; previous import/render
measurements are unchanged. The five shuffled repeat blocks use seeds 2151–2155.

E times the production view-data update and synchronous export RPC, including
current production compression and application in NEURON. It excludes import,
editing, verification, Blender startup, and exit. F contains three stacked
error axes: total surface-area relative change, maximum per-section length
relative change (both absolute percentages), and
maximum coordinate error (µm) against the exact intended transform. Each bar
pools the ten observations per cell count across interaction levels (five
each): median height and full pooled min–max. Its range therefore includes
between-level differences, not just repeated-run timing variability.
The length error is measured directly as the maximum of
`100 * abs(L_after - L_before) / L_before` across all NEURON sections in a run.
Its worst section and pre/post lengths are saved for independent checks.
All checks run outside the timer. Exact-zero nseg/n3d checks remain in raw
measurements but are no longer plotted.
Existing export measurements resume from the aggregate even after per-run
logs/JSON are removed. Move the aggregate aside for a fresh five-run sweep.

### Round-trip validation

NEURON snapshots capture per-section length (`Section.L`), surface area and
volume (sums of `Segment.area()` and `Segment.volume()`), all pt3d coordinates,
diameters, nseg, n3d, and parent identities. The benchmark verifies that:

- Every section's nseg/n3d and parent identity are unchanged.
- Diameters are unchanged within 0.00001 µm.
- Directly read Blender world-space points agree with an independently
  calculated double-precision rigid transform of the original NEURON points.
- Post-export NEURON points also agree with that exact intended transform.

Coordinate validation uses
`max(0.01 µm, 32 * float32_epsilon * max_abs_expected_coordinate)` to allow
floating-point rounding. This bound is independent of observed errors; plotted
errors are neither clipped nor normalized by it. Raw measurements also retain
Blender-to-NEURON-only and Blender-transform-only coordinate errors.

The fixed layout width controls loss of absolute coordinate precision as
objects move farther from the origin. Cell count changes only spacing, not
individual cell shapes or the two-row layout. Dense scenes may overlap; this
does not affect this geometry-export workload, which is not rendered.

The import helper's optional callback keeps the production-connected NEURON
server alive for editing, export, and validation, then cleans it up. The
normal import benchmark path is unchanged. Each worker has a 300-second
deadline. All 70 export measurements were collected afresh with direct length
validation; lengths were not inferred from area/volume or copied between runs.
Volume and count checks remain in raw data even though they are not plotted.

## I–J: Native EEVEE Rendering

I/J use 8, 16, 32, 64, 128 cells with 16 sections each, Cell interaction,
and Cell, Section, or 3D Segment animation. The retained aggregate has 75
measurements (five independent processes per condition):
`results/eevee_g_h_native_minmax/results.json`. The original first repeat came
from the first native sweep; four further fresh repeats completed the five.

The reference system was Apple M1 Max, 32 GiB RAM, macOS 15.6, Blender 5.2.0
LTS with Metal. A–H used Docker / Blender 4.0.2, so these are separate workflow
measurements, not a controlled backend comparison.

Each run times an initial render at frame 66 separately, then averages twelve
warmed frames: 0, 36, 66, 68, 70, 71, 72, 107, 143, 179, 214, 250. Rendering
includes the add-on neon compositor but excludes frame changes and saving PNGs.
The camera is orthogonal to the tree plane and verified to frame every cell.
Resolution is 1800 × 900 at 100%, with 64 EEVEE samples. Memory is peak current
process RSS sampled every 10 ms across the initial and warmed renders, minus
pre-render current RSS; not VRAM. This differs from B/D/H's high-water-mark metric.
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

## File Organization

`plot_figures_a_to_j.py` and `performance_evaluation.ipynb` are the only figure
entry points. `figures/` contains only the final A–J PNG, SVG, and PDF.
This README is the single methodology and reproduction guide.

The three `results/*/results.json` files are required inputs to the final
figure, not superseded figures. Historical A–F/G–H names in measurement
scripts/data paths identify the original workloads; the A–J plotter maps them
to the current panel labels without duplicating data. The remaining scripts
are needed to regenerate those measurements through production add-on code.

Archives, exploratory artifacts, standalone panel figures, and redundant
per-run JSON/logs have been removed. Retained aggregates are sufficient for
plotting and resuming the final benchmark runs.
