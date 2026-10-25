"""Standalone panel E: seed-averaged confinement success and supporting table."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from confinement_config import SETUP
from confinement import ANGLES, LENGTHS

HERE = Path(__file__).resolve().parent


def main():
    rows = json.loads((HERE/'results/confinement_z_up/results.json').read_text())['records']
    assert all(r['setup'] == SETUP and r['before'] == rows[0]['before'] for r in rows)
    seeds = sorted({r['seed'] for r in rows})
    assert seeds == list(range(5)), 'Expected five seeds (0–4)'
    assert len(rows) == len(ANGLES)*len(LENGTHS)*len(seeds), 'Unexpected trial count'
    summary = []
    for length in LENGTHS:
        for angle in ANGLES:
            trials = [r for r in rows if r['angle'] == angle and r['max_length_um'] == length]
            assert sorted(r['seed'] for r in trials) == seeds, 'Incomplete sweep'
            stats = dict(angle_degrees=angle, max_section_length_um=length, seeds=len(seeds))
            for metric in ('points_outside_percent', 'cable_outside_percent', 'uniform_points_outside_percent'):
                values = [r['containment']['target']['dendrites']['after'][metric] for r in trials]
                for name, value in (('mean', np.mean(values)), ('sd', np.std(values, ddof=1)),
                                    ('min', min(values)), ('max', max(values))):
                    stats[metric+'_'+name] = float(value)
            stats['mean_split_objects'] = float(np.mean([r['split_objects'] for r in trials]))
            stats['mean_confine_seconds'] = float(np.mean([r['confine_seconds'] for r in trials]))
            summary.append(stats)
    out = HERE/'figures/confinement_panels'
    with (HERE/'results/confinement_z_up/summary.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    values = np.array([s['points_outside_percent_mean'] for s in summary]).reshape(len(LENGTHS), len(ANGLES))
    spreads = np.array([s['points_outside_percent_sd'] for s in summary]).reshape(values.shape)
    fig, ax = plt.subplots(figsize=(8.2, 5.8), constrained_layout=True)
    im = ax.imshow(values, vmin=0, vmax=100, cmap='magma_r', aspect='auto')
    for j, row in enumerate(values):
        for i, value in enumerate(row):
            rgba = im.cmap(im.norm(value))
            luminance = .2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
            ax.text(i, j, f'{value:.1f} ± {spreads[j, i]:.1f}%', ha='center', va='center',
                    color='black' if luminance > .5 else 'white', fontsize=11)
    ax.set_xticks(range(len(ANGLES)))
    ax.set_xticklabels([f'{a:g}' for a in ANGLES])
    ax.set_yticks(range(len(LENGTHS)))
    ax.set_yticklabels([f'{l:g}' for l in LENGTHS])
    ax.set(xlabel='Maximum bend angle (degrees)', ylabel='Maximum section length (µm)')
    baseline = rows[0]['containment']['target']['dendrites']['before']['points_outside_percent']
    ax.set_title(f'E  Dendrite 3D points outside target zone\nMean ± SD across {len(seeds)} seeds; baseline {baseline:.1f}% outside', loc='left')
    fig.colorbar(im, ax=ax, label='Mean points outside (%)')
    for extension in ('png', 'pdf', 'svg'):
        fig.savefig(out/('E_confinement_heatmap.'+extension), dpi=200, facecolor='white')
    plt.close(fig)
    print('Baseline outside: %.2f%%; after range %.2f–%.2f%%' % (baseline, values.min(), values.max()))


if __name__ == '__main__':
    main()
