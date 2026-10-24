import io
import hmac
import secrets
from blenderneuron import connection

import ast
import zlib

from blenderneuron.utils import deserialize, serialize

try:
    import Queue as queue
except:
    import queue

import threading, time, sys
import os, json, traceback, socket, tempfile, atexit
from contextlib import closing

try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib

try:
    from xmlrpc.server import SimpleXMLRPCServer
    from xmlrpc.server import SimpleXMLRPCRequestHandler
except:                                                         # pragma: no cover
    from SimpleXMLRPCServer import SimpleXMLRPCServer           # pragma: no cover
    from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler   # pragma: no cover

try:
    from socketserver import ThreadingMixIn
except:                                                         # pragma: no cover
    from SocketServer import ThreadingMixIn                     # pragma: no cover

from collections import OrderedDict

debug = False

class CommNode(object):
    server_types = {
        "NEURON": "Blender",
        "Blender": "NEURON",
        "Control-Blender": "Blender",
        "Control-NEURON": "NEURON",
        "Package": "Blender",
    }

    def __init__(self, server_end, on_client_connected=None, on_server_setup=None, coverage=False):

        self.coverage = coverage

        self.groups = OrderedDict()
        self.root_index = OrderedDict()

        self.load_config()

        if server_end in self.server_types.keys():
            self.server_end = server_end
            self.client_end = self.server_types[server_end]

        else:
            raise Exception("Unrecognized server_end: " + str(server_end) + ". Should be one of: "
                            + str(self.server_types.keys()))

        self.connection_end = self.client_end if "Control" in server_end else server_end
        self.connection_settings = connection.load(self.connection_end + "-connection.json", {"mode": "local"})
        self.secret = connection.local_secret() if self.connection_settings["mode"] == "local" else self.connection_settings["secret"]
        self.on_client_connected = on_client_connected
        self.on_server_setup = on_server_setup

        # Try connecting to the other node (if it's running)
        self.try_setup_client()

        # 'Control' nodes are 1-directional (a node with a connected client, but no server of its own)
        if 'Control' in self.server_end:
            # The integration-test control nodes can be created before the process
            # that hosts their client.  Keep trying until that process publishes
            # its address instead of permanently retaining a failed first attempt.
            self.client_retry_stop = threading.Event()
            self.client_connected = threading.Event()
            if self.client is None:
                self.client_retry_thread = threading.Thread(target=self.retry_setup_client)
                self.client_retry_thread.daemon = True
                self.client_retry_thread.start()
                # A control node is normally consumed immediately after it is
                # created.  Give a just-started peer time to publish its server
                # address before exposing an unavailable client to the caller.
                self.client_connected.wait(5)
            return

        # Create a server
        # Package type does not result in server
        if server_end != 'Package':
            self.setup_server()

        # If successfully connected, then instruct the other node to connect back
        # and complete the 2nd half of the connection
        if self.client is not None:

            self.client.try_setup_client()

            if self.client is not None and hasattr(self, 'server') and self.server is not None:
                self.print_safe("Two-way communication between %s and %s established"
                                %(self.server_end, self.client_end))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "client_retry_stop"):
            self.client_retry_stop.set()
        if hasattr(self, "client_retry_thread") and self.client_retry_thread.is_alive():
            self.client_retry_thread.join()

        if self.coverage:
            self.client.end_code_coverage()

        self.stop_server()

    def load_config(self):
        package_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(package_dir, 'config.json')
        with open(config_file, "r") as f:
            self.config = json.load(f)[0]
        for path, value in connection.load('endpoint-settings.json', {}).items():
            section, end = path.split('|')
            self.config[section][end] = value


    def init_task_queue(self):
        self.queue = queue.Queue()
        self.task_lock = threading.Lock()
        self.tasks = {}
        self.task_next_id = 0

    def setup_server(self, service_queue=True):

        node = self
        replay_lock = threading.Lock()
        seen = {}
        epoch = secrets.token_hex(16)

        class ErrorHandler(SimpleXMLRPCRequestHandler):
            def do_GET(self):
                # Public startup challenge invalidates captured requests after restart.
                body = epoch.encode('ascii')
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 0 or length > 256 * 1024 * 1024:
                        raise ValueError('Invalid request size')
                    body = self.rfile.read(length)
                    timestamp = self.headers.get('X-BN-Time', '')
                    nonce = self.headers.get('X-BN-Nonce', '')
                    digest = self.headers.get('X-BN-Signature', '')
                    if abs(time.time() - int(timestamp)) > 60 or len(nonce) != 32:
                        raise ValueError('Expired request')
                    if self.headers.get('X-BN-Epoch', '') != epoch:
                        raise ValueError('Server restarted')
                    expected = connection.signature(node.secret, timestamp, epoch + nonce, body)
                    if not hmac.compare_digest(expected, digest):
                        raise ValueError('Authentication failed')
                    with replay_lock:
                        now = time.time()
                        for key in list(seen):
                            if seen[key] < now - 120:
                                del seen[key]
                        if nonce in seen:
                            raise ValueError('Repeated request')
                        seen[nonce] = now
                except (ValueError, UnicodeError):
                    self.send_error(403, 'Pairing authentication failed')
                    return
                self.rfile = io.BytesIO(body)
                super().do_POST()

            def _dispatch(self, method, params):
                try:
                    return self.server.funcs[method](*params)
                except:
                    import traceback
                    traceback.print_exc()
                    raise

        class CommNodeServer(ThreadingMixIn, SimpleXMLRPCServer, object):
            """
            A helper class to create an XML-RCP server
            """

            def __init__(self, param):
                self.daemon_threads = True
                super(CommNodeServer, self).__init__(
                    param,
                    requestHandler=ErrorHandler,
                    allow_none=True,
                    logRequests=False
                )

        if service_queue or not hasattr(self, "queue"):
            self.init_task_queue()

        port = self.connection_settings.get("listen_port", "") if self.connection_settings["mode"] == "manual" else ""

        self.server_requested_port = str(port)
        self.server_ip = self.connection_settings.get("listen_host", "127.0.0.1") if self.connection_settings["mode"] == "manual" else "127.0.0.1"
        self.server_port = "0" if port == "" else str(port)
        self.server = CommNodeServer((self.server_ip, int(self.server_port)))
        self.server_port = str(self.server.server_address[1])
        self.server_address = 'http://' + self.server_ip + ':' + self.server_port
        self.server.register_introspection_functions()

        # Basic server functions
        self.server.register_function(self.sm_stop, 'stop')
        self.server.register_function(self.sm_ping, 'ping')
        self.server.register_function(self.try_setup_client, 'try_setup_client')

        # Synchronous execution
        self.server.register_function(self.sm_run_command, 'run_command')

        # Asynchronous task execution queueing
        self.server.register_function(self.sm_enqueue_command, 'enqueue_command')
        self.server.register_function(self.sm_get_task_status, 'get_task_status')
        self.server.register_function(self.sm_get_task_error,  'get_task_error')
        self.server.register_function(self.sm_get_task_result, 'get_task_result')

        # Code coverage result saving
        self.server.register_function(self.sm_end_code_coverage, 'end_code_coverage')

        # Start the server in a separate thread - it will place tasks onto queue
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        # Perform the servicing of queued tasks in a separate thread
        if service_queue:
            self.service_thread = threading.Thread(target=self.service_queue_loop)
            self.service_thread.daemon = True
            self.service_thread_continue = True
            self.service_thread.start()

        if self.on_server_setup is not None:
            self.on_server_setup()

        # Communicate the address of the server to the client
        self.save_server_address_file()

        self.print_safe("Started " + self.server_end + " server at: " + self.server_address)

    def stop_server(self):
        if hasattr(self, "service_thread") and self.service_thread is not None and self.service_thread.is_alive():
            self.service_thread_continue = False
            self.service_thread.join()
            self.service_thread = None
            self.init_task_queue()

        if hasattr(self, "server_thread") and self.server_thread is not None and self.server_thread.is_alive():
            try:
                self.sm_stop()
                self.server_thread.join()
                self.server_thread = None
            except:     # pragma: no cover
                pass    # pragma: no cover

        if hasattr(self, "server"):
            self.server = None
            self.server_ip = None
            self.server_port = None
            self.server_address = None

            self.save_server_address_file()

    def find_free_port(self):
        """
        :return: A random available port
        """
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('localhost', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return str(s.getsockname()[1])

    def try_setup_client(self, warn=True):
        try:
            config_ip = self.config["default_ip"][self.client_end]
            config_port = self.config["default_port"][self.client_end]

            if self.connection_settings["mode"] == "manual":
                client_address = self.connection_settings["peer_address"]
            else:
                # Try reading the client address file
                client_address = self.read_client_address_file()

            # Create XML-RCP client and attempt to connect to it
            self.client = connection.proxy(client_address, self.secret)
            assert self.client.ping() == 1

            # If connection succeeded, save the address
            self.client_address = client_address

        except (IOError, ValueError, AssertionError, KeyError, xmlrpclib.Error) as error:
            self.last_connection_error = ('Pairing credentials do not match. Paste connection information again.'
                if isinstance(error, xmlrpclib.ProtocolError) and error.errcode == 403
                else 'NEURON did not respond at ' + str(locals().get('client_address', 'the saved address')))
            if warn:
                self.print_safe("Could not connect to " + self.client_end + " server. Ensure "+
                    ("Blender+BlenderNEURON addon" if self.server_end == "NEURON" else "NEURON+BlenderNEURON package")+
                    " is running.")

            self.client = None
            self.client_address = None

        if self.client is not None:
            self.last_connection_error = ""

        if self.client is not None and self.on_client_connected is not None:
            self.on_client_connected(self)

        if self.client is not None and hasattr(self, "client_connected"):
            self.client_connected.set()

    def retry_setup_client(self):
        while not self.client_retry_stop.is_set() and self.client is None:
            self.try_setup_client(warn=False)
            self.client_retry_stop.wait(0.1)

    def read_client_address_file(self):
        """
        Read from a file in tmp folder that contains the address of the other node's XML-RCP server
        :return: The address of the other end's XML-RCP server
        """
        tmp_dir = os.path.abspath(tempfile.gettempdir())
        file_name = self.get_end_address_file(self.client_end)

        if not os.path.exists(file_name):
            raise IOError("Client address file not found:" + file_name)

        with open(file_name, "r") as f:
            client_address = json.load(f)

        if "http" not in client_address:
            raise ValueError("Address in the client address file does not appear to be valid:" + client_address) # pragma: no cover

        return client_address

    def save_server_address_file(self):
        """
        Create a file in tmp folder that contains the address of this node's XML-RCP server
        :return: Nothing
        """
        file_name = self.get_end_address_file(self.server_end)

        # If the server address is blank (i.e. on cleanup), remove the file if it exists
        if self.server_address is None:
            if os.path.exists(file_name):
                try:
                    os.remove(file_name)
                except OSError: # pragma: no cover
                    pass        # pragma: no cover

        else:
            connection.save(os.path.basename(file_name), self.server_address)

    def get_end_address_file(self, end):
        file_name = str(connection.config_directory() / ("BlenderNEURON-" + end + ".address"))
        return file_name

    def pairing_information(self):
        """Return a credential-bearing string. Share only with a trusted peer."""
        return json.dumps({"version": 1, "secret": self.secret,
                           "address": self.server_address})

    def configure_connection(self, mode="local", peer_address=None,
                             listen_host=None, listen_port=None, pairing=None):
        """Persist settings; changing listening settings requires restarting the node."""
        remembered = connection.load(self.connection_end + "-manual.json", {}) if mode == "manual" else {}
        settings = {"mode": mode,
                    "listen_host": listen_host if listen_host is not None else remembered.get("listen_host", "127.0.0.1"),
                    "listen_port": str(listen_port) if listen_port is not None else remembered.get("listen_port", "")}
        if settings["listen_port"] and (not settings["listen_port"].isdigit() or not 1 <= int(settings["listen_port"]) <= 65535):
            raise ValueError("Listening port must be between 1 and 65535")
        if mode not in ("local", "manual"):
            raise ValueError("Unknown connection mode")
        if mode == "manual":
            info = json.loads(pairing) if pairing else {}
            if not isinstance(info, dict):
                raise ValueError("Pairing information must be a JSON object")
            secret = info.get("secret", remembered.get("secret", self.secret))
            if not isinstance(secret, str) or len(secret) != 64 or any(c not in "0123456789abcdef" for c in secret):
                raise ValueError("Invalid pairing secret")
            if info and info.get("version") != 1:
                raise ValueError("Unsupported pairing version")
            address = peer_address or info.get("address") or self.connection_settings.get("peer_address") or remembered.get("peer_address")
            from urllib.parse import urlparse
            parsed = urlparse(address or "")
            if address and (parsed.scheme != "http" or not parsed.hostname or not parsed.port or parsed.username):
                raise ValueError("Provide an HTTP peer address with a port")
            settings.update(secret=secret, peer_address=address or "")
            connection.save(self.connection_end + "-manual.json", settings)
        else:
            secret = connection.local_secret()
        connection.save(self.connection_end + "-connection.json", settings)
        self.connection_settings, self.secret = settings, secret
        self.client = None
        self.client_address = None

    def forget_connection(self):
        """Revoke credentials without changing simulation or scene data."""
        self.secret = secrets.token_hex(32)
        if self.connection_settings["mode"] == "local":
            path = connection.config_directory() / 'local-secret'
            fd, temporary = tempfile.mkstemp(dir=str(path.parent))
            with os.fdopen(fd, 'w') as stream:
                stream.write(self.secret)
            os.replace(temporary, str(path))
        else:
            self.connection_settings["secret"] = self.secret
            self.connection_settings.pop("peer_address", None)
        try:
            (connection.config_directory() / (self.connection_end + "-manual.json")).unlink()
        except FileNotFoundError:
            pass
        connection.save(self.connection_end + "-connection.json", self.connection_settings)
        self.client = None
        self.client_address = None

    def test_connection(self):
        self.try_setup_client()
        if self.client is not None:
            self.client.try_setup_client()
        return self.client is not None

    def print_safe(self, value):
        if debug == False:
            return

        try:                             # pragma: no cover
            print(value)                 # pragma: no cover
        except:                          # pragma: no cover
            tb = traceback.format_exc()  # pragma: no cover
            print(tb)                    # pragma: no cover

    def sm_stop(self):
        """
        A method that, when called by a client of the node server, will stop the server
        :return:
        """
        if hasattr(self, "server") and self.server is not None:
            self.server.shutdown()
            self.server.server_close()

        return 0

    def sm_ping(self):
        self.print_safe(self.server_end + " server at " + self.server_address + " ALIVE")
        return 1

    def sm_run_command(self, command_string):
        exec_lambda = self._get_command_lambda(command_string)
        return self._run_lambda(exec_lambda)

    def sm_enqueue_command(self, command_string):
        exec_lambda = self._get_command_lambda(command_string)
        return self._enqueue_lambda(exec_lambda)

    def sm_end_code_coverage(self):
        try:
            print('Getting Coverage info', self.server_end)
            from blenderneuron import COV
        except:                                         # pragma: no cover
            print('Failed to get COV', self.server_end) # pragma: no cover

            # Dont try to save coverage info if not in coverage
            return                                      # pragma: no cover

        COV.stop()                                      # pragma: no cover
        COV.save()                                      # pragma: no cover
        time.sleep(1)                                   # pragma: no cover

        print('SAVED Coverage info', self.server_end)   # pragma: no cover

    def _get_command_lambda(self, command_string):
        """
        Execute arbitrary python command within Blender's python process
        :param command_string: A python expression. Set variable 'return_value' to receive a response.
           e.g. command_string = "print('test')" -> will print 'test' in Blender console
           e.g. command_string = "return_value = 1+3" -> will compute in Blender and return 4
           e.g. command_string = "import bpy; return_value = [i for i in bpy.data.objects]" -> will list all Blender objects
        :return:
        """
        def exec_lambda():

            end_imports = self.config["imports"][self.server_end]
            try:
                exec(end_imports + "; " + command_string, globals())
            except SystemExit:
                raise
            except:
                print('Error while attempting to run the following command(s) within ' + self.server_end + ':')
                print('------------ Command ------------')
                print(command_string.replace(";","\n"))
                print('---------------------------------')
                raise

            return globals().pop('return_value', None)

        return exec_lambda

    def _run_lambda(self, task_lambda):
        id = self._enqueue_lambda(task_lambda)

        while self.sm_get_task_status(id) == 'QUEUED':
            time.sleep(0.1)

        status = self.sm_get_task_status(id)

        if status == "SUCCESS":
            return self.sm_get_task_result(id)

        else:
            raise Exception(self.sm_get_task_error(id))

    def _enqueue_lambda(self, task_lambda):
        task_id = self._get_new_task_id()

        task = {
            "id": task_id,
            "status": "QUEUED",
            "lambda": task_lambda,
            "result": None,
            "error": None
        }

        self.tasks[task_id] = task
        self.queue.put(task)

        return task_id

    def _get_new_task_id(self):
        with self.task_lock:
            task_id = self.task_next_id
            self.task_next_id += 1

        return task_id

    def sm_get_task_status(self, task_id):
        if task_id in self.tasks:
            return self.tasks[task_id]["status"]

        return "DOES_NOT_EXIST"

    def sm_get_task_error(self, task_id):
        return self.tasks[task_id]["error"]

    def sm_get_task_result(self, task_id):
        return self.tasks[task_id]["result"]

    def work_on_queue_tasks(self):
        q = self.queue
        self.queue_error = False

        while not q.empty():
            self.print_safe("Tasks in queue. Getting next task...")
            task = q.get()

            try:
                if not self.queue_error:
                    self.print_safe("Running task...")
                    result = task["lambda"]()
                    task["result"] = result
                    task["status"] = "SUCCESS"
                else:
                    self.print_safe("Previous task had an error. SKIPPING.")
                    task["status"] = "ERROR"

            except:
                self.queue_error = True
                tb = traceback.format_exc()

                if "SystemExit" not in tb:
                    task["status"] = "ERROR"
                    task["error"] = tb
                    self.print_safe(tb)

                else:
                    task["status"] = "SUCCESS"
                    task["result"] = None

                    # We want to allow the RCP server to send back a response before killing the process
                    def self_destruct():
                        self.print_safe("Exiting NEURON in 1s ... ")
                        time.sleep(0.5)
                        quit()

                    thread = threading.Thread(target=self_destruct)
                    thread.start()

            q.task_done()
            self.print_safe("DONE")

    def service_queue_loop(self):
        while self.service_thread_continue:
            if not self.queue.empty():
                self.work_on_queue_tasks()
            else:
                time.sleep(0.1)

    def compress(self, obj):
        payload = serialize(obj).encode('utf-8')
        return xmlrpclib.Binary(zlib.compress(payload, 2))

    def decompress(self, compressed):
        return deserialize(zlib.decompress(compressed.data).decode('utf-8'))

