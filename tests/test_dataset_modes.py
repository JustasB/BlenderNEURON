"""One scene source at a time, explicit transitions, and offline .blend recovery."""
import os
from pathlib import Path
import shlex
import tempfile

from tests import BackgroundBlender, NEURON
from tests import test_offline
from blenderneuron.commnode import CommNode


from tests import BlenderTestCase
class TestDatasetSource(BlenderTestCase):
    def producer(self, *args, **kwargs):
        return test_offline.TestOffline.__dict__['producer'](self, *args, **kwargs)

    def test_explicit_switching_and_reconnect_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.producer(directory)
            with NEURON() as neuron, BackgroundBlender():
                control = CommNode('Control-Blender')
                script = '''
import bpy
from types import SimpleNamespace
from blenderneuron.blender.dataset import is_offline, SOURCE
from blenderneuron.blender.operators.rootgroup import ImportSimulationResultsOperator, ExportGroupsOperator
from blenderneuron.blender.operators.connection import SwitchToLiveOperator
node = bpy.types.Object.BlenderNEURON_node
assert node.client is not None
old_groups = list(node.groups)
# A scripted/stale action cannot silently replace the active live dataset.
try:
    bpy.ops.blenderneuron.import_simulation_results(filepath=PATH)
except RuntimeError:
    pass
else:
    raise AssertionError('Missing live replacement confirmation')
assert not is_offline() and node.client is not None
assert list(node.groups) == old_groups
# Invoking the confirmation makes no changes until its execute step is accepted.
requests = []
window = SimpleNamespace(invoke_props_dialog=lambda op, **kw: requests.append(op) or {'RUNNING_MODAL'})
op = SimpleNamespace(node=node, filepath=PATH, replace_live=False,
                     options=SimpleNamespace(is_invoke=True), report=lambda *args: None)
assert ImportSimulationResultsOperator.execute(op, SimpleNamespace(window_manager=window)) == {'RUNNING_MODAL'}
assert requests == [op] and op.replace_live
assert not is_offline() and node.client is not None
assert bpy.ops.blenderneuron.import_simulation_results(filepath=PATH, replace_live=True) == {'FINISHED'}
assert is_offline() and node.client is None
assert bpy.context.scene[SOURCE] == PATH
assert node.test_connection() is False
assert node.client is None
try:
    ExportGroupsOperator.execute(SimpleNamespace(node=node), bpy.context)
except RuntimeError:
    pass
else:
    raise AssertionError('Direct offline export was accepted')
try:
    bpy.ops.blenderneuron.connection_settings(action='CONNECT')
except RuntimeError:
    pass
assert is_offline() and node.groups
# Canceling a mode-switch confirmation leaves cells and mode untouched.
assert SwitchToLiveOperator.invoke(op, SimpleNamespace(window_manager=window), None) == {'RUNNING_MODAL'}
assert is_offline() and node.groups
assert bpy.ops.blenderneuron.switch_to_live() == {'FINISHED'}
assert not is_offline() and not node.groups and not node.root_index
assert node.client is None
assert bpy.ops.blenderneuron.connection_settings(action='CONNECT') == {'FINISHED'}
assert node.client is not None and not node.groups
node.client.run_command("soma = h.Section(name='soma'); h.pt3dadd(0,0,0,2,sec=soma); h.pt3dadd(10,0,0,2,sec=soma)")
group = node.add_group()
node.import_groups_from_neuron([group])
node.display_groups()
assert group.view is not None
saved_group = group
saved_objects = len(bpy.data.objects)
return_value = True
'''.replace('PATH', repr(path))
                self.assertTrue(control.client.run_command(script))
                neuron.close()
                self.assertTrue(control.client.run_command('''
assert node.test_connection() is False
assert not is_offline() and node.groups[group.name] is saved_group
assert len(bpy.data.objects) == saved_objects
return_value = True
'''))
                # A different process can have the same section name. Reconnect
                # warns rather than claiming to know whether the model changed.
                with NEURON():
                    self.assertTrue(control.client.run_command('''
assert node.test_connection()
assert node.export_requires_confirmation
node.client.run_command("soma = h.Section(name='soma'); h.pt3dadd(0,0,0,2,sec=soma); h.pt3dadd(10,0,0,2,sec=soma)")
try:
    bpy.ops.blenderneuron.export_groups()
except RuntimeError:
    pass
else:
    raise AssertionError('Reconnect export did not require consent')
assert node.export_requires_confirmation
assert bpy.ops.blenderneuron.export_groups(confirm_reconnected=True) == {'FINISHED'}
assert not node.export_requires_confirmation
return_value = True
'''))

    def test_offline_scene_reopens_without_source_or_live_pairing(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.producer(directory)
            blend = str(Path(directory) / 'offline.blend')
            with BackgroundBlender():
                control = CommNode('Control-Blender')
                self.assertTrue(control.client.run_command('''
import bpy
assert bpy.ops.blenderneuron.import_simulation_results(filepath=PATH) == {'FINISHED'}
node = bpy.types.Object.BlenderNEURON_node
group = node.groups['Network']
group.default_color = [0, 1, 0, 1]
group.interaction_granularity = 'Section'
node.display_groups()
container = next(iter(group.view.containers.values()))
container.object.location.x += 12
bpy.context.scene.BlenderNEURON.simulator_settings.frames_per_ms = 20
bpy.context.scene['test_object_count'] = len(bpy.data.objects)
bpy.context.scene['test_saved_x'] = container.object.location.x
bpy.context.scene['test_container_name'] = container.object.name
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
return_value = True
'''.replace('PATH', repr(path)).replace('BLEND', repr(blend))))
            Path(path).unlink()
            with NEURON(), BackgroundBlender(cmd_args=shlex.quote(blend)):
                control = CommNode('Control-Blender')
                self.assertTrue(control.client.run_command('''
import bpy
from blenderneuron.blender.dataset import is_offline, SOURCE
scene = bpy.context.scene
node = bpy.types.Object.BlenderNEURON_node
assert is_offline() and node.client is None
assert scene[SOURCE] == PATH
assert node.test_connection() is False
assert set(node.groups) == {'Network'}
group = node.groups['Network']
assert list(group.default_color) == [0, 1, 0, 1]
assert group.interaction_granularity == 'Section'
assert group.view is not None
assert scene.BlenderNEURON.simulator_settings.frames_per_ms == 20
assert len(bpy.data.objects) == scene['test_object_count']
assert bpy.data.objects[scene['test_container_name']].location.x == scene['test_saved_x']
assert group.roots[next(iter(group.roots))].activity.times.size > 0
return_value = True
'''.replace('PATH', repr(path))))


if __name__ == '__main__':
    import unittest
    unittest.main()
