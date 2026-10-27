"""Exercise the available soma display backend in each supported Blender release."""
import runpy
import sys
import bpy
import blenderneuron
from blenderneuron.blender.somadisplay import SPHERICAL_SOMAS_SUPPORTED, TAG, attach, refresh

scenario = sys.argv[-1]
assert scenario in ('display', 'animation', 'reopen', 'incremental')
if SPHERICAL_SOMAS_SUPPORTED:
    runpy.run_path('tests/soma_%s_worker.py' % scenario, run_name='__main__')
else:
    blenderneuron.register()
    from blenderneuron.blender.blenderroot import BlenderSection
    from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
    from blenderneuron.blender.views.cellobjectview import CellObjectView
    from blenderneuron.blender.views.groupobjectview import GroupObjectView
    from blenderneuron.blender.views.sectionobjectview import SectionObjectView

    if scenario == 'reopen':
        bpy.ops.wm.open_mainfile(filepath='/tmp/soma-cylindrical.blend')
        obj = bpy.data.objects['cylindrical.soma']
        assert obj.type == 'CURVE' and TAG not in obj
        for frame, radius in ((1, 5), (2, 4)):
            bpy.context.scene.frame_set(frame)
            assert abs(obj.data.splines[0].bezier_points[1].radius - radius) < 1e-6
    else:
        for view_class in (CellObjectView, GroupObjectView, SectionObjectView):
            for recording in ('Cell', 'Section', '3D Segment'):
                group = BlenderRootGroup('cylindrical', None)
                group.recording_granularity = recording
                group.spherize_soma_if_DeqL = True
                root = BlenderSection()
                root.name = 'cylindrical.soma'
                root.coords = [0, 0, 0, 5, 0, 0, 10, 0, 0]
                root.radii = [5, 5, 5]
                root.point_count, root.nseg = 3, 1
                group.roots = {root.name: root}
                view = view_class(group)
                view.frame_view = False
                view.closed_ends = False
                view.show()
                group.view = view
                for container in view.containers.values():
                    obj = container.object
                    original = container.get_spline_3d_data(next(iter(container.name2spline_index)))
                    assert attach(container) is None and TAG not in obj
                    refresh([obj])
                    view.update_group_with_view_data()
                    assert container.get_spline_3d_data(next(iter(container.name2spline_index))) == original
                    bpy.context.view_layer.update()
                    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    mesh = evaluated.to_mesh()
                    assert len(mesh.vertices) > 0 and len(mesh.polygons) > 0
                    evaluated.to_mesh_clear()
                    assert not obj.modifiers
                if scenario == 'incremental':
                    point = obj.data.splines[0].bezier_points[1]
                    point.radius *= .8
                    obj.data.update_tag()
                    bpy.context.view_layer.update()
                    assert TAG not in obj and obj.type == 'CURVE'
                if scenario == 'animation' and view_class is CellObjectView and recording == 'Cell':
                    point = obj.data.splines[0].bezier_points[1]
                    for frame, radius in ((1, 5), (2, 4)):
                        point.radius = radius
                        point.keyframe_insert(data_path='radius', frame=frame)
                    scene = bpy.context.scene
                    bpy.ops.object.camera_add(location=(0, -30, 15))
                    camera = bpy.context.object
                    camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
                    camera.data.type, camera.data.ortho_scale = 'ORTHO', 20
                    scene.camera = camera
                    scene.render.engine = 'BLENDER_WORKBENCH'
                    scene.render.resolution_x = scene.render.resolution_y = 64
                    scene.render.resolution_percentage = 100
                    for frame in (1, 2):
                        scene.frame_set(frame)
                        bpy.ops.render.render()
                        assert obj.type == 'CURVE' and TAG not in obj
                    bpy.ops.wm.save_as_mainfile(filepath='/tmp/soma-cylindrical.blend')
                view.remove()
                assert not any(candidate.get(TAG+'_resource') for candidate in bpy.data.objects)
    print('PASS: cylindrical soma %s on Blender %s' % (scenario, bpy.app.version_string))
    if getattr(blenderneuron, 'COV', None):
        blenderneuron.COV.stop()
        blenderneuron.COV.save()
