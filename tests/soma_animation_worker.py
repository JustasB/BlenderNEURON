"""Animated eligibility, renderer evaluation and clean-process load checks."""
import sys
sys.path.insert(0, '/BlenderNEURON')
import bpy
import blenderneuron
blenderneuron.register()
from blenderneuron.blender.blenderroot import BlenderSection
from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
from blenderneuron.blender.views.cellobjectview import CellObjectView
from blenderneuron.blender.somadisplay import TAG, refresh, validate
from mathutils import Vector

# The previous worker's file is also exercised from a new process by test runner.
# Build an independent fixture so this test does not depend on execution order.
group = BlenderRootGroup('animated', None)
group.recording_granularity = 'Cell'
root = BlenderSection()
root.name = 'animated.soma'
root.coords = [0,0,0, 5,0,0, 10,0,0]
root.radii = [5,5,5]
root.point_count, root.nseg = 3, 1
group.roots = {root.name:root}
view = CellObjectView(group)
view.frame_view = False
view.show()
container = next(iter(view.containers.values()))
obj = container.object
source = container.get_spline_3d_data(root.name)
assert obj.modifiers[TAG].show_viewport
# A second deforming modifier and shape keys must disable cached replacement.
extra = obj.modifiers.new('Unrelated deformation', 'SIMPLE_DEFORM')
refresh([obj])
assert not obj.modifiers[TAG].show_viewport
obj.modifiers.remove(extra)
refresh([obj])
assert obj.modifiers[TAG].show_viewport
# Collinear handles that overshoot an interval can create backtracking curves.
p = obj.data.splines[0].bezier_points[1]
right = p.handle_right.copy()
p.handle_right_type = 'FREE'
p.handle_right = p.co + Vector((100,0,0))
refresh([obj])
assert not obj.modifiers[TAG].show_viewport
p.handle_right = right
refresh([obj])
assert obj.modifiers[TAG].show_viewport
# Linked source curves get independent display caches, including transform fallback.
from types import SimpleNamespace
from blenderneuron.blender.somadisplay import attach, detach
from blenderneuron.datablocknames import METADATA
import json
linked = obj.copy()
for modifier in list(linked.modifiers):
    linked.modifiers.remove(modifier)
for key in (TAG, METADATA):
    if key in linked:
        del linked[key]
bpy.context.scene.collection.objects.link(linked)
attach(SimpleNamespace(object=linked, spline_index2section=container.spline_index2section,
                       closed_ends=container.closed_ends))
assert json.loads(linked[TAG])['cache'] != json.loads(obj[TAG])['cache']
linked.scale = (2,1,1)
bpy.context.view_layer.update()
assert not linked.modifiers[TAG].show_viewport
assert obj.modifiers[TAG].show_viewport
detach(linked)
bpy.data.objects.remove(linked, do_unlink=True)
obj.scale = (2,2,2)
bpy.context.view_layer.update()
assert not obj.modifiers[TAG].show_viewport
obj.scale = (1,1,1)
bpy.context.view_layer.update()
assert obj.modifiers[TAG].show_viewport
# Shape-key deformation cannot be silently replaced by the cached display.
obj.shape_key_add(name='Basis')
obj.shape_key_add(name='Deformed')
refresh([obj])
assert not obj.modifiers[TAG].show_viewport
obj.shape_key_clear()
refresh([obj])
assert obj.modifiers[TAG].show_viewport
# A rigid constraint affects world placement, while source data/export stays intact.
bpy.ops.object.empty_add(location=(0,0,8))
target = bpy.context.object
constraint = obj.constraints.new('COPY_LOCATION')
constraint.target = target
bpy.context.view_layer.update()
assert abs(obj.matrix_world.translation.z-8) < 1e-6
assert obj.modifiers[TAG].show_viewport
obj.constraints.remove(constraint)
bpy.data.objects.remove(target, do_unlink=True)
bpy.context.view_layer.update()
assert container.get_spline_3d_data(root.name) == source
# Cache and source share animated material datablocks rather than frozen colors.
cache = bpy.data.objects[json.loads(obj[TAG])['spheres'][0]['cache']]
assert cache.data.materials[0] == obj.data.materials[0]
# Keys modify original curve radii: valid at frame 1, invalid at frame 2.
p = obj.data.splines[0].bezier_points[1]
p.radius = 5
p.keyframe_insert(data_path='radius', frame=1)
p.radius = 4
p.keyframe_insert(data_path='radius', frame=2)
scene = bpy.context.scene
scene.frame_set(1)
assert obj.modifiers[TAG].show_viewport
scene.frame_set(2)
assert not obj.modifiers[TAG].show_viewport
scene.frame_set(1)
assert obj.modifiers[TAG].show_viewport
assert container.get_spline_3d_data(root.name) == source
# Render both frames through Blender's actual render evaluation.
bpy.ops.object.camera_add(location=(0,-30,15))
camera = bpy.context.object
camera.rotation_euler = (-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type, camera.data.ortho_scale = 'ORTHO', 20
scene.camera = camera
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
for frame in (1,2):
    scene.frame_set(frame)
    scene.render.filepath = '/tmp/soma-frame-%d.png' % frame
    bpy.ops.render.render(write_still=True)
    assert obj.modifiers[TAG].show_render == (frame == 1)
# Source topology survives both renders and save/load without manual module import.
validate(obj)
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath='/tmp/soma-animation.blend')
bpy.ops.wm.open_mainfile(filepath='/tmp/soma-animation.blend')
obj = bpy.data.objects[container.blender_name]
bpy.context.scene.frame_set(2)
assert not obj.modifiers[TAG].show_viewport
bpy.context.scene.frame_set(1)
assert obj.modifiers[TAG].show_viewport
print('PASS: animated eligibility, modifier fallback, actual frame rendering and reopen')
if hasattr(blenderneuron, 'COV') and blenderneuron.COV:
    blenderneuron.COV.stop()
    blenderneuron.COV.save()
