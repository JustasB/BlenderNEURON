import zlib

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

        self.on_client_connected = on_client_connected
        self.on_server_setup = on_server_setup

        # Try connecting to the other node (if it's running)
        self.try_setup_client()

        # 'Control' nodes are 1-directional (a node with a connected client, but no server of its own)
        if 'Control' in self.server_end:
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
        if self.coverage:
            self.client.end_code_coverage()

        self.stop_server()

    def load_config(self):
        package_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(package_dir, 'config.json')
        with open(config_file, "r") as f:
            self.config = json.load(f)[0]

    def init_task_queue(self):
        self.queue = queue.Queue()
        self.task_lock = threading.Lock()
        self.tasks = {}
        self.task_next_id = 0

    def setup_server(self):

        class ErrorHandler(SimpleXMLRPCRequestHandler):
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

        self.init_task_queue()

        port = self.config["default_port"][self.server_end]

        self.server_ip = self.config["default_ip"][self.server_end]
        self.server_port = self.find_free_port() if port == "" else port
        self.server_address = 'http://' + self.server_ip + ':' + self.server_port

        self.server = CommNodeServer((self.server_ip, int(self.server_port)))
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
        self.service_thread = threading.Thread(target=self.service_queue_loop)
        self.service_thread.daemon = True
        self.service_thread_continue = True # When false, queue servicing thread will stop
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
                own_server_client = xmlrpclib.ServerProxy(self.server_address, allow_none=True)
                own_server_client.stop()
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

            if config_ip != "127.0.0.1" and config_port != "":
                client_address = 'http://' + config_ip + ':' + config_port
            else:
                # Try reading the client address file
                client_address = self.read_client_address_file()

            # Create XML-RCP client and attempt to connect to it
            self.client = xmlrpclib.ServerProxy(client_address, allow_none=True)
            assert self.client.ping() == 1

            # If connection succeeded, save the address
            self.client_address = client_address

        except (IOError, ValueError, AssertionError):
            if warn:
                self.print_safe("Could not connect to " + self.client_end + " server. Ensure "+
                    ("Blender+BlenderNEURON addon" if self.server_end == "NEURON" else "NEURON+BlenderNEURON package")+
                    " is running.")

            self.client = None
            self.client_address = None

        if self.client is not None and self.on_client_connected is not None:
            self.on_client_connected(self)

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
            client_address = f.read()

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
            with open(file_name, "w") as f:
                f.write(self.server_address)

    def get_end_address_file(self, end):
        tmp_dir = os.path.abspath(tempfile.gettempdir())
        file_name = os.path.join(tmp_dir, "BlenderNEURON-" + end + ".address")
        return file_name

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
        compressed = str(obj)

        try:
            compressed = xmlrpclib.Binary(zlib.compress(compressed, 2))
        except:
            compressed = xmlrpclib.Binary(zlib.compress(compressed.encode('utf8'), 2))

        return compressed

    def decompress(self, compressed):
        uncompressed = eval(zlib.decompress(compressed.data).decode('utf-8'))

        return uncompressed

