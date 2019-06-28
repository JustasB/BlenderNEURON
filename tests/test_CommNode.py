# From repo root, run all tests with 'python tests/test_CommNode.py'
# Run single test with: 'python tests/test_CommNode.py TestClassNameHere.test_method'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, BlenderTestCase

class TestCommNode(BlenderTestCase):
    def test_control_NEURON(self):
        def test():
            from neuron import h
            h.load_file('stdrun.hoc')
            cm1 = CommNode("NEURON")
            soma = h.Section()
            soma.insert('pas')
            soma.insert('hh')
            h.tstop = 100

            cm2 = CommNode("Blender")

            tstart = h.t
            cm2.client.run_command("h.run()")

            self.assertGreater(h.t, tstart)

        self.in_separate_process(test)

    def test_wrong_end(self):
        try:
            with CommNode("FOO") as cm:
                raise Exception("FOO should not be a valid end type")
        except:
            pass

    def test_no_client(self):
        with CommNode("NEURON") as cm:
            self.assertTrue(cm.client is None)
            self.assertTrue(cm.client_address is None)

    def test_stop_server(self):
        with CommNode("NEURON") as cm:
            cm.stop_server()

            self.assertTrue(cm.server_thread is None)
            self.assertTrue(cm.server is None)
            self.assertTrue(cm.server_address is None)

    def test_file_cleanup(self):
        with CommNode("NEURON") as cm:
            server_address_file = cm.get_end_address_file(cm.server_end)

            # Should exist before exit
            self.assertTrue(os.path.exists(server_address_file))

        # Should be gone after exit
        self.assertFalse(os.path.exists(server_address_file))

    def test_double_stop_server(self):
        with CommNode("NEURON") as cm: # Should stop on end of "with"
            pass

        self.assertTrue(cm.server_thread is None)
        self.assertTrue(cm.server is None)
        self.assertTrue(cm.server_address is None)

        # This should not blow up
        cm.stop_server()

    def test_Blender_first(self):
        with CommNode("Blender") as cm1:
            with CommNode("NEURON") as cm2:
                self.assertEqual(cm1.client.ping(), 1)
                self.assertEqual(cm2.client.ping(), 1)

    def test_NEURON_first(self):
        with CommNode("NEURON") as cm1:
            with CommNode("Blender") as cm2:
                self.assertEqual(cm1.client.ping(), 1)
                self.assertEqual(cm2.client.ping(), 1)


if __name__ == '__main__':
    unittest.main()
