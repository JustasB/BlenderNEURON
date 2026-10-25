"""Save an unconfined, Z-up binary-tree cell and its two confinement planes.

Inside Docker:
blender --background --python notebooks/performance/confinement_setup.py
"""
import math
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from confinement_config import SETUP, cell_pose_matrix



def apply_print_style(group=None):
    """White paper background, blue cable, and a front orthographic view."""
    import bpy
    from mathutils import Vector
    scene = bpy.context.scene
    scene['Confinement figure setup'] = json.dumps(SETUP, sort_keys=True)
    blue = SETUP['cell_rgba']
    if group is not None:
        group.default_color = blue
        group.default_brightness = 1.
        for container in group.view.containers.values():
            obj = container.get_object()
            for mat in obj.data.materials:
                mat.diffuse_color = blue
                if mat.use_nodes:
                    for shader in mat.node_tree.nodes:
                        if shader.type == 'EMISSION':
                            shader.inputs['Color'].default_value = blue
                            shader.inputs['Strength'].default_value = 1.
                        elif shader.type == 'BSDF_PRINCIPLED':
                            shader.inputs['Base Color'].default_value = blue
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = SETUP['world_rgba']
    background.inputs['Strength'].default_value = 1.
    scene.render.film_transparent = False
    scene.render.use_compositing = False
    scene.view_settings.view_transform = SETUP['view_transform']
    scene.view_settings.look = SETUP['look']
    scene.view_settings.exposure = 0.
    scene.view_settings.gamma = 1.
    camera = scene.camera
    camera.location = SETUP['camera_location_um']
    camera.rotation_euler = (Vector(SETUP['camera_target_um'])-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = SETUP['camera_type']
    camera.data.ortho_scale = SETUP['camera_width_um']
    camera.data.clip_end = 10000.
    # Horizontal meshes are edge-on in the front view. Thin guides make their
    # heights visible without changing the actual confinement meshes.
    for z in SETUP['slab_um']:
        name = 'Layer boundary guide Z %g' % z
        if bpy.data.objects.get(name) is None:
            curve = bpy.data.curves.new(name, 'CURVE')
            curve.dimensions = '3D'
            curve.bevel_depth = .45
            curve.bevel_resolution = 2
            spline = curve.splines.new('POLY')
            spline.points.add(1)
            spline.points[0].co = (-300., -2., z, 1.)
            spline.points[1].co = (300., -2., z, 1.)
            ob = bpy.data.objects.new(name, curve)
            bpy.context.collection.objects.link(ob)
            mat = bpy.data.materials.new(name)
            mat.diffuse_color = (.25, .25, .25, 1.)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            emission = nodes.new('ShaderNodeEmission')
            emission.inputs['Color'].default_value = (.25, .25, .25, 1.)
            mat.node_tree.links.new(emission.outputs[0], nodes.get('Material Output').inputs['Surface'])
            curve.materials.append(mat)
    # A neutral backdrop marks the configured target slab.
    band_name = 'Target region backdrop Z %g–%g' % tuple(SETUP['target_um'])
    half_size = SETUP['plane_size_um']/2
    low, high = SETUP['target_um']
    band = bpy.data.objects.get(band_name)
    if band is None:
        mesh = bpy.data.meshes.new(band_name)
        mesh.from_pydata([(-half_size, 300., low), (half_size, 300., low),
                          (half_size, 300., high), (-half_size, 300., high)], [], [(0, 1, 2, 3)])
        mesh.update()
        band = bpy.data.objects.new(band_name, mesh)
        bpy.context.collection.objects.link(band)
        mat = bpy.data.materials.new(band_name)
        mat.diffuse_color = SETUP['target_rgba']
        mat.use_nodes = True
        emission = mat.node_tree.nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = SETUP['target_rgba']
        emission.inputs['Strength'].default_value = 1.
        mat.node_tree.links.new(emission.outputs[0],
                               mat.node_tree.nodes.get('Material Output').inputs['Surface'])
        mesh.materials.append(mat)
        band['purpose'] = 'Visual target shading only; not a confinement boundary'
    scene.render.resolution_x, scene.render.resolution_y = SETUP['resolution']
    scene.render.resolution_percentage = 100
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_perspective = 'CAMERA'
                space.shading.type = 'MATERIAL'
                space.shading.use_scene_world = True
                space.shading.use_scene_lights = True
                space.shading.background_type = 'WORLD'
                area.tag_redraw()


def main(group=None, node=None, output=None, render=True, transform_cell=True, save=True):
    import bpy
    from mathutils import Matrix, Vector, Quaternion
    import performance_eval as perf
    output = Path(output) if output else HERE/'figures/confinement_setup.blend'
    output.parent.mkdir(exist_ok=True)
    if group is None:
        perf.clear_scene()

    def material(name, color, alpha=1.):
        mat = bpy.data.materials.new(name)
        mat.diffuse_color = (*color, alpha)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value = (*color, 1.)
        shader.inputs['Alpha'].default_value = alpha
        shader.inputs['Roughness'].default_value = .65
        if alpha < 1:
            if hasattr(mat, 'surface_render_method'):
                mat.surface_render_method = 'DITHERED'
            else:
                mat.blend_method = 'BLEND'
            if hasattr(mat, 'use_screen_refraction'):
                mat.use_screen_refraction = True
            if hasattr(mat, 'show_transparent_back'):
                mat.show_transparent_back = False
        return mat

    def setup(group, node):
        # Use the identical rigid pose in Blender and the NEURON source.
        transform = Matrix(cell_pose_matrix()) if transform_cell else Matrix.Identity(4)
        for root in group.roots.values():
            ob = group.view.containers[root.name].get_object()
            ob.matrix_world = transform @ ob.matrix_world
        bpy.context.view_layer.update()
        # Bake the setup into the production section data before saving.
        group.update_with_view_data()
        group.show()
        bottom, top = SETUP['slab_um']
        target_low, target_high = SETUP['target_um']
        bottom_name = 'Bottom plane — Z %g µm' % bottom
        top_name = 'Top plane — Z %g µm' % top
        for z, name, color in ((bottom, bottom_name, (.15, .4, .65)),
                               (top, top_name, (.1, .6, .4))):
            bpy.ops.mesh.primitive_plane_add(size=SETUP['plane_size_um'], location=(0, 0, z))
            ob = bpy.context.object
            ob.name = name
            ob.data.materials.append(material(name, color, .16))
            ob['layer_z_um'] = z
            ob.show_wire = True
            ob.show_all_edges = True
        group.set_confiner_layers(bottom_name, top_name, 15., *SETUP['height_fractions'])
        group.ui_group.layer_confiner_settings.max_section_length = 25.
        group.ui_group.layer_confiner_settings.seed = 0
        # Label the planes and configured target without adding another boundary mesh.
        for text, loc in (('BOTTOM  Z = %g µm' % bottom, (-300, -305, bottom-20.)),
                          ('TOP  Z = %g µm' % top, (-300, -305, top+10.)),
                          ('Target Zone', (-300, -305, (target_low+target_high)/2))):
            bpy.ops.object.text_add(location=loc, rotation=(math.pi/2, 0, 0))
            ob = bpy.context.object
            ob.name = text
            ob.data.body = text
            ob.data.size = 15
            if text == 'Target Zone':
                ob.data.align_y = 'CENTER'
            ob.data.materials.append(material(text, (.08, .12, .16)))
        scene = bpy.context.scene
        bpy.ops.object.camera_add(location=SETUP['camera_location_um'])
        camera = bpy.context.object
        target = Vector(SETUP['camera_target_um'])
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.type = SETUP['camera_type']
        camera.data.ortho_scale = SETUP['camera_width_um']
        camera.data.clip_end = 10000
        scene.camera = camera
        bpy.ops.object.light_add(type='AREA', location=(100, -400, 700))
        bpy.context.object.data.energy = 10000000
        bpy.context.object.data.shape = 'DISK'
        bpy.context.object.data.size = 600
        bpy.context.object.rotation_euler = (target-bpy.context.object.location).to_track_quat('-Z', 'Y').to_euler()
        engines = {item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items}
        scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
        if hasattr(scene, 'eevee'):
            scene.eevee.taa_render_samples = 64
        scene.world.use_nodes = True
        scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = SETUP['world_rgba']
        scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.
        scene.render.resolution_x = 1200
        scene.render.resolution_y = 900
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(output.with_suffix('.png'))
        scene['Confinement setup'] = ('UNCONFINED binary-tree test cell; soma center %s µm; Z rotation %g degrees then Y rotation %g degrees; ' %
                                      (SETUP['soma_center_um'], SETUP['cell_z_rotation_degrees'], SETUP['cell_y_rotation_degrees']) +
                                      'planes at Z %g/%g; target Z %g–%g.' % (bottom, top, target_low, target_high))
        scene['Confinement settings'] = ('15 degrees; max piece 25 µm; seed 0; *dend*; target height fractions %g–%g' % tuple(SETUP['height_fractions']))
        note = bpy.data.texts.new('READ ME — confinement setup')
        note.write(scene['Confinement setup']+'\n'+scene['Confinement settings']+'\nNo confinement has been applied. Geometry was imported from live NEURON using the existing performance binary-tree generator (16 sections).\n')
        bpy.ops.object.select_all(action='DESELECT')
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    space.clip_end = 10000
                    space.region_3d.view_perspective = 'CAMERA'
                    space.overlay.show_extras = False
                    space.shading.type = 'MATERIAL'
        apply_print_style(group)
        if save:
            bpy.ops.wm.save_as_mainfile(filepath=str(output))
        if render:
            bpy.ops.render.render(write_still=True)
        print('Saved setup:' if save else 'Prepared setup:', output)
    if group is None:
        perf.import_live_neuron_group(1, 16, 'Section', 'Section', False, after_import=setup)
    else:
        setup(group, node)


if __name__ == '__main__':
    main()
