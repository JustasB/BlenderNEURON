"""Run inside Docker: blender -b --factory-startup --python prototypes/test_soma_display.py."""
import sys
sys.path.insert(0, '/BlenderNEURON')
import bpy
sys.stdout.reconfigure(line_buffering=True)
import blenderneuron
blenderneuron.register()
from blenderneuron.blender.blenderroot import BlenderSection
from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
from blenderneuron.blender.views.cellobjectview import CellObjectView
from blenderneuron.blender.views.groupobjectview import GroupObjectView
from blenderneuron.blender.views.sectionobjectview import SectionObjectView
from blenderneuron.blender.views.synapseformerview import SynapseFormerView
from blenderneuron.blender.views.vectorconfinerview import VectorConfinerView
from blenderneuron.blender.somadisplay import attach, detach, refresh, TAG
from mathutils import Vector


def section(name, coords, radii):
    sec = BlenderSection()
    sec.name, sec.coords, sec.radii = name, coords, radii
    sec.nseg, sec.point_count = 3, len(radii)
    return sec


def snapshot(container):
    return {name: container.get_spline_3d_data(name) for name in container.name2spline_index}


def mesh_count(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return len(mesh.vertices)
    finally:
        evaluated.to_mesh_clear()


checks = 0
for view_class in (SectionObjectView, CellObjectView, GroupObjectView):
    for granularity in ('Cell', 'Section', '3D Segment'):
        name = view_class.__name__+granularity
        group = BlenderRootGroup(name, None)
        group.recording_granularity = granularity
        group.spherize_soma_if_DeqL = False
        group.smooth_sections = False
        roots = []
        for i in range(2):
            y = i*40
            root = section(name+str(i)+'.soma', [0,y,0, 5,y,0, 10,y,0], [5,5,5])
            root.children = [section(name+str(i)+'.dend', [10,y,0, 20,y,0], [1,1])]
            roots.append(root)
        group.roots = {r.name:r for r in roots}
        view = view_class(group)
        view.frame_view = False
        view.closed_ends = False
        view.show()
        group.view = view
        for container in view.containers.values():
            if not any('soma' in s.name for s in container.spline_index2section.values()):
                continue
            obj = container.object
            before = snapshot(container)
            baseline_tree = SynapseFormerView.build_tree(view, '*')[1] if granularity != '3D Segment' else None
            original_count = mesh_count(obj)
            modifier = attach(container)
            assert modifier.show_viewport
            assert mesh_count(obj) != original_count, (name, 'no evaluated change')
            assert snapshot(container) == before
            view.update_group_with_view_data()
            assert snapshot(container) == before
            if baseline_tree is not None:
                after_tree = SynapseFormerView.build_tree(view, '*')[1]
                assert [(t.loc, t.radius, t.x) for t in baseline_tree.values()] == [(t.loc, t.radius, t.x) for t in after_tree.values()]
            # Source geometry remains usable by confinement's actual alignment reader.
            VectorConfinerView.align_object_towards(obj, obj.matrix_world @ Vector((20,0,0)), 0)
            assert snapshot(container) == before
            # Global nonuniform scaling should disable spherical styling.
            obj.scale = (2,1,1)
            bpy.context.view_layer.update()
            refresh()
            assert not modifier.show_viewport
            obj.scale = (1,1,1)
            bpy.context.view_layer.update()
            refresh()
            assert modifier.show_viewport
            # Edit diameter, bend control point, and bend handles independently.
            index = next(i for i,s in container.spline_index2section.items() if 'soma' in s.name)
            spline = obj.data.splines[index]
            p = spline.bezier_points[0]
            radius = p.radius
            p.radius *= .8
            refresh()
            # Group can have another eligible soma: inspect selection independently.
            from blenderneuron.blender.somadisplay import eligible
            import json
            indices = json.loads(obj[TAG])['sections'][0]
            assert eligible(obj, indices, container.closed_ends) is None
            p.radius = radius
            co = p.co.copy()
            p.co.y += 1
            refresh()
            assert eligible(obj, indices, container.closed_ends) is None
            p.co = co
            p.handle_left = co
            p.handle_right = co + Vector((0,1,0))
            refresh()
            assert eligible(obj, indices, container.closed_ends) is None
            p.handle_right = co
            refresh()
            assert eligible(obj, indices, container.closed_ends) is not None
            assert snapshot(container) == before
            detach(obj)
            assert mesh_count(obj) == original_count
            checks += 1
        view.remove()
print('PASS:', checks, 'containers across all 9 view/recording combinations')

# Default smooth/capped rendering, unequal pt3d intervals, and persistence.
group = BlenderRootGroup('edge_cases', None)
group.recording_granularity = '3D Segment'
group.spherize_soma_if_DeqL = False
root = section('edge.soma', [0,0,0, 2,0,0, 10,0,0], [5,5,5])
group.roots = {root.name:root}
view = GroupObjectView(group)
view.frame_view = False
view.show()
container = next(iter(view.containers.values()))
obj = container.object
before = snapshot(container)
modifier = attach(container)
assert modifier.show_viewport
assert snapshot(container) == before
# Material boundary uses x=2 rather than the midpoint x=5.
import json
cache = bpy.data.objects[json.loads(obj[TAG])['spheres'][0]['cache']]
center = Vector((5,0,0))-container.origin
for face in cache.data.polygons:
    x = face.center.x - center.x + 5
    assert face.material_index == (0 if x <= 2 else 1)
# Lines should remain lines.
obj.data.bevel_depth = 0
refresh()
assert not modifier.show_viewport
obj.data.bevel_depth = 1
refresh()
assert modifier.show_viewport
# Cyclic and zero length sources never qualify.
obj.data.splines[0].use_cyclic_u = True
refresh()
assert not modifier.show_viewport
obj.data.splines[0].use_cyclic_u = False
refresh()
assert modifier.show_viewport
# Edit Mode keeps the original curve and does not display the replacement.
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
assert not modifier.show_in_editmode
bpy.ops.object.mode_set(mode='OBJECT')
assert snapshot(container) == before
# Save/reopen in the same runtime, then edit and refresh through persistent handler.
bpy.ops.wm.save_as_mainfile(filepath='/tmp/soma-prototype.blend')
name = obj.name
bpy.ops.wm.open_mainfile(filepath='/tmp/soma-prototype.blend')
obj = bpy.data.objects[name]
assert obj.modifiers[TAG].show_viewport
assert mesh_count(obj) > 100
p = obj.data.splines[0].bezier_points[1]
p.radius *= .8
obj.data.update_tag()
bpy.context.view_layer.update()
assert not obj.modifiers[TAG].show_viewport, 'depsgraph fallback did not run'
p.radius /= .8
obj.data.update_tag()
bpy.context.view_layer.update()
assert obj.modifiers[TAG].show_viewport
# Converting a COPY bakes the sphere without changing the managed curve.
copy = obj.copy()
copy.data = obj.data.copy()
bpy.context.scene.collection.objects.link(copy)
bpy.ops.object.select_all(action='DESELECT')
copy.select_set(True)
bpy.context.view_layer.objects.active = copy
bpy.ops.object.convert(target='MESH')
assert copy.type == 'MESH' and obj.type == 'CURVE'
assert obj.modifiers[TAG].show_viewport
print('PASS: capped smooth segment curves, unequal material bands, lines, cyclic curves, edit mode, save/reopen, automatic refresh, mesh copy')
# Degenerate/length-edited geometry and shear fail closed.
from blenderneuron.blender.somadisplay import eligible
indices = json.loads(obj[TAG])['sections'][0]
ps = obj.data.splines[indices[-1]].bezier_points
p = ps[-2]
co = p.co.copy()
p.co.x += 2
refresh()
assert not obj.modifiers[TAG].show_viewport
p.co = co
refresh()
assert obj.modifiers[TAG].show_viewport
from mathutils import Matrix
matrix = obj.matrix_world.copy()
shear = Matrix.Identity(4)
shear[0][1] = .5
obj.matrix_world = shear
bpy.context.view_layer.update()
refresh()
assert not obj.modifiers[TAG].show_viewport
obj.matrix_world = matrix
bpy.context.view_layer.update()
refresh()
assert obj.modifiers[TAG].show_viewport
# Actual confinement executes identically with display enabled/disabled.
import random
bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-10))
low = bpy.context.object
bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,20))
high = bpy.context.object
matrix = obj.matrix_world.copy()
obj.modifiers[TAG].show_viewport = False
random.seed(17)
VectorConfinerView.confine_between_meshes(obj, low, high, .2, .8, 10)
without = obj.matrix_world.copy()
obj.matrix_world = matrix
obj.modifiers[TAG].show_viewport = True
random.seed(17)
VectorConfinerView.confine_between_meshes(obj, low, high, .2, .8, 10)
assert obj.matrix_world == without
print('PASS: length edits, shear fallback, deterministic confinement with sphere on/off')
# Added/deleted splines cannot leave a stale sphere covering changed topology.
added = obj.data.splines.new('BEZIER')
refresh()
assert not obj.modifiers[TAG].show_viewport
obj.data.splines.remove(added)
refresh()
assert obj.modifiers[TAG].show_viewport
print('PASS: topology-count edits disable the cached display')
# Undo/redo source edits must invalidate the display and rebuild from original data.
from blenderneuron.blender.somadisplay import cleanup, validate
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
name = obj.name
bpy.context.preferences.edit.use_global_undo = True
bpy.ops.ed.undo_push(message='Eligible soma')
obj.data.splines[0].bezier_points[1].radius *= .8
obj.data.update_tag()
bpy.context.view_layer.update()
assert not obj.modifiers[TAG].show_viewport
bpy.ops.ed.undo_push(message='Changed soma radius')
bpy.ops.ed.undo()
obj = bpy.data.objects[name]
assert obj.modifiers[TAG].show_viewport
bpy.ops.ed.redo()
obj = bpy.data.objects[name]
assert not obj.modifiers[TAG].show_viewport
# Restore eligibility, then ensure manual source deletion reaps unlinked resources.
obj.data.splines[0].bezier_points[1].radius /= .8
obj.data.update_tag()
bpy.context.view_layer.update()
cache_name = json.loads(obj[TAG])['cache']
bpy.data.objects.remove(obj, do_unlink=True)
cleanup()
# Earlier explicitly converted copies carry prototype metadata; remove those too.
for candidate in list(bpy.data.objects):
    if TAG in candidate:
        bpy.data.objects.remove(candidate, do_unlink=True)
cleanup()
assert bpy.data.objects.get(cache_name) is None
assert not any(o.get(TAG+'_resource') for o in bpy.data.objects)
assert not any(n.get(TAG+'_resource') for n in bpy.data.node_groups)
print('PASS: actual Blender undo/redo and deleted-source resource cleanup')

# Repeated automatic display creation/removal must not leak caches or node trees.
bpy.ops.wm.read_factory_settings(use_empty=True)
for iteration in range(3):
    group = BlenderRootGroup('lifecycle%d' % iteration, None)
    group.recording_granularity = 'Section'
    group.roots = {root.name: root}
    view = CellObjectView(group)
    view.frame_view = False
    view.show()
    for container in view.containers.values():
        assert TAG in container.object
    view.remove()
    cleanup()
assert not any(o.get(TAG+'_resource') for o in bpy.data.objects)
print('PASS: automatic production lifecycle cleanup')
# Shared-material spline identity still detects reordering/material reassignment.
obj = None
group = BlenderRootGroup('topology', None)
group.recording_granularity = 'Cell'
root = section('topology.soma', [0,0,0, 5,0,0, 10,0,0], [5,5,5])
root.children = [section('topology.dend', [10,0,0, 20,0,0], [1,1])]
group.roots = {root.name:root}
view = CellObjectView(group)
view.frame_view = False
view.show()
obj = next(iter(view.containers.values())).object
copies = view.containers_to_mesh()
assert len(copies) == 1 and copies[0].type == 'MESH'
from blenderneuron.datablocknames import METADATA
assert METADATA not in copies[0] and METADATA not in copies[0].data
assert TAG not in copies[0] and obj.type == 'CURVE'
try:
    view.mesh_containers_to_curves()
except RuntimeError:
    pass
else:
    raise AssertionError('Display mesh reverse conversion was accepted')
bpy.data.objects.remove(copies[0], do_unlink=True)
slot = obj.data.splines[0].material_index
obj.data.splines[0].material_index = obj.data.splines[1].material_index
refresh()
assert not obj.modifiers[TAG].show_viewport
try:
    validate(obj)
except RuntimeError:
    pass
else:
    raise AssertionError('Changed spline identity accepted for export')
detach(obj)
try:
    validate(obj)
except RuntimeError:
    pass
else:
    raise AssertionError('Disabling styling bypassed topology validation')
obj.data.splines[0].material_index = slot
attach(next(iter(view.containers.values())))
refresh()
validate(obj)
view.remove()

# Large combined group: bounded rebuild time, source points unchanged, no leaks.
import time
start = time.perf_counter()
group = BlenderRootGroup('large_group', None)
group.recording_granularity = 'Cell'
roots = []
for i in range(250):
    y = i*15
    root = section('large%d.soma' % i, [0,y,0, 5,y,0, 10,y,0], [5,5,5])
    root.children = [section('large%d.dend%d' % (i,j), [10,y,0, 20,y,j+1], [1,1]) for j in range(4)]
    roots.append(root)
group.roots = {root.name:root for root in roots}
view = GroupObjectView(group)
view.frame_view = False
view.show()
container = next(iter(view.containers.values()))
obj = container.object
assert obj.modifiers[TAG].show_viewport
build_seconds = time.perf_counter()-start
before = snapshot(container)
start = time.perf_counter()
for _ in range(5):
    refresh([obj])
unchanged_seconds = (time.perf_counter()-start)/5
assert snapshot(container) == before
start = time.perf_counter()
obj.data.splines[0].bezier_points[1].radius *= .8
refresh([obj])
edit_seconds = time.perf_counter()-start
assert build_seconds < 30 and edit_seconds < 15
view.remove()
cleanup()
assert not any(o.get(TAG+'_resource') for o in bpy.data.objects)
print('PERFORMANCE: 250 cells / 1250 splines: build %.3fs, unchanged scan %.3fs, edit %.3fs' % (build_seconds, unchanged_seconds, edit_seconds))
if hasattr(blenderneuron, 'COV') and blenderneuron.COV:
    blenderneuron.COV.stop()
    blenderneuron.COV.save()
