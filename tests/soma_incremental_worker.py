"""Incremental-cache identity, native face preservation and segment-band coverage."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from collections import Counter
import bpy
import blenderneuron
blenderneuron.register()
from mathutils import Vector
from blenderneuron.blender.blenderroot import BlenderSection
from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
from blenderneuron.blender.views.groupobjectview import GroupObjectView
from blenderneuron.blender.somadisplay import TAG, attach, detach, refresh


def section(name, coords, radii):
    result = BlenderSection()
    result.name, result.coords, result.radii = name, coords, radii
    result.point_count, result.nseg = len(radii), 3
    return result


def faces(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        result = []
        for face in mesh.polygons:
            vertices = tuple(sorted(tuple(round(v,5) for v in mesh.vertices[i].co) for i in face.vertices))
            result.append((face.material_index, vertices))
        return result
    finally:
        evaluated.to_mesh_clear()


def cache_state(obj):
    return [(bpy.data.objects[entry['cache']].data.as_pointer(),
             tuple(tuple(v.co) for v in bpy.data.objects[entry['cache']].data.vertices),
             tuple(p.material_index for p in bpy.data.objects[entry['cache']].data.polygons))
            for entry in json.loads(obj[TAG])['spheres']]


from blenderneuron.blender import somadisplay
build_counts = Counter()
actual_sphere = somadisplay._sphere

def counted_sphere(mesh, obj, result):
    build_counts[mesh.as_pointer()] += 1
    actual_sphere(mesh, obj, result)

somadisplay._sphere = counted_sphere

for recording in ('Cell', 'Section', '3D Segment'):
    group = BlenderRootGroup('incremental_'+recording, None)
    group.spherize_soma_if_DeqL = False
    group.recording_granularity = recording
    # Tiny first interval and rotated/reversed axes exercise band mapping.
    a = section('a.soma', [0,0,0, .001,0,0, 3,0,0, 10,0,0], [5]*4)
    a.children = [section('a.dend', [10,0,0, 20,1,0], [1,1])]
    b = section('b.soma', [0,40,10, 0,40,7, 0,40,0], [5]*3)
    b.children = [section('b.dend', [0,40,0, 0,40,-10], [1,1])]
    group.roots = {s.name:s for s in (a,b)}
    view = GroupObjectView(group)
    view.frame_view = False
    view.show()
    container = next(iter(view.containers.values()))
    obj = container.object
    original = faces(obj)
    soma_indices = [i for i,s in container.spline_index2section.items() if 'soma' in s.name]
    soma_slots = {obj.data.splines[i].material_index for i in soma_indices}
    unchanged = Counter(vertices for mat,vertices in original if mat not in soma_slots)
    # Native bevel/smoothing/caps and dendrite vertices must be kept exactly.
    modifier = attach(container)
    displayed = faces(obj)
    descriptor = json.loads(obj[TAG])
    sphere_faces = sum(len(bpy.data.objects[e['cache']].data.polygons) for e in descriptor['spheres'])
    assert len(displayed) == len(original)-sum(mat in soma_slots for mat,_ in original)+sphere_faces
    assert not (unchanged-Counter(vertices for _,vertices in displayed))
    state = cache_state(obj)
    counts = build_counts.copy()
    # Dendrite edits do not change or regenerate ANY sphere mesh.
    di = container.name2spline_index['a.dend' if recording != '3D Segment' else 'a.dend[0]']
    point = obj.data.splines[di].bezier_points[1]
    radius = point.radius
    point.radius *= .8
    obj.data.update_tag()
    bpy.context.view_layer.update()
    assert cache_state(obj) == state and build_counts == counts
    point.radius = radius
    obj.data.update_tag()
    bpy.context.view_layer.update()
    # Editing soma A changes only cache A; soma B is untouched and still visible.
    indices = descriptor['spheres'][0]['indices']
    point = obj.data.splines[indices[0]].bezier_points[1]
    radius = point.radius
    point.radius *= .8
    obj.data.update_tag()
    bpy.context.view_layer.update()
    after = cache_state(obj)
    assert after[0] != state[0] and after[1] == state[1]
    assert build_counts[state[0][0]] == counts[state[0][0]]+1
    assert build_counts[state[1][0]] == counts[state[1][0]]
    assert modifier.show_viewport
    assert not bpy.data.objects[descriptor['spheres'][0]['cache']].get('eligible')
    point.radius = radius
    obj.data.update_tag()
    bpy.context.view_layer.update()
    assert cache_state(obj) == state
    counts = build_counts.copy()
    # Renaming the display modifier must not break ownership or eligibility.
    modifier.name = 'Spherical soma appearance'
    refresh([obj])
    assert modifier.show_viewport and cache_state(obj) == state
    modifier.name = TAG
    # Translation must not rebuild local meshes; rotation carries the cache with it.
    obj.location.x += 12
    bpy.context.view_layer.update()
    assert cache_state(obj) == state and build_counts == counts
    obj.rotation_euler.y = .4
    bpy.context.view_layer.update()
    assert cache_state(obj) == state and build_counts == counts
    obj.rotation_euler.y = 0
    obj.location.x -= 12
    bpy.context.view_layer.update()
    # Every interval, even the 0.001um interval, has a correctly bounded band.
    if recording == '3D Segment':
        sphere = bpy.data.objects[descriptor['spheres'][0]['cache']].data
        assert set(p.material_index for p in sphere.polygons) == {0,1,2}
        lo = Vector(a.coords[:3])-container.origin
        direction = (Vector(a.coords[-3:])-Vector(a.coords[:3])).normalized()
        for face in sphere.polygons:
            ts = [(sphere.vertices[i].co-lo).dot(direction)/10 for i in face.vertices]
            lower, upper = ((0,.0001),(.0001,.3),(.3,1))[face.material_index]
            assert min(ts) >= lower-1e-6 and max(ts) <= upper+1e-6
        # Sphere materials are the original animated datablocks in interval order.
        for band,index in enumerate(indices):
            assert sphere.materials[band] == obj.data.materials[obj.data.splines[index].material_index]
    if recording == '3D Segment':
        # Band materials really animate, without rebuilding any geometry cache.
        counts = build_counts.copy()
        for band, material in enumerate(sphere.materials):
            strength = material.node_tree.nodes['Emission'].inputs['Strength']
            view.add_keyframes(material.node_tree, strength.path_from_id('default_value'),
                               [1,2], [band+1,band+10])
        for frame,offset in ((1,1),(2,10),(1,1)):
            bpy.context.scene.frame_set(frame)
            for band,material in enumerate(sphere.materials):
                assert abs(material.node_tree.nodes['Emission'].inputs['Strength'].default_value-(band+offset)) < 1e-6
            assert build_counts == counts
    # Slot-count changes must disable filtering rather than sample a wrong mask.
    extra = bpy.data.materials.new('extra')
    obj.data.materials.append(extra)
    refresh([obj])
    assert not modifier.show_viewport
    obj.data.materials.pop(index=len(obj.data.materials)-1)
    refresh([obj])
    assert modifier.show_viewport
    # Upgrade an earlier scene descriptor without changing any original points.
    before_upgrade = {name: container.get_spline_3d_data(name) for name in container.name2spline_index}
    old = json.loads(obj[TAG])
    del old['spheres']
    obj[TAG] = json.dumps(old)
    refresh([obj])
    assert 'spheres' in json.loads(obj[TAG])
    assert before_upgrade == {name: container.get_spline_3d_data(name) for name in container.name2spline_index}
    assert len(faces(obj)) == len(displayed)
    view.remove()
# Dense pt3d sampling in cell/section mode must not create hundreds of bands.
group = BlenderRootGroup('dense_soma', None)
group.recording_granularity = 'Cell'
root = section('dense.soma', [v for i in range(101) for v in (i/10,0,0)], [5]*101)
group.roots = {root.name:root}
view = GroupObjectView(group)
view.frame_view = False
view.show()
obj = next(iter(view.containers.values())).object
sphere = bpy.data.objects[json.loads(obj[TAG])['spheres'][0]['cache']].data
assert len(sphere.vertices) < 600 and len(sphere.materials) == 1
view.remove()
print('PASS: native neurites, exact face masking, incremental soma caches, tiny/reversed bands, modifier rename and material-slot fallback')
if hasattr(blenderneuron, 'COV') and blenderneuron.COV:
    blenderneuron.COV.stop()
    blenderneuron.COV.save()
