"""Compose MC4 A–F from measured spherical-shell confinement trials."""
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
ROOT=Path(__file__).resolve().parent
ANGLES=(5,10,15,25);LENGTHS=(200,100,75,50,25)
COLORS={'soma':'#a329a3','dend':'#1764ab','apic':'#df7515','axon':'#159447'}
def draw_cell(ax,case):
    ax.set_axis_off()
    source=plt.imread(str(ROOT/('MC4_'+case+'_ZY.png')))
    # Shared tighter orthographic crop: preserve every cell and use one scale.
    crop=source[160:660,0:1167]
    main=ax.inset_axes([0,.10,1,.62])
    main.imshow(crop);main.set_axis_off();main.set_zorder(0)
    record=json.loads((ROOT/('MC4_'+case+'_result.json')).read_text())
    title='Baseline' if case=='A' else '%d° / %d µm'%(record['angle'],record['max_length_um'])
    ax.text(.035,.95,r'$\mathbf{'+case+r'}$  '+title,transform=ax.transAxes,fontsize=14,va='top',zorder=3)
    ax.text(.035,.865,'Lateral dendrite points outside: %.1f%%'%record['containment_after']['outside_percent'],transform=ax.transAxes,fontsize=10,va='top',zorder=3)
    # Crop width is converted from the source camera's 1,800 µm span.
    bar_start,bar_y,bar_length_um,view_width_um=.035,.05,200.,1800.*crop.shape[1]/source.shape[1]
    bar_end=bar_start+bar_length_um/view_width_um
    ax.plot([bar_start,bar_end],[bar_y,bar_y],transform=ax.transAxes,color='black',lw=2.5,zorder=3,solid_capstyle='butt')
    for x in (bar_start,bar_end):
        ax.plot([x,x],[bar_y-.008,bar_y+.008],transform=ax.transAxes,color='black',lw=1.2,zorder=3)
    ax.text((bar_start+bar_end)/2,bar_y+.02,'200 µm',transform=ax.transAxes,fontsize=10,ha='center',va='bottom',zorder=3,bbox=dict(facecolor='white',edgecolor='none',pad=1))
    snapshot=json.loads((ROOT/('MC4_'+case+'_result.json')).read_text())['after']
    for left,i,j,title in [(.62,0,1,'Top-down XY'),(.825,0,2,'Side XZ')]:
        inset=ax.inset_axes([left,.715,.165,.245])
        if j==2:
            x=np.linspace(-850,850,301);inner=np.sqrt(1000**2-x*x)-1000;outer=np.sqrt(1100**2-x*x)-1000
            inset.fill_between(x,inner,outer,color='.93',zorder=0)
            inset.plot(x,inner,color='.7',lw=.4);inset.plot(x,outer,color='.7',lw=.4)
        for name,section in snapshot.items():
            points=np.array(section['points']);kind=name.split('.')[-1].split('[')[0]
            inset.plot(points[:,i],points[:,j],color=COLORS[kind],lw=.55 if kind!='soma' else 1.5)
        inset.set_xlim(-850,850);inset.set_ylim((-850,850) if j==1 else (-650,350));inset.set_aspect('equal',adjustable='box')
        inset.set_xticks([-500,0,500]);inset.set_yticks([-500,0,500] if j==1 else [-500,0]);inset.tick_params(labelsize=6,length=1.5,pad=1)
        inset.set_xlabel('X (µm)',fontsize=7,labelpad=1);inset.set_ylabel(('Y' if j==1 else 'Z')+' (µm)',fontsize=7,labelpad=1)
        for spine in inset.spines.values():spine.set_color('.7');spine.set_linewidth(.5)
        inset.set_title(title,fontsize=8,pad=3)
def summaries(rows,partial=False):
    seeds=sorted({r['seed'] for r in rows})
    keys={(r['angle'],r['max_length_um'],r['seed']) for r in rows}
    assert len(keys)==len(rows)
    expected={(a,l,s) for a in ANGLES for l in LENGTHS for s in range(25)}
    assert keys<=expected
    if not partial:
        assert seeds==list(range(25)) and len(rows)==500 and keys==expected
    baseline=json.loads((ROOT/'MC4_A_result.json').read_text())['before']
    assert all(r['before']==baseline and r['setup']==rows[0]['setup'] and r['topology_unchanged'] and r['non_target_validation_passed'] for r in rows)
    heat=[]
    for length in LENGTHS:
        for angle in ANGLES:
            trials=[r for r in rows if r['angle']==angle and r['max_length_um']==length]
            assert len(trials)>=2
            record=dict(angle=angle,max_length_um=length,seeds=len(trials))
            for metric in ['points_outside_percent','cable_outside_percent']:
                values=[r['containment_after'][metric] for r in trials]
                for label,v in [('mean',np.mean(values)),('sd',np.std(values,ddof=1)),('median',np.median(values)),('p5',np.percentile(values,5)),('p95',np.percentile(values,95)),('min',min(values)),('max',max(values))]:record[metric+'_'+label]=float(v)
            heat.append(record)
    runtime=[]
    for length in sorted(LENGTHS):
        trials=[r for r in rows if r['max_length_um']==length]
        assert partial or len(trials)==100
        record=dict(max_length_um=length,trials=len(trials),angles=4,seeds_per_angle_min=min(sum(r['angle']==a for r in trials) for a in ANGLES),seeds_per_angle_max=max(sum(r['angle']==a for r in trials) for a in ANGLES),area_error_percent_max=max(abs(r['geometry']['area']['relative_change_percent']) for r in trials),area_tolerance_failures=sum(not r['area_validation_passed'] for r in trials),split_objects=trials[0]['split_objects'])
        assert all(r['split_objects']==record['split_objects'] for r in trials)
        values=[1000*(r['setup_seconds']+r['confine_seconds']) for r in trials]
        for label,v in [('mean',np.mean(values)),('sd',np.std(values,ddof=1)),('median',np.median(values)),('p5',np.percentile(values,5)),('p95',np.percentile(values,95)),('min',min(values)),('max',max(values))]:record['runtime_ms_'+label]=float(v)
        runtime.append(record)
    return heat,runtime

def draw_e(ax,heat,rows):
    values=np.array([r['points_outside_percent_mean'] for r in heat]).reshape(5,4)
    baseline=round(rows[0]['containment_before']['points_outside_percent'],1)
    image=ax.imshow(values,vmin=0,vmax=baseline,cmap='magma_r',aspect='auto')
    for j in range(5):
        for i in range(4):
            row=heat[j*4+i];rgba=image.cmap(image.norm(values[j,i]));lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
            label='%.1f%%\n[%.1f–%.1f]'%(values[j,i],row['points_outside_percent_p5'],row['points_outside_percent_p95'])
            if len(rows)<500:label+='\nn=%d'%row['seeds']
            ax.text(i,j,label,ha='center',va='center',fontsize=9,color='black' if lum>.5 else 'white')
    ax.set_xticks(range(4));ax.set_xticklabels(ANGLES);ax.set_yticks(range(5));ax.set_yticklabels(LENGTHS)
    ax.set(xlabel='Maximum bend angle (degrees)',ylabel='Maximum section length (µm)')
    status='25 seeds' if len(rows)==500 else 'INTERIM; n shown per tile'
    ax.set_title((r'$\mathbf{E}$  Lateral dendrite points outside spherical shell'+'\nMean [5th–95th percentile]; '+status+'\nBaseline: %.1f%% outside')%rows[0]['containment_before']['points_outside_percent'],loc='left',fontsize=11)
    bar=ax.figure.colorbar(image,ax=ax,label='Mean points outside (%)',shrink=.8)
    bar.set_ticks([0,10,20,30,40,baseline])
    bar.set_ticklabels(['0','10','20','30','40','%.1f'%baseline])

def draw_f(ax,runtime,rows):
    lengths=sorted(LENGTHS);times=[[1000*(r['setup_seconds']+r['confine_seconds']) for r in rows if r['max_length_um']==length] for length in lengths]
    ax.boxplot(times,positions=lengths,widths=9,whis=(5,95),patch_artist=True,manage_ticks=False,boxprops=dict(facecolor='#b7d4ed',edgecolor='#1764ab'),medianprops=dict(color='#1764ab',lw=1.8),whiskerprops=dict(color='#1764ab'),capprops=dict(color='#1764ab'),flierprops=dict(marker='.',markersize=3,markeredgecolor='#1764ab',alpha=.4))
    ax.set_xticks(lengths);ax.set(xlabel='Maximum section length (µm)',ylabel='Splitting + confinement time (ms)',ylim=(0,None));ax.tick_params(axis='y',colors='#1764ab');ax.yaxis.label.set_color('#1764ab');ax.grid(axis='y',alpha=.2)
    status='4 angles × 25 seeds pooled per length' if len(rows)==500 else 'INTERIM; %d–%d runs/length, uneven angle counts'%(min(r['trials'] for r in runtime),max(r['trials'] for r in runtime))
    ax.set_title(r'$\mathbf{F}$  Runtime and round-trip surface-area error'+'\n'+status+'\nBoxes: IQR; whiskers: 5th–95th percentile',loc='left',fontsize=11)
    right=ax.twinx();line,=right.plot(lengths,[r['area_error_percent_max'] for r in runtime],color='#c56816',marker='s',ls='--',lw=1.6,label='Whole-cell area error: maximum')
    right.set_ylabel('Maximum absolute surface-area error (%)',color='#c56816');right.tick_params(axis='y',colors='#c56816');right.ticklabel_format(axis='y',style='plain',useOffset=False);right.set_ylim(0,max(.0012,1.2*max(r['area_error_percent_max'] for r in runtime)))
    ax.legend(handles=[Patch(facecolor='#b7d4ed',edgecolor='#1764ab',label='Runtime'),line],loc='upper right',fontsize=7,frameon=False)
    top=ax.secondary_xaxis('top');top.set_xticks(lengths);top.set_xticklabels([r['split_objects'] for r in runtime]);top.set_xlabel('Blender objects after splitting',fontsize=10)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--partial',action='store_true');parser.add_argument('--results',type=Path,default=ROOT/'results/results.json');args=parser.parse_args()
    data=json.loads(args.results.read_text())
    rows=data['records']
    # Compact plotting inputs share one baseline instead of 500 copies.
    if 'baseline' in data:
        for row in rows:
            row['before']=data['baseline']
    heat,runtime=summaries(rows,partial=args.partial)
    prefix='interim_' if args.partial else ''
    out=ROOT/'figures';out.mkdir(exist_ok=True)
    for name,records in [('heatmap_summary',heat),('runtime_summary',runtime)]:
        with (ROOT/'results'/(prefix+name+'.csv')).open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]),lineterminator='\n');writer.writeheader();writer.writerows(records)
    for name,draw,data in [('E_MC4_heatmap',draw_e,heat),('F_MC4_runtime_area',draw_f,runtime)]:
        fig,ax=plt.subplots(figsize=(8.2,5.8),constrained_layout=True);draw(ax,data,rows)
        for ext in ['png','pdf','svg']:fig.savefig(str(out/(prefix+name+'.'+ext)),dpi=200,facecolor='white')
        plt.close(fig)
    fig=plt.figure(figsize=(19,10),constrained_layout=True);grid=fig.add_gridspec(2,3,width_ratios=(1,1,1.15))
    for index,case in enumerate('ABCD'):draw_cell(fig.add_subplot(grid[index//2,index%2]),case)
    draw_e(fig.add_subplot(grid[0,2]),heat,rows);draw_f(fig.add_subplot(grid[1,2]),runtime,rows)
    fig.suptitle(('INTERIM — %d/500 trials | '%len(rows) if args.partial else '')+'Mitral Cell confinement within an idealized spherical EPL band',fontsize=15)
    for ext in ['png','pdf','svg']:fig.savefig(str(out/(prefix+'MC4_confinement_A_to_F.'+ext)),dpi=180,facecolor='white')
    plt.close(fig)
    report=dict(trials=len(rows),area_tolerance_percent=.001,area_tolerance_failures=sum(not r['area_validation_passed'] for r in rows),max_area_error_percent=max(abs(r['geometry']['area']['relative_change_percent']) for r in rows),max_non_target_polyline_distance_um=max(r['non_target_max_polyline_distance_um'] for r in rows),setup=rows[0]['setup'])
    (ROOT/'results'/(prefix+'validation_summary.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
