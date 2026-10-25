"""Open the animation fixture in a clean Blender runtime with normal add-on startup."""
import sys
sys.path.insert(0, '/BlenderNEURON')
import bpy
import blenderneuron
blenderneuron.register()
from blenderneuron.blender.somadisplay import TAG
bpy.ops.wm.open_mainfile(filepath='/tmp/soma-animation.blend')
obj = next(o for o in bpy.data.objects if TAG in o)
bpy.context.scene.frame_set(2)
assert not obj.modifiers[TAG].show_viewport
bpy.context.scene.frame_set(1)
assert obj.modifiers[TAG].show_viewport
print('PASS: clean-process reopen with normal add-on registration')
from blenderneuron.blender import somadisplay
before = [(tuple(p.co), p.radius) for spline in obj.data.splines for p in spline.bezier_points]
somadisplay.unregister()
assert TAG not in obj
assert before == [(tuple(p.co), p.radius) for spline in obj.data.splines for p in spline.bezier_points]
assert not any(o.get(TAG+'_resource') for o in bpy.data.objects)
somadisplay.register()
somadisplay.register()
assert bpy.app.handlers.frame_change_post.count(somadisplay.frame_changed) == 1
print('PASS: unregister cleanup, original points, idempotent handler registration')
if hasattr(blenderneuron, 'COV') and blenderneuron.COV:
    blenderneuron.COV.stop()
    blenderneuron.COV.save()
