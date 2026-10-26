"""Display-only spherical somas; original curve data remains authoritative."""
import json
import math
import bpy
from bisect import bisect_right
from mathutils import Vector
from bpy.app.handlers import persistent

TAG = 'blenderneuron_soma_display'
SOURCE_TOPOLOGY = 'blenderneuron_source_topology'
SPHERICAL_SOMAS_SUPPORTED = bpy.app.version >= (4, 0, 0)
_busy = False
_signatures = {}


def modifier_for(obj):
    return next((m for m in obj.modifiers if m.type == 'NODES' and
                 m.node_group and m.node_group.get(TAG+'_resource')), None)


def topology(obj):
    return [(s.type, len(s.bezier_points), s.material_index) for s in obj.data.splines]


def validate(obj):
    if obj.type != 'CURVE':
        raise RuntimeError('Morphology was converted to a mesh. Undo or reimport before exporting.')
    expected = obj.get(SOURCE_TOPOLOGY)
    if expected is None and TAG in obj:
        expected = json.dumps(json.loads(obj[TAG])['topology'])
    if expected is not None and topology(obj) != [tuple(item) for item in json.loads(expected)]:
        raise RuntimeError('Morphology topology changed. Undo the change or reimport before exporting.')


def signature(obj, indices=None):
    """Only soma coordinates matter to sphere caches; topology remains checked globally."""
    splines = obj.data.splines
    indices = range(len(splines)) if indices is None else indices
    basis = obj.matrix_world.to_3x3()
    # Translation and rotation do not change eligibility or local sphere geometry.
    scale = obj.matrix_world.to_scale()
    columns = [basis.col[i].normalized() for i in range(3)]
    metric = (all(abs(value-1) <= 1e-6 for value in scale) and
              all(abs(columns[i].dot(columns[j])) <= 1e-6 for i in range(3) for j in range(i)))
    return repr((metric, obj.data.bevel_depth, obj.data.taper_object,
                 obj.data.bevel_object, obj.data.shape_keys,
                 [(m.name, m.type) for m in obj.modifiers if m != modifier_for(obj)],
                 [(splines[i].material_index, splines[i].use_cyclic_u,
                   [(tuple(p.co), p.radius, tuple(p.handle_left), tuple(p.handle_right))
                    for p in splines[i].bezier_points]) for i in indices],
                 [obj.data.materials[splines[i].material_index].as_pointer()
                  if obj.data.materials[splines[i].material_index] else 0 for i in indices]))


def eligible(obj, indices, capped):
    """Conservative eligibility; return center, radius and segment materials."""
    basis = obj.matrix_world.to_3x3()
    columns = [basis.col[i].normalized() for i in range(3)]
    if any(abs(columns[i].dot(columns[j])) > 1e-6 for i in range(3) for j in range(i)):
        return None
    scale = obj.matrix_world.to_scale()
    # Export transforms positions but retains source radii. A scaled object
    # therefore no longer satisfies exported L=D, even for uniform scaling.
    if any(abs(value-1) > 1e-6 for value in scale):
        return None
    if (obj.data.bevel_depth != 1 or obj.data.taper_object or obj.data.bevel_object
            or obj.data.shape_keys or any(m != modifier_for(obj) for m in obj.modifiers)):
        return None
    points, materials, interval_lengths = [], [], []
    for index in indices:
        spline = obj.data.splines[index]
        if spline.use_cyclic_u or spline.type != 'BEZIER':
            return None
        ps = list(spline.bezier_points)
        if capped:
            ps = ps[1:-1]
        if len(ps) < 2:
            return None
        if points and (points[-1].co - ps[0].co).length > 1e-6:
            return None
        materials.extend([spline.material_index] * (len(ps)-1))
        interval_lengths.extend((b.co-a.co).length for a,b in zip(ps, ps[1:]))
        points.extend(ps)
        # Include handle positions: collinear control points alone are insufficient.
        for p in ps:
            if not all(math.isfinite(v) for v in (*p.co, p.radius, *p.handle_left, *p.handle_right)):
                return None
    start, end = points[0].co, points[-1].co
    axis = end - start
    length = axis.length
    radius = points[0].radius
    if length <= 1e-6 or radius <= 0 or abs(length - 2*radius) > 1e-5 * length:
        return None
    direction = axis / length
    last = -1e-6
    for p in points:
        if abs(p.radius-radius) > 1e-6 * radius:
            return None
        distance = (p.co-start).dot(direction)
        if distance < last or distance > length + 1e-6:
            return None
        last = distance
        for v in (p.co, p.handle_left, p.handle_right):
            if ((v-start).cross(direction)).length > 1e-6 * length:
                return None
        # Reject handles that reverse or overshoot the centerline.
        if (p.handle_left-p.co).dot(direction) > 1e-6 or (p.handle_right-p.co).dot(direction) < -1e-6:
            return None
    for index in indices:
        ps = list(obj.data.splines[index].bezier_points)
        if capped:
            ps = ps[1:-1]
        for a, b in zip(ps, ps[1:]):
            span = (b.co-a.co).length
            if ((a.handle_right-a.co).dot(direction) > span + 1e-6 or
                    (b.co-b.handle_left).dot(direction) > span + 1e-6):
                return None
    boundaries = []
    distance = 0
    for interval in interval_lengths:
        distance += interval
        boundaries.append(distance / length)
    return (start+end)/2, radius, direction, materials, length, boundaries


HIDE_ATTRIBUTE = 'blenderneuron_hide_soma'


def _resource(name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    obj.use_fake_user = True
    obj[TAG+'_resource'] = True
    return obj


def _sphere(mesh, obj, result):
    """Rebuild just one sphere, with exact rings at original material boundaries."""
    mesh.clear_geometry()
    mesh.materials.clear()
    if result is None:
        return
    center, radius, direction, materials, length, boundaries = result
    # Many pt3d intervals can share one animated material (cell/section mode).
    # Only real material boundaries need rings or local material slots.
    compact_materials, compact_boundaries = [], []
    for index, boundary in zip(materials, boundaries):
        if (compact_materials and obj.data.materials[index] ==
                obj.data.materials[compact_materials[-1]]):
            compact_boundaries[-1] = boundary
        else:
            compact_materials.append(index)
            compact_boundaries.append(boundary)
    materials, boundaries = compact_materials, compact_boundaries
    rotation = direction.to_track_quat('Z', 'Y').to_matrix()
    levels = sorted(set([(1-math.cos(math.pi*i/16))/2 for i in range(1,16)] +
                        [t for t in boundaries[:-1] if 0 < t < 1]))
    vertices = [tuple(center-direction*radius)]
    for t in levels:
        z = 2*t-1
        width = math.sqrt(max(0, 1-z*z))
        for i in range(32):
            angle = 2*math.pi*i/32
            vertices.append(tuple(center+rotation @ Vector((width*math.cos(angle)*radius,
                                                            width*math.sin(angle)*radius, z*radius))))
    vertices.append(tuple(center+direction*radius))
    faces, bands = [], []
    for level in range(len(levels)+1):
        fraction = (([0]+levels)[level] + (levels+[1])[level])/2
        band = min(bisect_right(boundaries, fraction), len(materials)-1)
        for i in range(32):
            j = (i+1)%32
            if level == 0:
                face = (0, 1+j, 1+i)
            elif level == len(levels):
                start = 1+32*(level-1)
                face = (start+i, start+j, len(vertices)-1)
            else:
                low, high = 1+32*(level-1), 1+32*level
                face = (low+i, low+j, high+j, high+i)
            faces.append(face)
            bands.append(band)
    # Local slots keep a combined group's thousands of unrelated materials out
    # of each tiny sphere, while sharing the actual animated material datablocks.
    for source_index in materials:
        mesh.materials.append(obj.data.materials[source_index])
    mesh.from_pydata(vertices, [], faces)
    mesh.polygons.foreach_set('material_index', bands)
    mesh.polygons.foreach_set('use_smooth', [True]*len(faces))


def rebuild(obj):
    descriptor = json.loads(obj[TAG])
    if 'spheres' not in descriptor:
        # Upgrade scenes saved with the original full-object cache. Never bake
        # the old display mesh into the authoritative morphology curves.
        from types import SimpleNamespace
        sections = {i: SimpleNamespace(name='soma_%d' % n)
                    for n, indices in enumerate(descriptor['sections']) for i in indices}
        detach(obj)
        attach(SimpleNamespace(object=obj, closed_ends=descriptor['capped'],
                               spline_index2section=sections))
        if TAG in obj:
            rebuild(obj)
        return
    modifier = modifier_for(obj)
    mask = bpy.data.objects.get(descriptor['cache'])
    if modifier is None or mask is None:
        detach(obj)
        return
    if (topology(obj) != [tuple(item) for item in descriptor['topology']] or
            len(obj.data.materials) != descriptor['slot_count']):
        modifier.show_viewport = modifier.show_render = False
        return
    hidden = [False]*len(obj.data.materials)
    any_sphere = False
    for entry in descriptor['spheres']:
        sphere = bpy.data.objects.get(entry['cache'])
        if sphere is None:
            detach(obj)
            return
        indices = entry['indices']
        fingerprint = signature(obj, indices)
        key = (obj.as_pointer(), entry['cache'])
        if _signatures.get(key) != fingerprint:
            result = eligible(obj, indices, descriptor['capped'])
            _sphere(sphere.data, obj, result)
            sphere['eligible'] = result is not None
            _signatures[key] = fingerprint
        if sphere.get('eligible'):
            any_sphere = True
            for index in indices:
                hidden[obj.data.splines[index].material_index] = True
    attribute = mask.data.attributes[HIDE_ATTRIBUTE]
    old = [False]*len(hidden)
    attribute.data.foreach_get('value', old)
    if old != hidden:
        attribute.data.foreach_set('value', hidden)
        mask.data.update()
    modifier.show_viewport = modifier.show_render = any_sphere


def refresh(objects=None):
    global _busy
    if _busy:
        return
    _busy = True
    try:
        for obj in list(bpy.data.objects) if objects is None else objects:
            if TAG in obj and obj.type == 'CURVE' and obj.mode != 'EDIT':
                rebuild(obj)
    finally:
        _busy = False


@persistent
def updated(scene, depsgraph):
    if _busy:
        return
    changed = {update.id.original for update in depsgraph.updates}
    objects = [obj for obj in scene.objects if TAG in obj and
               (obj in changed or obj.data in changed)]
    refresh(objects)
    cleanup()


def attach(container):
    if not SPHERICAL_SOMAS_SUPPORTED:
        return None
    obj = container.object
    try:
        validate(obj)
    except RuntimeError:
        return None
    if TAG in obj:
        refresh([obj])
        return modifier_for(obj)
    if obj.modifiers:
        return None
    sections = {}
    for index, section in container.spline_index2section.items():
        if 'soma' in section.name.lower():
            sections.setdefault(section.name, []).append(index)
    if not sections:
        return None
    # Frame callbacks rebuild geometry. Prevent concurrent viewport access while
    # Blender's render thread evaluates animated source curves.
    bpy.context.scene.render.use_lock_interface = True
    mask_mesh = bpy.data.meshes.new(TAG+'_mask')
    mask_mesh.from_pydata([(0,0,0)]*len(obj.data.materials), [], [])
    mask_mesh.attributes.new(HIDE_ATTRIBUTE, 'BOOLEAN', 'POINT')
    cache = _resource(TAG+'_mask', mask_mesh)
    spheres = []
    for indices in sections.values():
        mesh = bpy.data.meshes.new(TAG+'_sphere')
        sphere = _resource(TAG+'_sphere', mesh)
        spheres.append(dict(indices=indices, cache=sphere.name))
    obj[TAG] = json.dumps(dict(cache=cache.name, capped=container.closed_ends,
                              topology=topology(obj), slot_count=len(obj.data.materials), spheres=spheres,
                              sections=list(sections.values())))
    nodes = bpy.data.node_groups.new(TAG, 'GeometryNodeTree')
    nodes[TAG+'_resource'] = True
    nodes.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    nodes.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    original = nodes.nodes.new('NodeGroupInput')
    out = nodes.nodes.new('NodeGroupOutput')
    info = nodes.nodes.new('GeometryNodeObjectInfo')
    info.inputs['Object'].default_value = cache
    info.transform_space = 'ORIGINAL'
    attribute = nodes.nodes.new('GeometryNodeInputNamedAttribute')
    attribute.data_type = 'BOOLEAN'
    attribute.inputs['Name'].default_value = HIDE_ATTRIBUTE
    sample = nodes.nodes.new('GeometryNodeSampleIndex')
    sample.data_type = 'BOOLEAN'
    sample.domain = 'POINT'
    material = nodes.nodes.new('GeometryNodeInputMaterialIndex')
    delete = nodes.nodes.new('GeometryNodeDeleteGeometry')
    delete.domain = 'FACE'
    delete.mode = 'ALL'
    join = nodes.nodes.new('GeometryNodeJoinGeometry')
    nodes.links.new(info.outputs['Geometry'], sample.inputs['Geometry'])
    nodes.links.new(attribute.outputs['Attribute'], sample.inputs['Value'])
    nodes.links.new(material.outputs['Material Index'], sample.inputs['Index'])
    nodes.links.new(sample.outputs['Value'], delete.inputs['Selection'])
    nodes.links.new(original.outputs['Geometry'], delete.inputs['Geometry'])
    nodes.links.new(delete.outputs['Geometry'], join.inputs['Geometry'])
    for entry in spheres:
        sphere_info = nodes.nodes.new('GeometryNodeObjectInfo')
        sphere_info.transform_space = 'ORIGINAL'
        sphere_info.inputs['Object'].default_value = bpy.data.objects[entry['cache']]
        nodes.links.new(sphere_info.outputs['Geometry'], join.inputs['Geometry'])
    nodes.links.new(join.outputs['Geometry'], out.inputs['Geometry'])
    modifier = obj.modifiers.new(TAG, 'NODES')
    modifier.node_group = nodes
    modifier.show_in_editmode = False
    if updated not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(updated)
    refresh([obj])
    return modifier


def detach(obj):
    if TAG not in obj:
        return
    descriptor = json.loads(obj[TAG])
    modifier = modifier_for(obj)
    if modifier:
        nodes = modifier.node_group
        obj.modifiers.remove(modifier)
        if nodes and nodes.users == 0:
            bpy.data.node_groups.remove(nodes)
    for name in [descriptor['cache']] + [entry['cache'] for entry in descriptor.get('spheres', [])]:
        cache = bpy.data.objects.get(name)
        if cache:
            mesh = cache.data
            bpy.data.objects.remove(cache, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    del obj[TAG]
    for key in list(_signatures):
        if key[0] == obj.as_pointer():
            del _signatures[key]


def cleanup():
    """Reap caches after manual source deletion and undo, without retaining RNA refs."""
    sources = [obj for obj in bpy.data.objects if TAG in obj]
    used = set()
    for obj in sources:
        descriptor = json.loads(obj[TAG])
        used.add(descriptor['cache'])
        used.update(entry['cache'] for entry in descriptor.get('spheres', []))
    live = {obj.as_pointer() for obj in sources}
    for pointer in list(_signatures):
        if pointer[0] not in live:
            del _signatures[pointer]
    for nodes in list(bpy.data.node_groups):
        if nodes.get(TAG+'_resource') and nodes.users == 0:
            bpy.data.node_groups.remove(nodes)
    for cache in list(bpy.data.objects):
        if cache.get(TAG+'_resource') and cache.name not in used:
            mesh = cache.data
            bpy.data.objects.remove(cache, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


@persistent
def loaded(*_):
    _signatures.clear()
    refresh()
    cleanup()


@persistent
def frame_changed(*_):
    refresh()


@persistent
def history_changed(*_):
    loaded()


def register():
    for handlers, callback in ((bpy.app.handlers.load_post, loaded),
                               (bpy.app.handlers.frame_change_post, frame_changed),
                               (bpy.app.handlers.depsgraph_update_post, updated),
                               (bpy.app.handlers.undo_post, history_changed),
                               (bpy.app.handlers.redo_post, history_changed)):
        if callback not in handlers:
            handlers.append(callback)


def unregister():
    for handlers, callback in ((bpy.app.handlers.load_post, loaded),
                               (bpy.app.handlers.frame_change_post, frame_changed),
                               (bpy.app.handlers.depsgraph_update_post, updated),
                               (bpy.app.handlers.undo_post, history_changed),
                               (bpy.app.handlers.redo_post, history_changed)):
        if callback in handlers:
            handlers.remove(callback)

    sources = [obj for obj in bpy.data.objects if TAG in obj]
    for obj in sources:
        detach(obj)
    cleanup()
    _signatures.clear()
