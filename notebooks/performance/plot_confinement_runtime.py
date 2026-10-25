"""Panel F: runtime and round-trip surface-area error vs section length."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from confinement import ANGLES, LENGTHS
from confinement_config import SETUP

HERE=Path(__file__).resolve().parent


def runtime_summary(rows):
    assert len(rows)==100 and all(r['setup']==SETUP for r in rows)
    summary=[]
    for length in sorted(LENGTHS):
        trials=[r for r in rows if r['max_length_um']==length]
        assert {(r['angle'],r['seed']) for r in trials}=={(a,s) for a in ANGLES for s in range(5)}
        assert len(trials)==20
        stats=dict(max_section_length_um=length,angles=len(ANGLES),seeds_per_angle=5,trials=len(trials))
        stats['whole_cell_area_error_percent_max']=max(
            abs(r['geometry']['area']['relative_change_percent']) for r in trials)
        for key in ('setup_seconds','confine_seconds','export_seconds','split_objects','processing_seconds'):
            values=[r['setup_seconds']+r['confine_seconds'] if key=='processing_seconds' else r[key] for r in trials]
            stats[key+'_mean']=float(np.mean(values))
            stats[key+'_sd']=float(np.std(values,ddof=1))
            stats[key+'_min']=float(min(values))
            stats[key+'_max']=float(max(values))
        summary.append(stats)
    return summary


def draw_runtime_panel(ax,rows):
    summary=runtime_summary(rows)
    runtime=ax.errorbar([r['max_section_length_um'] for r in summary],
                [r['processing_seconds_mean']*1000 for r in summary],
                yerr=[r['processing_seconds_sd']*1000 for r in summary],
                marker='o',color='#1764ab',capsize=4,lw=1.8,label='Runtime: mean ± SD')
    lengths=sorted(LENGTHS)
    counts=[next(r['split_objects_mean'] for r in summary if r['max_section_length_um']==l) for l in lengths]
    ax.set_xticks(lengths)
    ax.set(xlabel='Maximum section length (µm)',ylabel='Splitting + confinement time (ms)',ylim=(0,None))
    ax.set_title('F  Runtime and surface-area preservation\n4 angles × 5 seeds pooled per length',loc='left',fontsize=11)
    ax.tick_params(axis='y',colors='#1764ab')
    ax.yaxis.label.set_color('#1764ab')
    area_ax=ax.twinx()
    area_line,=area_ax.plot(lengths,[r['whole_cell_area_error_percent_max'] for r in summary],
                            color='#c56816',marker='s',ls='--',lw=1.6,
                            label='Whole-cell area error: maximum')
    area_ax.set_ylabel('Maximum absolute surface-area error (%)',color='#c56816')
    area_ax.tick_params(axis='y',colors='#c56816')
    area_ax.ticklabel_format(axis='y',style='plain',useOffset=False)
    area_ax.set_ylim(0,.001)
    ax.legend(handles=[runtime,area_line],loc='upper right',fontsize=8,frameon=False)
    ax.grid(axis='y',alpha=.2)
    top=ax.secondary_xaxis('top')
    top.set_xticks(lengths)
    top.set_xticklabels([f'{n:g}' for n in counts])
    top.set_xlabel('Blender objects after splitting',fontsize=10)
    return summary


def main():
    directory=HERE/'results/confinement_z_up'
    rows=json.loads((directory/'results.json').read_text())['records']
    fig,ax=plt.subplots(figsize=(8.2,5.8),constrained_layout=True)
    summary=draw_runtime_panel(ax,rows)
    with (directory/'runtime_summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    for suffix in ('png','pdf','svg'):
        fig.savefig(HERE/'figures/confinement_panels'/('F_confinement_runtime.'+suffix),dpi=200,facecolor='white')
    plt.close(fig)


if __name__=='__main__':
    main()
