"""Render the six-panel confinement figure from saved Docker measurements."""
import argparse
import json
import hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from confinement_config import SETUP, PANEL_SPECS, FIGURE_LAYOUT

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results-dir', type=Path, default=HERE/'results/confinement_z_up')
    p.add_argument('--panels-dir', type=Path, default=HERE/'figures/confinement_panels')
    args = p.parse_args()
    rows = json.loads((args.results_dir/'results.json').read_text())['records']
    if any(r.get('setup') != SETUP for r in rows):
        raise ValueError('Results do not match the reviewed Z-up setup/style; rerun the assessment')
    manifest = json.loads((HERE/'results/confinement_panels/manifest.json').read_text())
    if manifest['setup'] != SETUP or manifest['layout'] != FIGURE_LAYOUT:
        raise ValueError('Approved A–D panels do not match the sweep setup/layout')
    for panel in manifest['panels']:
        if hashlib.sha256((args.panels_dir/panel['file']).read_bytes()).hexdigest() != panel['sha256']:
            raise ValueError('Approved panel changed: '+panel['file'])
    fig = plt.figure(figsize=(18, 9), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, width_ratios=(1, 1, 1.15))
    for i, (letter, stem, filename, label) in enumerate(PANEL_SPECS):
        ax = fig.add_subplot(grid[i // 2, i % 2])
        ax.imshow(plt.imread(args.panels_dir/filename))
        ax.set_axis_off()
        ax.set_title(f'{letter}  {label}', loc='left', fontsize=11)
    ax = fig.add_subplot(grid[0, 2])
    angles = sorted({r['angle'] for r in rows})
    lengths = sorted({r['max_length_um'] for r in rows}, reverse=True)
    values = np.array([[np.mean([r['containment']['slab']['dendrites']['after']['points_outside_percent']
                                for r in rows if r['angle'] == a and r['max_length_um'] == l])
                        for a in angles] for l in lengths])
    spreads = np.array([[np.std([r['containment']['slab']['dendrites']['after']['points_outside_percent']
                                  for r in rows if r['angle'] == a and r['max_length_um'] == l], ddof=1)
                          for a in angles] for l in lengths])
    im = ax.imshow(values, vmin=0, vmax=100, cmap='magma_r', aspect='auto')
    for j in range(len(lengths)):
        for i in range(len(angles)):
            ax.text(i, j, f'{values[j, i]:.1f} ± {spreads[j, i]:.1f}%', ha='center', va='center', color='white' if values[j, i] > 50 else 'black')
    ax.set_xticks(range(len(angles)))
    ax.set_xticklabels([f'{a:g}' for a in angles])
    ax.set_yticks(range(len(lengths)))
    ax.set_yticklabels([f'{l:g}' for l in lengths])
    ax.set(xlabel='Maximum bend angle (degrees)', ylabel='Maximum piece length (µm)')
    baseline = rows[0]['containment']['slab']['dendrites']['before']['points_outside_percent']
    nseeds = len({r['seed'] for r in rows})
    ax.set_title(f'E  Dendritic n3d points outside planes\nMean ± SD over {nseeds} seeds; before: {baseline:.1f}%', loc='left', fontsize=11)
    fig.colorbar(im, ax=ax, label='Outside (%)', shrink=.8)
    ax = fig.add_subplot(grid[1, 2])
    from plot_confinement_runtime import draw_runtime_panel
    draw_runtime_panel(ax, rows)
    fig.suptitle('Binary-tree cell confinement between parallel planes', fontsize=15)
    out = HERE/'figures'
    out.mkdir(exist_ok=True)
    for suffix in ('png', 'pdf', 'svg'):
        fig.savefig(out/f'confinement_a_to_f.{suffix}', dpi=180, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
