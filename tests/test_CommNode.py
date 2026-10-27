# From repo root, run all tests with 'python tests/test_CommNode.py'
# Run single test with: 'python tests/test_CommNode.py TestClassNameHere.test_method'

import unittest
import os, sys
from multiprocessing import Process, Queue
from time import sleep
from unittest import TestCase
from unittest.mock import Mock, patch
from blenderneuron.commnode import CommNode
from tests import test_hoc_file, Blender, NEURON, BlenderTestCase
class TestCommNode(BlenderTestCase):
    def test_control_node_retries_until_client_is_available(self):
        attempts = []

        def try_setup_client(node, warn=True):
            attempts.append(warn)
            node.client = None
            if len(attempts) == 2:
                node.client = Mock()
                node.client_connected.set()

        with patch.object(CommNode, 'try_setup_client', try_setup_client):
            with CommNode('Control-NEURON') as node:
                self.assertIsNotNone(node.client)

        self.assertEqual(attempts, [True, False])

    def test_try_setup_client_notifies_control_node(self):
        node = CommNode.__new__(CommNode)
        node.config = {
            'default_ip': {'Blender': '127.0.0.1'},
            'default_port': {'Blender': ''},
        }
        node.connection_settings = {'mode': 'local'}
        node.secret = 'a' * 64
        node.client_end = 'Blender'
        node.server_end = 'Control-NEURON'
        node.on_client_connected = None
        node.client_connected = Mock()
        client = Mock()
        client.ping.return_value = 1

        with patch.object(node, 'read_client_address_file', return_value='http://test'), \
                patch('blenderneuron.commnode.connection.proxy', return_value=client):
            node.try_setup_client()

        node.client_connected.set.assert_called_once_with()

    def test_control_node_exit_stops_and_joins_retry_thread(self):
        node = CommNode.__new__(CommNode)
        node.client_retry_stop = Mock()
        node.client_retry_thread = Mock()
        node.client_retry_thread.is_alive.return_value = True
        node.coverage = False
        node.stop_server = Mock()

        node.__exit__(None, None, None)

        node.client_retry_stop.set.assert_called_once_with()
        node.client_retry_thread.join.assert_called_once_with()
        node.stop_server.assert_called_once_with()

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

    def test_queueing_commands(self):

        with CommNode("Blender") as cm1:
            with CommNode("NEURON") as cm2:

                task1 = cm1.client.enqueue_command('a = 1')
                task2 = cm1.client.enqueue_command('b = 0')
                task3 = cm1.client.enqueue_command('c = a / b')
                task4 = cm1.client.enqueue_command('d = "never happened"')

                i = 0
                while i < 1 and cm1.client.get_task_status(task4) == 'QUEUED':
                    sleep(0.1)
                    i += 0.1

                self.assertEqual(cm1.client.get_task_status(task1), 'SUCCESS')
                self.assertEqual(cm1.client.get_task_status(task2), 'SUCCESS')
                self.assertEqual(cm1.client.get_task_status(task3), 'ERROR')
                self.assertEqual(cm1.client.get_task_status(task4), 'ERROR')

                # Should fail on non-existing task
                self.assertEqual(cm1.client.get_task_status(9999), "DOES_NOT_EXIST")



    def test_quitting_from_client(self):
        with CommNode("Blender") as cm1:
            with CommNode("NEURON") as cm2:
                cm1.client.run_command('quit()')

    def test_NEURON_first(self):
        with CommNode("NEURON") as cm1:
            with CommNode("Blender") as cm2:
                self.assertEqual(cm1.client.ping(), 1)
                self.assertEqual(cm2.client.ping(), 1)

    def test_error_handling(self):

        with NEURON(), CommNode("Control-NEURON") as ncn, \
             Blender(), CommNode("Control-Blender") as bcn:

            from xmlrpc.client import Fault

            try:
                bcn.client.run_command('1/0')
            except Fault:
                pass

            try:
                ncn.client.run_command('1/0')
            except Fault:
                pass


            bcn.client.end_code_coverage()
            ncn.client.end_code_coverage()


if __name__ == '__main__':
    unittest.main()
