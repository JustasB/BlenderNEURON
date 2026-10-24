"""Encoder tests run in ordinary Python; Blender integration uses existing helpers."""
import unittest
from textwrap import dedent
from blenderneuron.datablocknames import entity_key, encode_name, name_limit
from blenderneuron.commnode import CommNode
from tests import Blender, NEURON, BlenderTestCase


class TestNameEncoder(unittest.TestCase):
    def test_limits_and_unicode(self):
        self.assertEqual(name_limit((4, 5, 0)), 63)
        self.assertEqual(name_limit((5, 0, 0)), 255)
        for limit in (63, 255):
            for name in ('soma', 'a'*limit, 'é'*(limit//2), 'a'*1000, '😀é'*200):
                key = entity_key('objects', 'section', name)
                mapped = encode_name(key, limit)
                self.assertLessEqual(len(mapped.encode('utf-8')), limit)
                self.assertEqual(mapped, encode_name(key, limit))
                if len(name.encode('utf-8')) <= limit:
                    self.assertEqual(mapped, name)
                else:
                    self.assertNotEqual(mapped, encode_name(entity_key('objects', 'section', name+'x'), limit))
                    self.assertNotEqual(mapped, encode_name(entity_key('objects', 'other', name), limit))
                    self.assertNotEqual(mapped, encode_name(entity_key('curves', 'section', name), limit))
                    self.assertNotEqual(mapped, encode_name(key, limit, 1))
        with self.assertRaises(ValueError):
            encode_name(entity_key('objects', 'section', 'a'), 17)
        for name in ('', None, 'a\0b'):
            with self.assertRaises(ValueError):
                entity_key('objects', 'section', name)

    def test_stable_digest(self):
        import subprocess, sys
        key = entity_key('objects', 'section', 'é'*200, 'rank1')
        code = 'from blenderneuron.datablocknames import encode_name; print(encode_name(%r, 63))' % (key,)
        result = subprocess.check_output([sys.executable, '-c', code]).decode().strip().splitlines()[-1]
        self.assertEqual(result, encode_name(key, 63))


class TestDataBlockNames(BlenderTestCase):
    def test_bounds_framing_keeps_all_objects_visible(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            control.client.run_command(dedent('''
                from types import SimpleNamespace
                from blenderneuron.blender.views.objectview import ObjectViewAbstract
                from bpy_extras.view3d_utils import location_3d_to_region_2d
                from mathutils import Vector
                objects = []
                for location in ((-1000, 500, 400), (400, -200, -100)):
                    bpy.ops.mesh.primitive_cube_add(location=location)
                    objects.append(bpy.context.object)
                view = ObjectViewAbstract.__new__(ObjectViewAbstract)
                view.containers = {ob.name: SimpleNamespace(get_object=lambda ob=ob: ob) for ob in objects}
                regions = [(area.spaces.active, region)
                           for area in bpy.context.screen.areas if area.type == 'VIEW_3D'
                           for region in area.regions if region.type == 'WINDOW']
                assert regions
                for perspective in ('PERSP', 'ORTHO'):
                    for space, region in regions:
                        space.region_3d.view_perspective = perspective
                    view.zoom_to_containers()
                    assert not bpy.context.selected_objects
                    for space, region in regions:
                        space.region_3d.update()
                        for ob in objects:
                            for corner in ob.bound_box:
                                point = location_3d_to_region_2d(
                                    region, space.region_3d, ob.matrix_world @ Vector(corner))
                                assert point is not None
                                assert 0 <= point.x <= region.width, (perspective, point, region.width)
                                assert 0 <= point.y <= region.height, (perspective, point, region.height)
                view.containers = {}
                view.zoom_to_containers()
            '''))

    def test_import_batch_preserves_identity_and_rollback(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            control.client.run_command(dedent('''
                from blenderneuron.datablocknames import *
                registry = NameRegistry(63)
                key = entity_key('objects', 'section', 'batch-existing')
                block = registry.create(key, lambda n: bpy.data.objects.new(n, None))
                block.name = 'renamed before import'
                collision_key = entity_key('objects', 'section', 'batch-collision')
                unrelated = bpy.data.objects.new(collision_key[3], None)
                long_key = entity_key('objects', 'section', 'é'*200)
                with registry.import_batch():
                    assert registry.resolve(key) == block
                    with registry.import_batch():
                        assert registry.resolve(key) == block
                    duplicate = registry.create(collision_key, lambda n: bpy.data.objects.new(n, None))
                    assert duplicate != unrelated and duplicate.name == 'batch-collision.001'
                    long_block = registry.create(long_key, lambda n: bpy.data.objects.new(n, None))
                    assert long_block.name == encode_name(long_key, 63)
                    registry.remove(long_block)
                    assert registry.resolve(long_key) is None
                    replacement = registry.create(long_key, lambda n: bpy.data.objects.new(n, None))
                    assert replacement.name == encode_name(long_key, 63)
                assert registry._import_cache is None
                # A new phase must not trust stale metadata from the previous one.
                block[METADATA] = key_json(collision_key)
                for batch in (False, True):
                    try:
                        if batch:
                            with registry.import_batch():
                                registry.resolve(key)
                        else:
                            registry.resolve(key)
                        assert False, 'changed identity accepted'
                    except MappingError:
                        pass
                block[METADATA] = key_json(key)
                failed_key = entity_key('objects', 'section', 'batch-failed')
                try:
                    with registry.transaction(), registry.import_batch():
                        registry.create(failed_key, lambda n: bpy.data.objects.new(n, None))
                        raise ValueError('rollback')
                except ValueError:
                    pass
                assert registry._import_cache is None
                assert registry.resolve(failed_key) is None
                assert bpy.data.objects.get(failed_key[3]) is None
                assert not registry.reservations
                bpy.data.objects.remove(block)
                assert registry.resolve(key) is None
            '''))

    def test_registry(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            control.client.run_command(dedent('''
                from blenderneuron.datablocknames import *
                from unittest.mock import patch
                registry = NameRegistry(63)
                key = entity_key('objects', 'section', 'short')
                unrelated = bpy.data.objects.new('short', None)
                block = registry.create(key, lambda n: bpy.data.objects.new(n, None))
                assert block != unrelated and block.name == 'short.001'
                assert registry.create(key, lambda n: None) == block
                assert registry.identity(block) == key
                block.name = 'user rename'
                assert registry.resolve(key) == block
                rebuilt = NameRegistry(63)
                assert rebuilt.resolve(key) == block
                duplicate = block.copy()
                try:
                    NameRegistry(63)
                    assert False
                except MappingError:
                    pass
                bpy.data.objects.remove(duplicate)
                block[METADATA] = 'bad json'
                try:
                    NameRegistry(63)
                    assert False
                except MappingError:
                    pass
                block[METADATA] = key_json(key)
                long_key = entity_key('objects', 'section', 'é'*200)
                first = registry.reserve(long_key)
                occupied = bpy.data.objects.new(first, None)
                registry.release(long_key)
                second = registry.reserve(long_key)
                assert first != second
                long_block = registry.create(long_key, lambda n: bpy.data.objects.new(n, None))
                assert long_block.name == second
                assert len(second.encode('utf-8')) <= 63
                registry.remove(long_block)
                registry.remove(long_block)
                with patch('blenderneuron.datablocknames.encode_name', return_value=first):
                    try:
                        registry.reserve(long_key)
                        assert False
                    except MappingError:
                        pass
                try:
                    with registry.transaction():
                        registry.create(long_key, lambda n: bpy.data.objects.new(n, None))
                        raise ValueError('rollback')
                except ValueError:
                    pass
                assert registry.resolve(long_key) is None
                assert registry.resolve(key) == block and bpy.data.objects.get('short') == unrelated
                try:
                    registry.create(long_key, lambda n: bpy.data.objects.new('wrong', None))
                    assert False
                except MappingError:
                    pass
                assert bpy.data.objects.get('wrong') is None
                try:
                    registry.remove(unrelated)
                    assert False
                except MappingError:
                    pass
                registry.remove(block)
                assert registry.resolve(key) is None
                external = registry.create(key, lambda n: bpy.data.objects.new(n, None))
                bpy.data.objects.remove(external)
                assert registry.resolve(key) is None
                for limit in (17, 256):
                    try:
                        NameRegistry(limit)
                        assert False
                    except ValueError:
                        pass
                compatible = NameRegistry(18)
                short_key = entity_key('objects', 'section', 'x'*18)
                bpy.data.objects.new('x'*18, None)
                bounded = compatible.create(short_key, lambda n: bpy.data.objects.new(n, None))
                assert bounded.name == 'x'*14 + '.001'
                assert '#' not in bounded.name
                compatible.remove(bounded)
                bad = bpy.data.objects.new('bad metadata', None)
                for metadata in ('[]', '[2,"objects","section","bad",""]',
                                 key_json(entity_key('curves', 'section', 'bad'))):
                    bad[METADATA] = metadata
                    try:
                        NameRegistry()
                        assert False
                    except MappingError:
                        pass
                bpy.data.objects.remove(bad)

            '''))

    def test_neuron_blender_roundtrip(self):
        with NEURON(), CommNode('Control-NEURON', coverage=True) as neuron, \
                Blender(), CommNode('Control-Blender', coverage=True) as blender:
            canonical = 'GeneratedHierarchy'*20 + '.soma'
            neuron.client.run_command('sec = h.Section(name=' + repr(canonical) + ');'
                                      'h.pt3dadd(0,0,0,2,sec=sec); h.pt3dadd(10,0,0,2,sec=sec)')
            blender.client.run_command(dedent('''
                bpy.ops.blenderneuron.get_cell_list_from_neuron()
                bpy.ops.blenderneuron.import_groups()
                group = bpy.types.Object.BlenderNEURON_node.groups['Group.000']
                container = next(iter(group.view.containers.values()))
                container.get_object().location.z += 8
                bpy.ops.blenderneuron.update_groups_with_view_data()
                bpy.ops.blenderneuron.export_groups()
                return_value = container.canonical_name
            '''))
            self.assertEqual(neuron.client.run_command('return_value = sec.name()'), canonical)
            self.assertEqual(neuron.client.run_command('return_value = h.z3d(0,sec=sec)'), 8.)
            for _ in range(2):
                self.assertEqual(blender.client.run_command(dedent('''
                    bpy.ops.blenderneuron.import_groups()
                    group = bpy.types.Object.BlenderNEURON_node.groups['Group.000']
                    from blenderneuron.datablocknames import METADATA
                    return_value = len([obj for obj in bpy.data.objects if METADATA in obj])
                ''')), 1)

    def test_save_reopen_and_split(self):
        import tempfile, os, shlex
        setup = dedent('''
            from blenderneuron.blender.blenderroot import BlenderSection
            from blenderneuron.blender.views.curvecontainer import CurveContainer
            from blenderneuron.datablocknames import get_registry, entity_key, MappingError
            root = BlenderSection()
            root.name = 'LongHierarchy'*30 + '.dend'
            root.coords = [0,0,0, 10,0,0, 20,0,0]
            root.radii = [1,1,1]
            root.point_count = 3
            root.nseg = 1
        ''')
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'names.blend')
            with Blender(), CommNode('Control-Blender', coverage=True) as control:
                control.client.run_command(setup)
                control.client.run_command(dedent('''
                    template = bpy.data.curves.new('test-template', 'CURVE')
                    container = CurveContainer(root, template, False, [1,1,1,1], 1, 'Section', closed_ends=False)
                    container.link()
                    container.get_object().location.z += 12
                    bpy.ops.wm.save_as_mainfile(filepath=''') + repr(path) + ')')
            with Blender(cmd_args=Blender.cmd_args + ' ' + shlex.quote(path)), CommNode('Control-Blender', coverage=True) as control:
                control.client.run_command(setup)
                control.client.run_command(dedent('''
                    registry = get_registry()
                    key = entity_key('objects', 'section-container', root.name)
                    saved = registry.resolve(key)
                    assert saved is not None
                    container = CurveContainer(root, saved.data, False, [1,1,1,1], 1, 'Section', closed_ends=False)
                    assert container.get_object() == saved
                    container.update_group_section_with_view_data(root)
                    assert root.coords[2] == 12
                    assert root.to_dict()['name'] == 'LongHierarchy'*30 + '.dend'
                    from blenderneuron.blender.views.synapseformerview import SynapseFormerView
                    from types import SimpleNamespace
                    tree, terminals, radius = SynapseFormerView.build_tree(SimpleNamespace(containers={root.name:container}), '*')
                    assert terminals and all(t.section_name == root.name for t in terminals.values())
                    container.remove()
                    container.remove()
                    template = bpy.data.curves.new('split template', 'CURVE')
                    splits = root.make_split_sections(7)
                    containers = [CurveContainer(part, template, False, [1,1,1,1], 1, 'Section', closed_ends=False) for part in splits]
                    assert len({c.blender_name for c in containers}) == len(splits)
                    for c in containers:
                        c.link()
                    for previous, child in zip(containers, containers[1:]):
                        child.set_parent_object(previous)
                        assert child.get_object().parent == previous.get_object()
                    for c in containers:
                        c.remove()
                '''))

    def test_long_mpi_names(self):
        import tempfile, subprocess, json
        from pathlib import Path
        for mode in ('automatic', 'explicit'):
            with tempfile.TemporaryDirectory() as directory:
                result = subprocess.run(['mpiexec', '--allow-run-as-root', '-n', '2',
                    'nrniv', '-mpi', '-python', 'tests/mpi_long_names_worker.py', mode, directory],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                groups = json.loads(Path(directory, 'groups.json').read_text())
                with Blender(), CommNode('Control-Blender', coverage=True) as control:
                    control.client.run_command('payload = ' + repr(groups))
                    control.client.run_command(dedent('''
                        from blenderneuron.blender.blenderroot import BlenderSection
                        from blenderneuron.blender.views.curvecontainer import CurveContainer
                        from blenderneuron.datablocknames import get_registry
                        template = bpy.data.curves.new('test template', 'CURVE')
                        containers = []
                        for data in payload[0]['roots']:
                            root = BlenderSection()
                            root.from_full_NEURON_section_dict(data)
                            container = CurveContainer(root, template, False, [1,1,1,1], 1, 'Section')
                            container.update_group_section_with_view_data(root)
                            assert root.to_dict()['name'] == data['name']
                            assert len(container.blender_name.encode('utf-8')) <= get_registry().maximum_bytes
                            containers.append(container)
                        assert containers[0].get_object() != containers[1].get_object()
                        for container in containers:
                            container.remove()
                    '''))

    def test_long_geometry_activity_recovery(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            control.client.run_command(dedent('''
                import numpy as np
                from types import SimpleNamespace
                from collections import OrderedDict
                from blenderneuron.activity import Activity
                from blenderneuron.blender.blenderroot import BlenderSection
                from blenderneuron.blender.views.cellobjectview import CellObjectView
                from blenderneuron.blender.views.sectionobjectview import SectionObjectView
                from blenderneuron.datablocknames import *
                import blenderneuron.datablocknames as naming
                def section(name):
                    sec = BlenderSection()
                    sec.name = name
                    sec.coords = [0,0,0, 10,0,0, 20,0,0]
                    sec.radii = [1,1,1]
                    sec.activity.times = np.array([0,1,2])
                    sec.activity.values = np.array([-70.,-20.,-50.])
                    sec.segment_activity = {i: sec.activity for i in range(2)}
                    return sec
                roots = [section('same'), section('é'*160 + 'a'), section('é'*160 + 'b')]
                child = section('generated_'*40 + '.dend')
                roots[1].children = [child]
                unrelated = bpy.data.objects.new('same', None)
                unrelated_mat = bpy.data.materials.new('same')
                for view_class in (CellObjectView, SectionObjectView):
                    for granularity in ('Cell', 'Section', '3D Segment'):
                        group = SimpleNamespace(name='group', roots=OrderedDict((r.name,r) for r in roots),
                            smooth_sections=False, default_color=[1,1,1,1], default_brightness=1,
                            segment_subdivisions=2, circular_subdivisions=6, as_lines=False,
                            recording_granularity=granularity, frames_per_ms=1,
                            animate_brightness=True, animate_color=False, max_brightness=2,
                            animation_range_low=-80, animation_range_high=40)
                        view = view_class(group)
                        view.show()
                        view.update_group_with_view_data()
                        assert roots[1].name == 'é'*160+'a'
                        for container in view.containers.values():
                            assert container.get_object() != unrelated
                            assert len(container.blender_name.encode('utf-8')) <= naming.get_registry().maximum_bytes
                            for mat in container.curve.materials:
                                assert mat != unrelated_mat
                                assert mat.animation_data.action is not None
                                assert naming.get_registry().identity(mat)[3] in view.materials
                        # Reconstruct runtime registry and containers from saved identity.
                        old_objects = {c.name: c.get_object() for c in view.containers.values()}
                        naming._registry = NameRegistry()
                        recovered = view_class(group)
                        recovered.show()
                        assert {c.name: c.get_object() for c in recovered.containers.values()} == old_objects
                        recovered.update_group_with_view_data()
                        recovered.remove()
                        recovered.remove()
                        assert bpy.data.objects.get('same') == unrelated
                        assert bpy.data.materials.get('same') == unrelated_mat
                assert not naming.get_registry().entries
            '''))


if __name__ == '__main__':
    unittest.main()
