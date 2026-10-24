import json
import os
import shlex
import socket
import subprocess
import tempfile
import time
from multiprocessing import Process, Queue
from queue import Empty
from unittest import TestCase
from xmlrpc.client import ServerProxy, Transport

from tests.process_utils import stop_process_group
from blenderneuron import connection


test_hoc_file = 'tests/TestCell.hoc'


class ProbeTransport(connection.AuthTransport):
    reply_timeout = 1

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = 1
        return connection


class BlenderNEURONProcess:
    executable = None
    server_end = None
    cmd_args = ''
    startup_timeout = 60

    def __init__(self, keep=False, cmd_args=None, sleep=1):
        self.keep = keep
        self.cmd_args = self.cmd_args if cmd_args is None else cmd_args
        self.sleep = sleep
        self.process = None

    def clear_server_address_file(self):
        if self.server_end is not None:
            try:
                os.remove(self.address_file(self.server_end))
            except FileNotFoundError:
                pass

    @staticmethod
    def address_file(end):
        return str(connection.config_directory() / ('BlenderNEURON-%s.address' % end))

    def wait_ready(self, connected=False):
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('%s exited during startup (status %s)' %
                                   (self.executable, self.process.returncode))
            try:
                with open(self.address_file(self.server_end)) as stream:
                    address = json.load(stream)
                with ServerProxy(address, transport=ProbeTransport(connection.local_secret())) as client:
                    if connected:
                        ready = client.run_command(
                            'node_client = bpy.types.Object.BlenderNEURON_node.client;'
                            'return_value = node_client is not None and node_client.ping() == 1')
                    else:
                        ready = client.ping() == 1
                    if ready:
                        return
            except (OSError, ValueError, socket.timeout):
                pass
            time.sleep(0.1)
        raise RuntimeError('%s did not become ready within %s seconds%s' %
                           (self.executable, self.startup_timeout,
                            ' (connection to NEURON)' if connected else ''))

    def __enter__(self):
        self.clear_server_address_file()
        try:
            self.process = subprocess.Popen(
                [self.executable] + shlex.split(self.cmd_args),
                stdin=subprocess.DEVNULL, start_new_session=True)
            if self.server_end is None:
                time.sleep(self.sleep)
            else:
                self.wait_ready()
            if self.server_end == 'Blender' and os.path.exists(self.address_file('NEURON')):
                self.wait_ready(connected=True)
            return self
        except BaseException:
            # __exit__ is not called when __enter__ fails.
            self.close()
            raise

    def close(self):
        try:
            if self.process is not None:
                stop_process_group(self.process)
        finally:
            self.clear_server_address_file()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.keep:
            self.close()


class Blender(BlenderNEURONProcess):
    executable = 'blender'
    server_end = 'Blender'
    cmd_args = '-noaudio -p 300 200 1024 600'


class NEURON(BlenderNEURONProcess):
    executable = 'nrniv'
    server_end = 'NEURON'
    cmd_args = "-python -c 'from blenderneuron import neuronstart; import time; time.sleep(3600)'"


class BlenderTestCase(TestCase):
    def in_separate_process(self, function, timeout=120):
        """Run NEURON in an isolated interpreter with bounded result/exit waits."""
        def func_with_exception(result):
            try:
                result.put([function(), None])
            except BaseException as error:
                import traceback
                traceback.print_exc()
                result.put([-1, error])

        result = Queue()
        process = Process(target=func_with_exception, args=(result,))
        process.start()
        deadline = time.monotonic() + timeout
        try:
            while True:
                try:
                    result_value, error = result.get(timeout=0.1)
                    break
                except Empty:
                    if not process.is_alive():
                        raise RuntimeError('Test worker exited without a result (status %s)' % process.exitcode)
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Test worker exceeded %s seconds' % timeout)
            process.join(timeout=3)
            if process.is_alive():
                raise TimeoutError('Test worker returned a result but failed to exit')
            if error:
                raise error
            return result_value
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=3)
            if process.is_alive():
                process.kill()
                process.join(timeout=3)
            result.close()
            result.join_thread()


def check_blender_can_run():
    with Blender():
        pass
