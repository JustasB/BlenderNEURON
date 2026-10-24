"""Verify a fixed simplified trace drives the expected Blender channels."""
import inspect
import unittest
from textwrap import dedent
from blenderneuron.commnode import CommNode
from tests import BackgroundBlender as Blender, BlenderTestCase
from tests import select_eevee_engine


class TestRenderEngineSelection(unittest.TestCase):
    def test_supported_identifiers(self):
        for supported, expected in (({'BLENDER_EEVEE'}, 'BLENDER_EEVEE'),
                                    ({'BLENDER_EEVEE_NEXT'}, 'BLENDER_EEVEE_NEXT'),
                                    ({'BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'}, 'BLENDER_EEVEE_NEXT'),
                                    (set(), None)):
            with self.subTest(supported=supported):
                class Render:
                    @property
                    def engine(self):
                        return self.selected

                    @engine.setter
                    def engine(self, value):
                        if value not in supported:
                            raise TypeError('Unsupported render-engine enum')
                        self.selected = value

                render = Render()
                if expected is None:
                    with self.assertRaisesRegex(AssertionError, 'No supported EEVEE'):
                        select_eevee_engine(render)
                else:
                    self.assertEqual(select_eevee_engine(render), expected)
                    self.assertEqual(render.engine, expected)

    def test_unexpected_errors_are_not_hidden(self):
        class BrokenRender:
            def __setattr__(self, name, value):
                raise RuntimeError('Unexpected engine initialization failure')

        with self.assertRaisesRegex(RuntimeError, 'Unexpected engine initialization'):
            select_eevee_engine(BrokenRender())


class TestRDPAnimation(BlenderTestCase):
    def test_material_channels_and_scrubbing(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            # Official Blender builds ignore PYTHONPATH by default, so send the
            # helper source instead of importing the host-only tests package.
            result = control.client.run_command('\n' + inspect.getsource(select_eevee_engine) + dedent('''
                import numpy as np
                from types import SimpleNamespace
                from blenderneuron.activity import Activity
                from blenderneuron.blender.views.objectview import ObjectViewAbstract
                from blenderneuron.blender.utils import COLOR_RAMP_NAME
                times = np.array([0., 2.5, 5., 7.5, 10., 12.5, 15., 20., 25.])
                values = np.array([-65., -65., -65., -15., 35., -15., -65., -65., -65.])
                expected = np.array([[0., -65.], [5., -65.], [10., 35.], [15., -65.], [25., -65.]])
                activity = Activity()
                activity.times, activity.values = times.copy(), values.copy()
                activity.simplify(.1)
                np.testing.assert_array_equal(np.column_stack((activity.times, activity.values)), expected)
                ramp = bpy.data.materials.new('rdp_ramp')
                ramp.use_nodes = True
                ramp.node_tree.nodes.new('ShaderNodeValToRGB').name = COLOR_RAMP_NAME
                bpy.context.scene.BlenderNEURON.simulator_settings.frames_per_ms = 10
                view = ObjectViewAbstract.__new__(ObjectViewAbstract)
                view.group = SimpleNamespace(frames_per_ms=10, max_brightness=2,
                    animate_brightness=True, animate_color=True,
                    animation_range_low=-80, animation_range_high=40, color_ramp_material=ramp)
                materials = []
                for name, trace in [('rdp_expected', SimpleNamespace(times=expected[:, 0], values=expected[:, 1])),
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
                np.testing.assert_array_equal([p.co.x for p in raw.keyframe_points], expected[:, 0] * 10)
                eevee = select_eevee_engine(bpy.context.scene.render)
                engines = ['BLENDER_WORKBENCH', 'CYCLES', eevee]
                for engine in engines:
                    bpy.context.scene.render.engine = engine
                    for frame in [0, 50, 100, 150, 250, 75, 100, 0]:
                        bpy.context.scene.frame_set(frame)
                        def channels(mat):
                            emit = mat.node_tree.nodes['Emission']
                            return [mat['recorded_value'], *mat.diffuse_color,
                                    *emit.inputs['Color'].default_value, emit.inputs['Strength'].default_value]
                        np.testing.assert_array_equal(channels(materials[0]), channels(materials[1]))
                return_value = len(raw.keyframe_points)
            '''))
            self.assertEqual(result, 5)


if __name__ == '__main__':
    unittest.main()
