"""Live NEURON round trips with the opt-in prototype enabled (run in Docker)."""
import sys
sys.path.insert(0, '/BlenderNEURON')
import unittest
from tests import NEURON, BackgroundBlender, BlenderTestCase
from blenderneuron.commnode import CommNode


class SomaRoundTrip(BlenderTestCase):
    def test_live_roundtrip(self):
        with NEURON(), CommNode('Control-NEURON') as nrn, BackgroundBlender(), CommNode('Control-Blender') as blender:
            nrn.client.run_command('''
cells = [h.Section(name='soma0'), h.Section(name='soma1')]
for i, sec in enumerate(cells):
    sec.nseg = 3
    h.pt3dclear(sec=sec)
    for x in (0, 2, 10):
        h.pt3dadd(x, i*30, 0, 10, sec=sec)
''')
            snapshot = '''
return_value = [(s.name(), s.L, s.nseg, [(s.x3d(i), s.y3d(i), s.z3d(i), s.diam3d(i)) for i in range(s.n3d())], sum(seg.area() for seg in s)) for s in cells]
'''
            original = nrn.client.run_command(snapshot)
            blender.client.run_command('bpy.ops.blenderneuron.get_cell_list_from_neuron()')
            for interaction in ('Cell', 'Group'):
                for recording in ('Cell', 'Section', '3D Segment'):
                    blender.client.run_command('''
from blenderneuron.blender.somadisplay import attach, detach
ui = bpy.context.scene.BlenderNEURON.groups[0]
ui.interaction_granularity = %r
ui.recording_granularity = %r
bpy.ops.blenderneuron.import_groups()
group = ui.node_group
for container in group.view.containers.values():
    modifier = attach(container)
    assert modifier.show_viewport
bpy.ops.blenderneuron.export_groups()
''' % (interaction, recording))
                    self.assertEqual(nrn.client.run_command(snapshot), original)
                    blender.client.run_command('''
ui.spherize_soma_if_DeqL = False
assert all('blenderneuron_soma_display' not in c.object for c in group.view.containers.values())
bpy.ops.blenderneuron.export_groups()
ui.spherize_soma_if_DeqL = True
assert all('blenderneuron_soma_display' in c.object for c in group.view.containers.values())
bpy.ops.blenderneuron.import_groups()
bpy.ops.blenderneuron.export_groups()
''')
                    self.assertEqual(nrn.client.run_command(snapshot), original)


if __name__ == '__main__':
    unittest.main()
