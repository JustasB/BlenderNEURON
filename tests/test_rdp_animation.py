"""Verify the reference and optimized traces drive identical Blender channels."""
import unittest
from textwrap import dedent
from blenderneuron.commnode import CommNode
from tests import Blender, BlenderTestCase


class TestRDPAnimation(BlenderTestCase):
    def test_material_channels_and_scrubbing(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            result = control.client.run_command(dedent('''
                import numpy as np
                from types import SimpleNamespace
                from blenderneuron.activity import Activity
                from blenderneuron.blender.views.objectview import ObjectViewAbstract
                from blenderneuron.blender.utils import COLOR_RAMP_NAME
                from tests.rdp_reference import rdp as reference

                times = np.linspace(0, 25, 250)
                values = -65 + 100*np.exp(-((times-8)/.65)**2) - 12*np.exp(-((times-10)/1.3)**2)
                expected = reference(np.column_stack((times, values)), .1)
                activity = Activity()
                activity.times, activity.values = times.copy(), values.copy()
                activity.simplify(.1)
                np.testing.assert_array_equal(np.column_stack((activity.times, activity.values)), expected)
                ramp = bpy.data.materials.new('rdp_ramp')
                ramp.use_nodes = True
                ramp.node_tree.nodes.new('ShaderNodeValToRGB').name = COLOR_RAMP_NAME
                view = ObjectViewAbstract.__new__(ObjectViewAbstract)
                view.group = SimpleNamespace(frames_per_ms=10, max_brightness=2,
                    animate_brightness=True, animate_color=True,
                    animation_range_low=-80, animation_range_high=40, color_ramp_material=ramp)
                materials = []
                for name, trace in [('rdp_reference', SimpleNamespace(times=expected[:, 0], values=expected[:, 1])),
                                    ('rdp_current', activity)]:
                    material = bpy.data.materials.new(name)
                    material.use_nodes = True
                    material.node_tree.nodes.new('ShaderNodeEmission').name = 'Emission'
                    view.animate_activity(trace, name)
                    materials.append(material)
                action = materials[1].animation_data.action
                if hasattr(action, 'fcurve_ensure_for_datablock'):
                    raw = action.fcurve_ensure_for_datablock(materials[1], '["recorded_value"]')
                else:
                    raw = action.fcurves.find('["recorded_value"]')
                np.testing.assert_array_equal([p.co.y for p in raw.keyframe_points], expected[:, 1].astype(np.float32))
                engines = ['BLENDER_WORKBENCH', 'CYCLES',
                           'BLENDER_EEVEE_NEXT' if bpy.app.version >= (4, 2, 0) else 'BLENDER_EEVEE']
                for engine in engines:
                    bpy.context.scene.render.engine = engine
                    for frame in [0, 80, 100, 250, 40, 80, 0]:
                        bpy.context.scene.frame_set(frame)
                        def channels(mat):
                            emit = mat.node_tree.nodes['Emission']
                            return [mat['recorded_value'], *mat.diffuse_color,
                                    *emit.inputs['Color'].default_value, emit.inputs['Strength'].default_value]
                        np.testing.assert_array_equal(channels(materials[0]), channels(materials[1]))
                return_value = len(raw.keyframe_points)
            '''))
            self.assertGreater(result, 2)


if __name__ == '__main__':
    unittest.main()
