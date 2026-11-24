"""Fresh-process MC4 spherical-shell confinement sweep; no rendering in timers."""
import argparse,hashlib,json,math,os,random,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ANGLES=(5,10,15,25)
LENGTHS=(200,100,75,50,25)
SETUP=dict(cell='MC4',transform='TransformMC4',center_um=[0,0,-1000],radii_um=[1000,1100],sphere_segments=256,sphere_rings=128,pattern='*dend*',height_fractions=[0,1],passes=1,geometry_only=True,
           source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['MC4.hoc','MCTransforms.py']})
def measure(snapshot):
    selected=[s for n,s in snapshot.items() if '.dend' in n]
    points=[p for s in selected for p in s['points']]
    inside=sum(1000<=math.sqrt(x*x+y*y+(z+1000)**2)<=1100 for x,y,z in points)
    total_length=inside_length=0.
    for s in selected:
        for p,q in zip(s['points'],s['points'][1:]):
            p=[p[0],p[1],p[2]+1000];q=[q[0],q[1],q[2]+1000]
            v=[b-a for a,b in zip(p,q)];a=sum(x*x for x in v)
            if a==0:continue
            length=math.sqrt(a);total_length+=length;b=2*sum(x*y for x,y in zip(p,v));cuts=[0.,1.]
            for radius in (1000,1100):
                c=sum(x*x for x in p)-radius**2;disc=b*b-4*a*c
                if disc>=0:
                    for t in ((-b-math.sqrt(disc))/(2*a),(-b+math.sqrt(disc))/(2*a)):
                        if 0<t<1:cuts.append(t)
            cuts.sort()
            for start,end in zip(cuts,cuts[1:]):
                middle=(start+end)/2;r=math.sqrt(sum((x+middle*y)**2 for x,y in zip(p,v)))
                if 1000<=r<=1100:inside_length+=length*(end-start)
    return dict(points=len(points),points_inside=inside,points_outside_percent=100*(1-inside/len(points)),cable_length_um=total_length,cable_inside_um=inside_length,cable_outside_percent=100*(1-inside_length/total_length))
def worker(args):
    sys.path.insert(0,'/BlenderNEURON');sys.path.insert(0,'/BlenderNEURON/notebooks/performance')
    import bpy,numpy as np
    import performance_eval as perf
    from export_roundtrip import remote_snapshot
    perf.HERE=ROOT;perf.clear_scene()
    def experiment(group,node):
        before=remote_snapshot(node)
        spheres=[]
        for radius in (1000,1100):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=256,ring_count=128,radius=radius,location=(0,0,-1000))
            ob=bpy.context.object;ob.name='Inner_R1000' if radius==1000 else 'Outer_R1100';spheres.append(ob)
        settings=group.ui_group.layer_confiner_settings
        settings.start_mesh,settings.end_mesh=spheres
        settings.max_bend_angle=args.angle;settings.max_section_length=args.length;settings.seed=args.seed
        settings.height_min=0;settings.height_max=1;settings.moveable_sections_pattern='*dend*'
        start=time.perf_counter();group.setup_confiner();setup_seconds=time.perf_counter()-start
        objects=len(group.view.containers)
        start=time.perf_counter();group.confine_between_layers();bpy.context.view_layer.update();confine_seconds=time.perf_counter()-start
        start=time.perf_counter()
        assert bpy.ops.blenderneuron.update_groups_with_view_data()=={'FINISHED'}
        assert bpy.ops.blenderneuron.export_groups()=={'FINISHED'}
        export_seconds=time.perf_counter()-start
        after=remote_snapshot(node)
        assert set(before)==set(after)
        topology=all(before[n]['parent']==after[n]['parent'] and before[n]['nseg']==after[n]['nseg'] for n in before)
        geometry={}
        for key in ('area','length','volume'):
            pre=sum(s[key] for s in before.values());post=sum(s[key] for s in after.values())
            geometry[key]=dict(before=pre,after=post,relative_change_percent=100*(post-pre)/pre,max_section_relative_change_percent=max(abs(100*(after[n][key]-before[n][key])/before[n][key]) for n in before))
        def distance(points,polyline):
            a=np.array(polyline[:-1]);v=np.diff(np.array(polyline),axis=0);den=(v*v).sum(axis=1)
            return max(np.sqrt(((a+np.clip(((np.array(p)-a)*v).sum(axis=1)/np.maximum(den,1e-30),0,1)[:,None]*v-np.array(p))**2).sum(axis=1)).min() for p in points)
        non_target=max(max(distance(before[n]['points'],after[n]['points']),distance(after[n]['points'],before[n]['points'])) for n in before if '.dend' not in n)
        result=dict(setup=SETUP,angle=args.angle,max_length_um=args.length,seed=args.seed,sections=len(before),split_objects=objects,setup_seconds=setup_seconds,confine_seconds=confine_seconds,export_seconds=export_seconds,geometry=geometry,topology_unchanged=topology,non_target_max_polyline_distance_um=float(non_target),
                    area_validation_passed=abs(geometry['area']['relative_change_percent'])<=.001,non_target_validation_passed=bool(non_target<.001),area_tolerance_percent=.001,
                    before=before,after=after,containment_before=measure(before),containment_after=measure(after),blender=bpy.app.version_string)
        args.output.write_text(json.dumps(result,separators=(',',':')))
    perf.import_live_neuron_group(1,49,'Section','Section',False,after_import=experiment)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',action='store_true');p.add_argument('--angle',type=int);p.add_argument('--length',type=int);p.add_argument('--seed',type=int);p.add_argument('--output',type=Path);p.add_argument('--seeds',type=int,default=25)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    if args.worker:return worker(args)
    # Keep newly measured geometry snapshots separate from compact plotting inputs.
    directory=ROOT/'results';directory.mkdir(exist_ok=True);aggregate=directory/'raw_results.json'
    cache={}
    if aggregate.exists():
        existing=json.loads(aggregate.read_text());assert existing['setup']==SETUP
        cache={(r['angle'],r['max_length_um'],r['seed']):r for r in existing['records']}
    trials=[(a,l,s) for a in ANGLES for l in LENGTHS for s in range(args.seeds)];random.Random(20261121).shuffle(trials)
    env=os.environ.copy();env.pop('COVERAGE_PROCESS_START',None)
    for index,(angle,length,seed) in enumerate(trials):
        key=(angle,length,seed);output=directory/('a%d_l%d_s%d.json'%key)
        if key not in cache:
            if not output.exists():
                command=['blender','--background','--python-exit-code','1','--python',str(Path(__file__).resolve()),'--','--worker','--angle',str(angle),'--length',str(length),'--seed',str(seed),'--output',str(output)]
                with output.with_suffix('.log').open('w') as stream:subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=300)
            row=json.loads(output.read_text());assert row['setup']==SETUP
            cache[key]=row
            tmp=aggregate.with_suffix('.tmp');tmp.write_text(json.dumps(dict(setup=SETUP,records=list(cache.values())),separators=(',',':')));os.replace(str(tmp),str(aggregate))
        print('%d/%d angle=%d length=%d seed=%d area_pass=%s'%(index+1,len(trials),angle,length,seed,cache[key]['area_validation_passed']),flush=True)
if __name__=='__main__':main()
