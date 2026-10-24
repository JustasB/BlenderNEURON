"""Scene-wide animation timing, including existing material and shader curves."""
import unittest
from textwrap import dedent
from blenderneuron.commnode import CommNode
from tests import BackgroundBlender as Blender, BlenderTestCase


class TestSceneTiming(BlenderTestCase):
    def test_shared_timing_and_retime(self):
        with Blender(), CommNode('Control-Blender', coverage=True) as control:
            control.client.run_command(dedent('''
                import numpy as np
                from types import SimpleNamespace
                from blenderneuron.blender.views.objectview import ObjectViewAbstract
                settings = bpy.context.scene.BlenderNEURON.simulator_settings
                assert settings.frames_per_ms == 10
                def curves(data):
                    action = data.animation_data.action
                    if hasattr(action, 'fcurves'):
                        return list(action.fcurves)
                    return [f for layer in action.layers for strip in layer.strips
                            for bag in strip.channelbags for f in bag.fcurves]
                materials = []
                for index, obsolete_scale in enumerate((1, 100)):
                    material = bpy.data.materials.new('SceneTiming' + str(index))
                    material.use_nodes = True
                    material.node_tree.nodes.new('ShaderNodeEmission').name = 'Emission'
                    bpy.ops.mesh.primitive_cube_add()
                    bpy.context.object.data.materials.append(material)
                    view = ObjectViewAbstract.__new__(ObjectViewAbstract)
                    view.group = SimpleNamespace(frames_per_ms=obsolete_scale,
                        max_brightness=2, animate_color=False, animate_brightness=True,
                        animation_range_low=-80, animation_range_high=40)
                    trace = SimpleNamespace(times=np.array([0, 5, 10]), values=np.array([-65., 30., -65.]))
                    view.animate_activity(trace, material.name)
                    materials.append(material)
                def check(expected):
                    for material in materials:
                        for data in (material, material.node_tree):
                            for curve in curves(data):
                                assert [round(p.co.x, 4) for p in curve.keyframe_points] == expected
                check([0, 50, 100])
                settings.frames_per_ms = 2
                check([0, 10, 20])
                settings.frames_per_ms = 10
                check([0, 50, 100])
                bpy.context.scene.frame_set(50)
                for material in materials:
                    assert abs(material['recorded_value'] - 30) < .001
            '''))


if __name__ == '__main__':
    unittest.main()
