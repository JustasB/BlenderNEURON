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
    def test_server_established(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            # Create a node that controls Blender but Blender will not control it back
            # This will allow us to have Blender start a NEURON process which it does control
            # But allow us to control Blender as a 3rd party for testing
            with CommNode("NEURON", connect_back=False) as control_node:
                self.assertEqual(control_node.client.ping(), 1)

    def test_can_launch_and_stop_neuron(self):
        # Start Blender with a running node
        with Blender(cmd_args="--python blenderneuron/__init__.py", sleep=3):
            # Create a node that controls Blender but Blender will not control it back
            # This will allow us to have Blender start a NEURON process which it does control
            # But allow us to control Blender as a 3rd party for testing
            with CommNode("NEURON", connect_back=False) as control_node:
                # Tell Blender to launch own NEURON process
                control_node.client.run_command("bpy.ops.wm.blenderneuron_launch_neuron()")
                sleep(1)

                # See if Blender is able to connect to the NEURON process node
                result = control_node.client.run_command("return_value = str(bpy.types.Object.BlenderNEURON_node.client)")
                self.assertIn("Proxy", result)

                # Stop NEURON
                control_node.client.run_command("bpy.ops.wm.blenderneuron_stop_neuron()")

                # Check if the client was cleaned up
                result = control_node.client.run_command("return_value = str(bpy.types.Object.BlenderNEURON_node.client)")
                self.assertIn("None", result)


if __name__ == '__main__':
    unittest.main()
