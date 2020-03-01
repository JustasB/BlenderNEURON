# From repo root, run all tests with 'python tests/test_render.py'
# Run single test with: 'python tests/test_render.py TestRender.test_glare'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, NEURON, BlenderTestCase


class TestRender(BlenderTestCase):
    def test_glare(self):
        with NEURON(), CommNode("Control-NEURON", coverage=True) as ncn, \
                Blender(), CommNode("Control-Blender", coverage=True) as bcn:

            bcn.client.run_command('bpy.ops.blenderneuron.add_neon_effect();')

            # Adding 2nd time should not fail either
            bcn.client.run_command('bpy.ops.blenderneuron.add_neon_effect();')


if __name__ == '__main__':
    unittest.main()
