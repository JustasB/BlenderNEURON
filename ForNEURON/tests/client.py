import unittest

# Example assertions:
# self.assertEqual('foo'.upper(), 'FOO')
# self.assertTrue('FOO'.isupper())
# self.assertFalse('Foo'.isupper())

# with self.assertRaises(TypeError):
#     s.split(2)

import os, sys
from multiprocessing import Process
from time import sleep
from unittest import TestCase

sys.path.append("..")

class Blender:
    def __init__(self, keep=False):
        self.keep = keep
        self.blender = Process(target=self.start_Blender)

    def start_Blender(self):
        os.system("blender")

    def __enter__(self):
        self.blender.start()
        sleep(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep:
            os.system("pkill -9 blender")
            self.blender.join()


class BlenderTestCase(TestCase):
    def in_separate_process(self, function):
        p = Process(target=function);
        p.start();
        p.join();


class TestMorphologyExport(BlenderTestCase):
    def test_ping(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                self.assertTrue(bn.is_blender_ready())

        self.in_separate_process(test)

    def test_run_command(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                self.assertTrue(bn.run_command("print('Test')") is None)
                self.assertTrue(bn.run_command("return_value = 1+3") == 4)
                self.assertTrue(bn.run_command("return_value = 'Camera' in bpy.data.objects"))

        self.in_separate_process(test)

    def test_single_compartment(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                from neuron import h
                soma = h.Section(name="Soma")
                soma.L = soma.diam = 10

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'Soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = bpy.data.objects['Soma'].dimensions == mathutils.Vector((10.020000457763672, 10.0, 10.0))"))

        self.in_separate_process(test)

    def test_multi_compartment(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                from neuron import h
                h.load_file('TestCell.hoc')
                tc = h.TestCell()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = len([i for i in bpy.data.objects if 'dendrites' in i.name]) == 31"))

        self.in_separate_process(test)

    def test_multiple_root_sections(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                from neuron import h
                soma1 = h.Section(name="Soma1")
                soma2 = h.Section(name="Soma2")

                soma1.L = soma2.L = soma1.diam = soma2.diam = 5

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'Soma1' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'Soma2' in bpy.data.objects"))

        self.in_separate_process(test)

    def test_multiple_cells(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.objects"))

        self.in_separate_process(test)

    def test_add_cell_and_reexport(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                from neuron import h
                h.load_file('TestCell.hoc')

                # Add one cell
                tc1 = h.TestCell()
                bn.to_blender()

                # Check if it was exported
                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))

                # Add a second cell
                tc2 = h.TestCell()

                # Refresh sections
                bn.refresh()
                bn.to_blender()

                # Both cells should be in blender
                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = len([i for i in bpy.data.objects if 'soma' in i.name]) == 2"))

        self.in_separate_process(test)

    def test_group_interaction_group_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Group"
                bn.groups["all"]["3d_data"]["color_level"] = "Group"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['allGroup'].emit") == 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['allGroup'].emit") - 1.06 < 0.1)

        self.in_separate_process(test)

    def test_group_interaction_cell_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender():
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Group"
                bn.groups["all"]["3d_data"]["color_level"] = "Cell"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[0]'].emit") == 0.0)
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[1]'].emit") == 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[0]'].emit") == 2.0)
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[1]'].emit") == 0.0)

        self.in_separate_process(test)

    def test_group_interaction_section_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Group"
                bn.groups["all"]["3d_data"]["color_level"] = "Section"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma'].emit") == 0.0)
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma'].emit") == 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma'].emit") == 2.0)
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma'].emit") == 0.0)

        self.in_separate_process(test)

    def test_group_interaction_segment_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Group"
                bn.groups["all"]["3d_data"]["color_level"] = "Segment"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma[0]' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma[0]' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma[0]'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma[0]'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma[0]'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma[0]'].emit"), 0.0)

        self.in_separate_process(test)


    def test_cell_interaction_group_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Cell"
                bn.groups["all"]["3d_data"]["color_level"] = "Group"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['allGroup'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['allGroup'].emit"), 1.069335699081421)

        self.in_separate_process(test)

    def test_cell_interaction_cell_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Cell"
                bn.groups["all"]["3d_data"]["color_level"] = "Cell"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0]'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1]'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0]'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1]'].emit"), 0.0)

        self.in_separate_process(test)

    def test_cell_interaction_section_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Cell"
                bn.groups["all"]["3d_data"]["color_level"] = "Section"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma'].emit"), 0.0)

        self.in_separate_process(test)

    def test_cell_interaction_segment_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Cell"
                bn.groups["all"]["3d_data"]["color_level"] = "Segment"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma[0]' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma[0]' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma[0]'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma[0]'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma[0]'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma[0]'].emit"), 0.0)

        self.in_separate_process(test)


    def test_section_interaction_group_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Section"
                bn.groups["all"]["3d_data"]["color_level"] = "Group"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'allGroup' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['allGroup'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['allGroup'].emit"), 1.069335699081421)

        self.in_separate_process(test)

    def test_section_interaction_cell_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Section"
                bn.groups["all"]["3d_data"]["color_level"] = "Cell"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'TestCell[0]' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1]' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0]'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1]'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0]'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1]'].emit"), 0.0)

        self.in_separate_process(test)

    def test_section_interaction_section_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Section"
                bn.groups["all"]["3d_data"]["color_level"] = "Section"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma'].emit"), 0.0)

        self.in_separate_process(test)

    def test_section_interaction_segment_color_levels(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc1 = h.TestCell()
                tc2 = h.TestCell()

                ic = h.IClamp(0.5, sec=tc1.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                bn.groups["all"]["3d_data"]["interaction_level"] = "Section"
                bn.groups["all"]["3d_data"]["color_level"] = "Segment"

                h.run()

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma' in bpy.data.objects"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma' in bpy.data.objects"))

                self.assertTrue(bn.run_command("return_value = 'TestCell[0].soma[0]' in bpy.data.materials"))
                self.assertTrue(bn.run_command("return_value = 'TestCell[1].soma[0]' in bpy.data.materials"))

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 0")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma[0]'].emit"), 0.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma[0]'].emit"), 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7")
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[0].soma[0]'].emit"), 2.0)
                self.assertEqual(bn.run_command("return_value = bpy.data.materials['TestCell[1].soma[0]'].emit"), 0.0)

        self.in_separate_process(test)


class TestConnectionExport(BlenderTestCase):
    def test_synapse(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h

                s1 = h.Section(name="Soma1")
                s2 = h.Section(name="Soma2")
                s1.L = s1.diam = s2.L = s2.diam = 10

                syn = h.Exp2Syn(0.5, sec=s2)
                syn.g = 10

                nc = h.NetCon(s1(0.5)._ref_v, syn, sec=s1)
                nc.weight[0] = 1

                bn.to_blender()

                self.assertTrue(bn.run_command("return_value = bpy.data.objects['SynapsesGroup'].dimensions == mathutils.Vector((4.0, 4.0, 101.02000427246094))"))

        self.in_separate_process(test)

class TestActivityExport(BlenderTestCase):

    def test_activity_export(self):
        def test():
            from blenderneuron.quick import bn

            with Blender(keep=False):
                import pydevd
                pydevd.settrace('192.168.0.34', port=4200, suspend=False)

                from neuron import h
                h.load_file('TestCell.hoc')
                tc = h.TestCell()

                ic = h.IClamp(0.5, sec=tc.soma)
                ic.delay = 1
                ic.dur = 3
                ic.amp = 0.5

                bn.prepare_for_collection()
                h.run()
                bn.to_blender()

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 1;")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[0].dendrites[9][0]'].emit") == 0.0)

                bn.run_command("bpy.data.scenes['Scene'].frame_current = 7;")
                self.assertTrue(bn.run_command("return_value = bpy.data.materials['TestCell[0].dendrites[9][0]'].emit") == 2.0)


        self.in_separate_process(test)

if __name__ == '__main__':
    unittest.main()