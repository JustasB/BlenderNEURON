"""Combine the latest optimized import and native EEVEE measurements."""

import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = {"Cell": "#0072B2", "Section": "#E69F00", "3D Segment": "#009E73"}


HERE = Path(__file__).resolve().parent


def main():
    imports = json.loads((HERE / "results/production_optimized_a_f_minmax/results.json").read_text())["records"]
    assert len(imports) == 195, "Complete all five A–F repeats before plotting"
    renders = json.loads((HERE / "results/eevee_g_h_native_minmax/results.json").read_text())["records"]
    fig, axes = plt.subplots(2, 4, figsize=(17, 8))
    columns = (
        ("A/B", "cells", "Cells (16 Sections per Cell)", "Static Import Time", "Static Import Memory"),
        ("C/D", "sections", "Sections per Cell (8 Cells)", "Static Import Time", "Static Import Memory"),
        ("E/F", "cells", "Cells (16 Sections per Cell)", "Animation Import and Setup Time", "Animation Setup Memory"),
        (None, "cells", "Cells (16 Sections per Cell)", "EEVEE Frame Render Time", "Rendering Memory"),
    )
    for col, (group, xkey, xlabel, top, bottom) in enumerate(columns):
        rows = [r for r in imports if r["figure"] == group] if group else renders
        levels = ("Cell", "Section") if col < 2 else tuple(COLORS)
        xs = sorted({r[xkey] for r in rows})
        for row, title in enumerate((top, bottom)):
            ax = axes[row, col]
            metric = ("seconds" if row == 0 else
                      "rss_peak_delta_mib" if group else "rss_render_peak_delta_mib")
            for level in levels:
                level_key = "level" if group else "recording"
                values = [[r[metric] for r in rows if r[xkey] == x and r[level_key] == level] for x in xs]
                assert all(len(v) == 5 for v in values)
                centers = [statistics.median(v) for v in values]
                ax.errorbar(xs, centers,
                            yerr=[[m-min(v) for m, v in zip(centers, values)],
                                  [max(v)-m for m, v in zip(centers, values)]],
                            fmt="o-", ms=3, lw=1.5, elinewidth=1, capsize=2.5,
                            color=COLORS[level], label=level)
            letter = "ABCDEFGH"[col * 2 + row]
            ax.set_title(f"{letter}. {title}", loc="left", fontsize=11, pad=12)
            ax.set_ylabel("Seconds / Frame" if col == 3 and row == 0 else "Seconds" if row == 0 else "Additional RAM (MiB)")
            ax.set_ylim(bottom=0)
            ax.set_xticks(xs)
            ax.set_xlim(min(xs)-max(xs)*.025, max(xs)*1.04)
            ax.grid(alpha=.22)
            ax.tick_params(axis="both", labelsize=9)
            if col == 0:
                ax.tick_params(axis="x", labelrotation=55)
            if row == 0:
                ax.legend(title="Interaction Level" if col < 2 else "Animation Granularity",
                          frameon=False, fontsize=9, title_fontsize=9, loc="upper left")
            else:
                ax.set_xlabel(xlabel, labelpad=9)
    fig.subplots_adjust(left=.065, right=.99, top=.94, bottom=.19, wspace=.35, hspace=.32)
    fig.text(.065, .075,
             "All Panels: Median and Min–Max of Five Independent Runs per Condition. A–F: Docker / Blender 4.0.2.\n"
             "G–H: Native macOS / Metal / Blender 5.2; Render Time Averages 12 Warmed Frames per Run.\n"
             "Rendering: 1800 × 900, 64 EEVEE Samples, Add-on Neon Glow. Memory: Additional Process RAM, Not Dedicated GPU VRAM.",
             fontsize=10, va="center", linespacing=1.5)
    output = HERE / "figures/figures_a_to_h"
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(str(output.with_suffix("." + suffix)), dpi=220)
    print(output.with_suffix(".png"))


if __name__ == "__main__":
    main()
