# Reproducing the import/export and confinement figures

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

The plotter writes `figures/figures_a_to_j.png`, `.svg`, and `.pdf`.

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

`plot_figures_a_to_j.py` is the import/export A–J figure entry point. `figures/` contains the final A–J PNG, SVG, and PDF, plus the approved
confinement panels described below.
This README is the single methodology and reproduction guide.

The three `results/*/results.json` files are required inputs to the final
figure, not superseded figures. Historical A–F/G–H names in measurement
scripts/data paths identify the original workloads; the A–J plotter maps them
to the current panel labels without duplicating data. The remaining scripts
are needed to regenerate those measurements through production add-on code.

Archives, exploratory artifacts, standalone panel figures, and redundant
per-run JSON/logs have been removed. Retained aggregates are sufficient for
plotting and resuming the final benchmark runs.

## Confinement figure: approved panels A–D

These four panels are the accepted visual baseline for the separate confinement
figure. They are independent of the existing performance A–J figure above.

| Panel | Case | Approved file |
| --- | --- | --- |
| A | Original cell, before confinement | `figures/confinement_panels/A_baseline.png` |
| B | 5° maximum bend, 100 µm maximum piece length | `figures/confinement_panels/B_5deg_100um.png` |
| C | 10°, 75 µm | `figures/confinement_panels/C_10deg_75um.png` |
| D | 15°, 50 µm | `figures/confinement_panels/D_15deg_50um.png` |

All use the same 16-section binary-tree morphology and seed 0. The source +X
trunk is mapped to +Z, rotated 80° around world Z, then +50° around world Y
(leaning right), about the soma center. The soma is placed at (−200, 0, 10) µm.
The planes are Z = 0 and 100 µm; height fractions 0–1 target the entire slab.
Each confinement trial starts from an identical original NEURON cell.

The style uses a blue cell, white background, gray target band, front
orthographic camera, and matching top-down inset looking along −Z. Front
renders are cropped 30% at the top and 20% at the right. Insets occupy the upper
left, shifted inward to keep axis labels within the figure margin. Target Zone
is vertically centered, the top caption is 10 µm above its boundary, and the
bottom caption is 20 µm below its boundary. No changes to this approved layout
are needed when adding the remaining metric panels.

`confinement_config.py` is the shared source of the pose, setup version,
conditions, panel mapping, and layout. `confinement_setup.py` constructs and
styles the scene. `confinement.py` runs production import/confinement/export
and records point/cable containment plus NEURON area, length, and volume.
The existing `tests/test_layer_confinement.py` also asserts total NEURON surface
area is preserved through confinement/export within 0.001%.

### Retained inputs and regeneration

`results/confinement_panels/` contains the three-trial `results.json`, eight
uncropped front/top source PNGs (including baseline), and `manifest.json` with
panel mapping, setup/layout, and SHA-256 hashes of the four approved PNGs.
This is sufficient to audit or recompose A–D. Superseded confinement scenes,
parameter examples, intermediate figures, per-run JSON/logs, and exploratory
sweeps have been removed.

To regenerate measurements and raw renders, start the Docker environment as
shown above and run inside it:

```sh
python notebooks/performance/render_confinement_examples.py
```

Then compose the four approved-layout panels on the host with matplotlib:

```sh
python notebooks/performance/confinement_insets.py
```

The renderer leaves the aggregate and eight raw images in
`results/confinement_panels/`; the compositor writes the four canonical PNGs
and updates the manifest. It never creates the superseded iteration folders.
The accepted images are retained byte-for-byte from the last reviewed layout.

The sensitivity sweep uses angles 5, 10, 15, and 25 degrees crossed
with maximum section lengths 200, 100, 75, 50, and 25 µm, each with seeds 0–4.
Every trial starts from identical original geometry. Run `confinement.py` inside
Docker to collect `results/confinement_z_up/` (100 trials; no renders unless
`--render` is supplied), then `plot_confinement_heatmap.py` on the host for
standalone panel E (PNG/PDF/SVG) and `summary.csv`. The primary metric is the
seed-averaged percentage of native dendrite n3d points outside the inclusive
Z=0–100 µm target zone. Zero means every measured point is inside. Splitting
can change point density, so the CSV also reports exact polyline cable-length
outside percentages and uniformly sampled point percentages, with seed SD,
minimum and maximum for each. Cable length means the summed lengths of all
dendrite sections, including partial segments crossing the boundaries.
Object counts and confinement times are retained to assess computational cost.
Heat-map labels report mean ± sample standard deviation across five seeds;
colors encode the mean. SD describes trial-to-trial variability, not the
uncertainty of the mean. Individual trial JSON files and the aggregate retain
each seed. Existing cached trials outside the current grid are excluded from
the aggregate and plot; matching trials are reused.

Run `plot_confinement.py` on the host to assemble the complete figure. The final
plotter uses the approved A–D images directly, with containment heatmap E and
runtime panel F, writing `confinement_a_to_f` PNG/PDF/SVG. The two-row,
three-column layout places A/B above C/D in the left two columns, with E above
F in the right column.
Both sweep and panel setup versions must match; exploratory measurements cannot
be silently reused.

### Runtime (panel F)

Run `python notebooks/performance/plot_confinement.py` to regenerate the final
figure. `plot_confinement_runtime.py` and `plot_confinement_heatmap.py` provide
the metric calculations and can optionally export standalone panels and CSV summaries. The plot reports mean ± sample SD for
`setup_seconds + confine_seconds`, pooled over four angles × five seeds
(20 trials) at each maximum section length. The blue curve reports mean ±
sample SD; the CSV also includes minimum and maximum timings. The orange curve
uses the right axis to show the maximum absolute whole-cell NEURON surface-area
error across those same 20 trials: `100 * abs(post - original) / original`,
after confinement and export back to NEURON. This maximum is also saved in the CSV.
Setup includes construction/splitting of the confinement view; confinement
includes the final Blender view-layer update. Import, rendering, export and
NEURON validation are excluded. Export timings remain separately in the CSV.
The top axis shows the measured number of Blender objects after splitting,
which is identical across angles/seeds at each length in this dataset.
All timings use the existing Docker trials on this machine; the runs were
collected in batches rather than randomized as a dedicated timing benchmark.
Seed SD therefore includes timing noise and run-order effects. These results
apply to the 16-section test morphology; they do not establish scaling to
large cells or groups. `plot_confinement.py` uses this runtime panel in A–F.

Only the two final figures, their source images/measurement aggregates, and
scripts required to regenerate them are retained. Confinement per-trial JSON
files duplicate the aggregate and are omitted; the sweep resumes directly from
`results/confinement_z_up/results.json`. To collect fresh measurements, use a
new `--results-dir`. Standalone metric exports are optional generated outputs.
