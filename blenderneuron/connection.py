"""Standard-library connection storage and authenticated XML-RPC transport.

Authentication does not encrypt traffic: remote connections require SSH tunnels.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
from xmlrpc.client import Transport, ServerProxy


def config_directory():
    override = os.environ.get('BLENDERNEURON_CONFIG_DIR')
    if override:
        directory = Path(override)
    elif os.name == 'nt':
        directory = Path(os.environ['LOCALAPPDATA']) / 'BlenderNEURON'
    elif sys.platform == 'darwin':
        directory = Path.home() / 'Library' / 'Application Support' / 'BlenderNEURON'
    else:
        directory = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'blenderneuron'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        directory.chmod(0o700)
    return directory


def save(name, value):
    directory = config_directory()
    fd, temporary = tempfile.mkstemp(dir=str(directory))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
        os.replace(temporary, str(directory / name))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load(name, default=None):
    try:
        with (config_directory() / name).open() as stream:
            return json.load(stream)
    except FileNotFoundError:
        return default


def local_secret():
    path = config_directory() / 'local-secret'
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # A concurrent process may still be publishing its first secret.
        for _ in range(100):
            secret = path.read_text()
            if len(secret) == 64:
                return secret
            time.sleep(0.01)
        raise ValueError('Incomplete local pairing file')
    secret = secrets.token_hex(32)
    with os.fdopen(fd, 'w') as stream:
        stream.write(secret)
    return secret


def signature(secret, timestamp, nonce, body):
    return hmac.new(secret.encode('ascii'), timestamp.encode('ascii') + b'\n' +
                    nonce.encode('ascii') + b'\n' + body, hashlib.sha256).hexdigest()


class AuthTransport(Transport):
    reply_timeout = None

    def __init__(self, secret):
        super().__init__()
        self.secret = secret

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = 10
        connection.request('GET', '/RPC2')
        response = connection.getresponse()
        self.epoch = response.read().decode('ascii')
        if response.status != 200 or len(self.epoch) != 32:
            raise ValueError('Peer does not support authenticated pairing')
        return connection

    def send_content(self, connection, body):
        timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
        connection.putheader('X-BN-Epoch', self.epoch)
        connection.putheader('X-BN-Time', timestamp)
        connection.putheader('X-BN-Nonce', nonce)
        connection.putheader('X-BN-Signature', signature(self.secret, timestamp, self.epoch + nonce, body))
        super().send_content(connection, body)
        # Model operations may legitimately run for hours. Bound the handshake,
        # but preserve the existing unlimited operation wait.
        if connection.sock is not None:
            connection.sock.settimeout(self.reply_timeout)


def proxy(address, secret):
    return ServerProxy(address, transport=AuthTransport(secret), allow_none=True)
