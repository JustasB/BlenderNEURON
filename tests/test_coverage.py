# From repo root, run all tests with 'python tests/test_blender_node.py'
# Run single test with: 'python tests/test_blender_node.py TestBlenderNode.test_method'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, NEURON, BlenderTestCase

class TestCoverage(BlenderTestCase):
    def test_blender_coverage(self):

        with NEURON(), Blender(), \
             CommNode('Control-NEURON') as cn, \
             CommNode("Control-Blender") as cb:

                self.assertEqual(cn.client.ping(), 1)
                self.assertEqual(cb.client.ping(), 1)

                cn.client.end_code_coverage()
                cb.client.end_code_coverage()


if __name__ == '__main__':
    unittest.main()

