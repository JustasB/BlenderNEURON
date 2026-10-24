"""Dependency-free tests, also run on native Windows CI."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import http.client
import time
import subprocess
from xmlrpc.client import ServerProxy, dumps, ProtocolError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blenderneuron.commnode import CommNode
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('connection', Path(__file__).resolve().parents[1] / 'blenderneuron' / 'connection.py')
connection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connection)


class ConnectionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, BLENDERNEURON_CONFIG_DIR=self.directory.name)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_secret_survives_restart(self):
        first = connection.local_secret()
        self.assertEqual(64, len(first))
        self.assertEqual(first, connection.local_secret())

    def test_private_atomic_settings(self):
        connection.save('NEURON-connection.json', {'secret': 'example'})
        self.assertEqual({'secret': 'example'}, connection.load('NEURON-connection.json'))
        connection.save('NEURON-connection.json', {'mode': 'local'})
        self.assertEqual({'mode': 'local'}, connection.load('NEURON-connection.json'))
        self.assertIsNone(connection.load('missing'))
        if os.name != 'nt':
            self.assertEqual(0o600, (Path(self.directory.name) / 'NEURON-connection.json').stat().st_mode & 0o777)

    def test_invalid_pairing_does_not_replace_credentials(self):
        with CommNode('NEURON') as node:
            secret = node.secret
            for pairing in ['[]', '{"version": 9, "secret": "' + secret + '"}',
                            '{"version": 1, "secret": "short"}']:
                with self.assertRaises(ValueError):
                    node.configure_connection('manual', pairing=pairing)
                self.assertEqual(secret, node.secret)
            with self.assertRaises(ValueError):
                node.configure_connection('manual', listen_port='70000')

    def test_signature_binds_entire_request(self):
        sign = connection.signature
        original = sign('a' * 64, '100', 'nonce', b'command')
        for args in [('b' * 64, '100', 'nonce', b'command'),
                     ('a' * 64, '101', 'nonce', b'command'),
                     ('a' * 64, '100', 'other', b'command'),
                     ('a' * 64, '100', 'nonce', b'stop')]:
            self.assertNotEqual(original, sign(*args))

    def test_authenticated_socket_and_replay(self):
        with CommNode('NEURON') as node:
            self.assertEqual(1, connection.proxy(node.server_address, node.secret).ping())
            with self.assertRaises(ProtocolError):
                ServerProxy(node.server_address).ping()
            with self.assertRaises(ProtocolError):
                connection.proxy(node.server_address, 'b' * 64).run_command('raise RuntimeError()')
            body = dumps((), methodname='ping').encode()
            stamp, nonce = str(int(time.time())), 'a' * 32
            challenge = http.client.HTTPConnection(node.server_ip, int(node.server_port))
            challenge.request('GET', '/RPC2')
            epoch = challenge.getresponse().read().decode('ascii')
            challenge.close()
            headers = {'X-BN-Epoch': epoch, 'X-BN-Time': stamp, 'X-BN-Nonce': nonce,
                       'X-BN-Signature': connection.signature(node.secret, stamp, epoch + nonce, body)}
            def request():
                client = http.client.HTTPConnection(node.server_ip, int(node.server_port), timeout=5)
                client.request('POST', '/RPC2', body, headers)
                response = client.getresponse()
                status = response.status
                response.read()
                client.close()
                return status
            self.assertEqual(200, request())
            self.assertEqual(403, request())
            headers['X-BN-Nonce'] = 'b' * 32
            self.assertEqual(403, request())  # modified nonce, unchanged signature
            stamp = str(int(time.time()) - 120)
            headers.update({'X-BN-Time': stamp,
                            'X-BN-Signature': connection.signature(node.secret, stamp, epoch + 'b' * 32, body)})
            self.assertEqual(403, request())
            for method in ['stop', 'system.listMethods', 'enqueue_command']:
                with self.assertRaises(ProtocolError):
                    getattr(ServerProxy(node.server_address), method)()
            self.assertEqual(1, connection.proxy(node.server_address, node.secret).ping())
            old_secret = node.secret
            node.forget_connection()
            with self.assertRaises(ProtocolError):
                connection.proxy(node.server_address, old_secret).ping()

    def test_remote_peer_with_separate_user_directory_and_restart(self):
        with CommNode('NEURON') as node, tempfile.TemporaryDirectory() as remote_directory:
            node.configure_connection('manual', listen_port=node.server_port)
            script = """
import json, sys
from blenderneuron.commnode import CommNode
from blenderneuron import connection
info = json.loads(sys.argv[1])
with CommNode('Blender') as peer:
    peer.configure_connection('manual', pairing=json.dumps(info), listen_port=peer.server_port)
    assert peer.test_connection()
    print(peer.pairing_information(), flush=True)
    connection.save('published.json', peer.pairing_information())
    assert sys.stdin.readline().strip() == 'restart'
# New node reads the saved fixed port, credentials, and peer endpoint.
with CommNode('Blender') as peer:
    assert peer.test_connection()
    print('reconnected', flush=True)
"""
            environment = dict(os.environ, BLENDERNEURON_CONFIG_DIR=remote_directory)
            process = subprocess.Popen([sys.executable, '-c', script, node.pairing_information()],
                                       env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, universal_newlines=True)
            try:
                published = Path(remote_directory) / 'published.json'
                deadline = time.monotonic() + 10
                while not published.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(published.exists())
                node.configure_connection('manual', pairing=json.loads(published.read_text()),
                                          listen_port=node.server_port)
                self.assertTrue(node.test_connection())
                # communicate bounds worker restart and shutdown.
                output, errors = process.communicate('restart\n', timeout=30)
                self.assertEqual(0, process.returncode, errors)
                lines = [line for line in output.splitlines() if line.startswith('{')]
                self.assertEqual(1, len(lines), output)
                info = json.loads(lines[0])
                self.assertEqual(node.secret, info['secret'])
                self.assertIn('reconnected', output)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_pairing_persistence_and_overrides(self):
        with CommNode('NEURON') as node:
            information = node.pairing_information()
            node.configure_connection('manual', pairing=information,
                                      peer_address='http://127.0.0.1:12345', listen_port='12346')
            secret = node.secret
            node.configure_connection('local')
            node.configure_connection('manual')
            self.assertEqual(secret, node.secret)
            self.assertEqual('http://127.0.0.1:12345', node.connection_settings['peer_address'])
            node.forget_connection()
            self.assertNotEqual(secret, node.secret)
            self.assertNotIn('peer_address', node.connection_settings)


if __name__ == '__main__':
    unittest.main()
