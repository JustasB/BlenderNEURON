"""Plot five-run import, edited-cell export, animation, and rendering results."""

import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea
from matplotlib.transforms import ScaledTranslation

HERE = Path(__file__).resolve().parent
COLORS = {"Cell": "#0072B2", "Section": "#E69F00", "3D Segment": "#009E73"}


def set_panel_title(ax, title, fontsize, pad):
    """Give panel letters an independent, larger font than title text."""
    if len(title) > 2 and title[0] in "ABCDEFGHIJ" and title[1:3] == ". ":
        content = HPacker(children=[
            TextArea(title[:2], textprops={"fontsize": 18, "fontweight": "bold"}),
            TextArea(title[3:], textprops={"fontsize": fontsize}),
        ], align="baseline", pad=0, sep=5)
        transform = ax.transAxes + ScaledTranslation(0, pad/72, ax.figure.dpi_scale_trans)
        ax.add_artist(AnchoredOffsetbox(loc="lower left", child=content,
                      pad=0, borderpad=0, frameon=False,
                      bbox_to_anchor=(0, 1), bbox_transform=transform))
    else:
        ax.set_title(title, loc="left", fontsize=fontsize, pad=pad)


def summary(values):
    assert len(values) == 5, "Every plotted point must have five measurements"
    mid = statistics.median(values)
    return mid, mid-min(values), max(values)-mid


def roundtrip_axes(fig, slot, rows):
    """Three unit-specific axes; each bar pools five runs from each level."""
    grid = slot.subgridspec(3, 1, hspace=.65)
    counts = sorted({r["cells"] for r in rows})
    width = min(b-a for a, b in zip(counts, counts[1:])) * .5
    first = None
    for i, (metric, title, ylabel) in enumerate((
        ("area", "F. Roundtrip Import->Export Errors", "Area (%)"),
        ("length", "Max Per-Section Length Error", "Length (%)"),
        ("points", "Point Positions", "Position (µm)"),
    )):
        ax = fig.add_subplot(grid[i], sharex=first)
        if first is None:
            first = ax
        stats = []
        for count in counts:
            group = [r for r in rows if r["cells"] == count]
            assert len(group) == 10
            values = [(r["max_analytic_point_error_um"] if metric == "points" else
                       r["max_section_relative_error_percent"]["length"] if metric == "length" else
                       abs(r["metrics"][metric]["relative_delta_percent"])) for r in group]
            mid = statistics.median(values)
            stats.append((mid, mid-min(values), max(values)-mid))
        ax.bar(counts, [s[0] for s in stats], width=width, color="#7B3294",
               yerr=[[s[1] for s in stats], [s[2] for s in stats]], capsize=2,
               error_kw={"elinewidth": .8})
        ax.set_xscale("linear")
        ax.set_xlim(0, max(counts)*1.04)
        ax.set_ylim(bottom=0)
        ax.set_xticks(counts)
        ax.tick_params(axis="both", labelsize=8.5)
        ax.tick_params(axis="x", labelbottom=i == 2, labelrotation=55)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, pos: f"{value:.8f}".rstrip("0").rstrip(".") if value else "0"))
        ax.set_ylabel(ylabel, fontsize=9.5)
        set_panel_title(ax, title, fontsize=11.5 if i == 0 else 9.5, pad=10)
        ax.grid(axis="y", alpha=.22)
        if i == 2:
            ax.set_xlabel("Cells (16 Sections per Cell)", fontsize=10.5, labelpad=8)


def main():
    imports = json.loads((HERE / "results/production_optimized_a_f_minmax/results.json").read_text())["records"]
    exports = json.loads((HERE / "results/export_roundtrip_fixed_width_length_minmax/results.json").read_text())["records"]
    renders = json.loads((HERE / "results/eevee_g_h_native_minmax/results.json").read_text())["records"]
    assert len(imports) == 195 and len(exports) == 70 and len(renders) == 75
    assert all(float(r["layout_x_extent_um"]) == 3150 for r in exports)
    fig, axes = plt.subplots(2, 5, figsize=(17.6, 8))
    columns = (
        ([r for r in imports if r["figure"] == "A/B" and r["cells"] >= 32], "cells", "level", ("Cell", "Section"),
         "A. Import Time: Cell Count", "B. Import Memory: Cell Count",
         "Cells (16 Sections per Cell)", "rss_peak_delta_mib"),
        ([r for r in imports if r["figure"] == "C/D"], "sections", "level", ("Cell", "Section"),
         "C. Import Time: Sections/Cell", "D. Import Memory: Sections/Cell",
         "Sections per Cell (8 Cells)", "rss_peak_delta_mib"),
        ([r for r in exports if r["cells"] >= 32], "cells", "interaction", ("Cell", "Section"),
         "E. Edited-Cell Export Time", "F. Roundtrip Import->Export Errors",
         "Cells (Fixed 3.15 mm Layout)", "area"),
        ([r for r in imports if r["figure"] == "E/F"], "cells", "level", tuple(COLORS),
         "G. Animation Import and Setup Time", "H. Animation Setup Memory",
         "Cells (16 Sections per Cell)", "rss_peak_delta_mib"),
        (renders, "cells", "recording", tuple(COLORS),
         "I. EEVEE Frame Render Time", "J. Rendering Memory",
         "Cells (16 Sections per Cell)", "rss_render_peak_delta_mib"),
    )
    for col, (rows, xkey, levelkey, levels, top, bottom, xlabel, memorykey) in enumerate(columns):
        xs = sorted({r[xkey] for r in rows})
        for ri, title in enumerate((top, bottom)):
            ax = axes[ri, col]
            area = col == 2 and ri == 1
            if area:
                slot = ax.get_subplotspec()
                ax.remove()
                roundtrip_axes(fig, slot, rows)
                continue
            for level in levels:
                groups = [[r for r in rows if r[xkey] == x and r[levelkey] == level] for x in xs]
                metric = "seconds" if ri == 0 else memorykey
                summaries = [summary([r[metric] for r in group]) for group in groups]
                centers = [s[0] for s in summaries]
                bounds = [[s[1] for s in summaries], [s[2] for s in summaries]]
                ax.errorbar(xs, centers, yerr=bounds, fmt="o-", ms=3, lw=1.5,
                            elinewidth=1, capsize=2, color=COLORS[level], label=level)
            set_panel_title(ax, title, fontsize=11.5, pad=14)
            ax.set_ylim(bottom=0)
            ax.grid(alpha=.22)
            ax.tick_params(axis="both", labelsize=9.5)
            ax.set_xscale("linear")
            ax.set_xticks(xs)
            ax.set_xlim(0, max(xs)*1.04)
            ax.tick_params(axis="x", labelrotation=55)
            ax.set_ylabel("Seconds / Frame" if ri == 0 and col == 4 else
                          "Seconds" if ri == 0 else "Additional RAM (MiB)", fontsize=10.5)
            if ri == 0:
                ax.legend(title="Interaction Level" if col < 3 else "Animation Granularity",
                          frameon=False, fontsize=9.5, title_fontsize=9.5, loc="upper left")
            else:
                ax.set_xlabel(xlabel, fontsize=10.5, labelpad=8)
    fig.subplots_adjust(left=.055, right=.99, top=.93, bottom=.12, wspace=.40, hspace=.40)
    output = HERE / "figures/figures_a_to_j"
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(str(output.with_suffix("."+suffix)), dpi=220)
    print(output.with_suffix(".png"))


if __name__ == "__main__":
    main()
