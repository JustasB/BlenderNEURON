"""Exercise deep group files through Blender export and NEURON geometry updates."""
import json
import os
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from textwrap import dedent
from xmlrpc.client import dumps, loads

from neuron import h
from blenderneuron.commnode import CommNode
from blenderneuron.nrn.neuronnode import NeuronNode
from blenderneuron.rootgroup import RootGroup
from blenderneuron.utils import serialize
from tests import BackgroundBlender, BlenderTestCase


class TestGroupFile(BlenderTestCase):
    def test_from_file_rejects_invalid_group_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'group.json')
            for payload in ['not json', '{"name":"old","roots":[]}',
                            serialize(None), serialize([]),
                            serialize({'name': 'missing-roots'}),
                            serialize({'name': 'invalid-roots', 'roots': {}})]:
                with self.subTest(payload=payload):
                    path.write_text(payload, encoding='utf-8')
                    with self.assertRaises(ValueError):
                        RootGroup.from_file(path)
            with self.assertRaises(FileNotFoundError):
                RootGroup.from_file(Path(directory, 'missing.json'))

    def test_deep_file_and_rpc_geometry_roundtrip(self):
        depth = 1500
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'nested', 'α-group.json')
            with BackgroundBlender(), CommNode('Control-Blender') as control:
                control.client.run_command(dedent('''
                    from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
                    from blenderneuron.rootgroup import RootGroup
                    from blenderneuron.section import Section
                    group = BlenderRootGroup.__new__(BlenderRootGroup)
                    RootGroup.__init__(group)
                    group.name = 'deep-export'
                    group.view = None
                    parent = None
                    for index in range(%d):
                        section = Section()
                        section.name = 'deep_export_%%d' %% index
                        section.nseg = 1
                        section.point_count = 2
                        section.coords = [index, 0, 7, index + 1, 0, 7]
                        section.radii = [1, 1]
                        if parent is None:
                            group.roots[section.name] = section
                        else:
                            parent.children.append(section)
                        parent = section
                    group.to_file(%r)
                    loaded = group.from_file(%r)
                    assert loaded['name'] == group.name
                    assert loaded['roots'][0]['name'] == 'deep_export_0'
                    with open(%r, encoding='utf-8') as stream:
                        before = stream.read()
                    parent.nseg = set()
                    try:
                        group.to_file(%r)
                    except TypeError:
                        pass
                    else:
                        raise AssertionError('Unsupported value was accepted')
                    with open(%r, encoding='utf-8') as stream:
                        assert stream.read() == before
                ''') % (depth, path, path, path, path, path))

            with open(path) as stream:
                table = json.load(stream)
            self.assertEqual(table['__blenderneuron_flat__'], 2)
            # Native JSON can also write the resulting storage table safely.
            original_table = json.dumps(table)
            group_dict = RootGroup.from_file(Path(path))
            section_dict = group_dict['roots'][0]
            for index in range(depth):
                self.assertEqual(section_dict['name'], 'deep_export_%d' % index)
                self.assertEqual(section_dict['coords'][2], 7)
                if index + 1 < depth:
                    section_dict = section_dict['children'][0]
            self.assertEqual(section_dict['children'], [])

            h.load_file('stdrun.hoc')
            sections = [h.Section(name='deep_export_%d' % i) for i in range(depth)]
            for parent, child in zip(sections, sections[1:]):
                child.connect(parent)
            node = NeuronNode.__new__(NeuronNode)
            node.groups = OrderedDict()
            node.parallel_ctx = None
            node.mpimap = None
            node.mpi_coordinator_active = False
            node.update_section_index()
            for payload in ([table], table, serialize([group_dict])):
                node.update_groups(payload)
                self.assertEqual(h.z3d(0, sec=sections[-1]), 7)
                self.assertEqual(h.diam3d(0, sec=sections[-1]), 2)
            self.assertEqual(json.dumps(table), original_table)

            # XML-RPC sees only a binary payload, never the nested morphology.
            binary = node.compress([group_dict])
            received = loads(dumps((binary,), allow_none=True))[0][0]
            node.update_groups(received)
            self.assertEqual(h.z3d(0, sec=sections[-1]), 7)


if __name__ == '__main__':
    unittest.main()
