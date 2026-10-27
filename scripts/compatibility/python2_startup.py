"""Test-only standard-library backports for the Python 2 full-suite lane.

Loaded as sitecustomize by every Python 2 test/worker process. Production
compatibility lives in blenderneuron.compat; this supplies modern test APIs.
"""
from __future__ import print_function
import sys
if sys.version_info[0] == 2:
    import __builtin__
    import errno
    import importlib
    import imp
    import inspect
    import gzip
    import io
    import math
    import os
    import re
    import shlex
    import tempfile
    import time
    import types
    from future import standard_library
    standard_library.install_aliases()
    import pathlib2
    original_print = __builtin__.print

    def modern_print(*args, **kwargs):
        flush = kwargs.pop('flush', False)
        original_print(*args, **kwargs)
        if flush:
            kwargs.get('file', sys.stdout).flush()

    __builtin__.print = modern_print
    import mock
    import unittest2
    import subprocess32
    from xmlrpc.client import ServerProxy
    ServerProxy.__enter__ = lambda self: self
    ServerProxy.__exit__ = lambda self, *error: self._ServerProxy__close()
    from backports.tempfile import TemporaryDirectory
    from monotonic import monotonic
    from funcsigs import signature

    original_write_text = pathlib2.Path.write_text

    def write_text(self, data, encoding=None, errors=None):
        if isinstance(data, str):
            data = data.decode(encoding or 'utf-8')
        return original_write_text(self, data, encoding=encoding, errors=errors)

    pathlib2.Path.write_text = write_text
    sys.modules['pathlib'] = pathlib2
    sys.modules['unittest'] = unittest2
    sys.modules['unittest.mock'] = mock
    unittest2.mock = mock
    unittest2.TestCase.assertCountEqual = unittest2.TestCase.assertItemsEqual
    original_test_init = unittest2.TestCase.__init__

    def test_init(self, methodName='runTest'):
        if type(self) is unittest2.TestCase and methodName == 'runTest':
            self.runTest = lambda: None
        original_test_init(self, methodName)

    unittest2.TestCase.__init__ = test_init
    tempfile.TemporaryDirectory = TemporaryDirectory

    def gzip_compress(data):
        stream = io.BytesIO()
        with gzip.GzipFile(fileobj=stream, mode='wb') as archive:
            archive.write(data)
        return stream.getvalue()

    gzip.compress = gzip_compress
    time.monotonic = monotonic
    inspect.signature = signature
    math.isfinite = lambda value: not math.isnan(value) and not math.isinf(value)
    shlex.quote = __import__('pipes').quote
    if not hasattr(os, 'replace'):
        os.replace = os.rename
    __builtin__.FileNotFoundError = IOError
    __builtin__.FileExistsError = OSError
    __builtin__.ProcessLookupError = OSError
    __builtin__.ChildProcessError = OSError
    __builtin__.TimeoutError = type("TimeoutError", (OSError,), {})

    class SimpleNamespace(object):
        def __init__(self, **values):
            self.__dict__.update(values)

        def __repr__(self):
            return 'namespace(%s)' % ', '.join('%s=%r' % item for item in sorted(self.__dict__.items()))

        def __eq__(self, other):
            return isinstance(other, SimpleNamespace) and self.__dict__ == other.__dict__

    types.SimpleNamespace = SimpleNamespace

    class Loader(object):
        def __init__(self, name, path):
            self.name, self.path = name, str(path)

        def exec_module(self, module):
            module.__file__ = self.path
            with open(self.path, 'rb') as stream:
                exec(compile(stream.read(), self.path, 'exec'), module.__dict__)

    def spec_from_file_location(name, path):
        return SimpleNamespace(name=name, loader=Loader(name, path))

    def module_from_spec(spec):
        return types.ModuleType(spec.name)

    util = types.ModuleType('importlib.util')
    util.spec_from_file_location = spec_from_file_location
    util.module_from_spec = module_from_spec
    importlib.util = util
    sys.modules['importlib.util'] = util
    re.fullmatch = lambda pattern, value, flags=0: re.match('(?:' + pattern + ')\\Z', value, flags)

    native_run = subprocess32.run
    native_popen = subprocess32.Popen

    class Popen(native_popen):
        def __init__(self, args, *positional, **kwargs):
            if isinstance(args, (list, tuple)):
                args = [str(arg) if hasattr(arg, '__fspath__') else arg for arg in args]
                # Generated child scripts use the same print semantics as tests.
                if '-c' in args and args[0] == sys.executable:
                    index = args.index('-c') + 1
                    args[index] = 'from __future__ import print_function\n' + args[index]
            if hasattr(kwargs.get('cwd'), '__fspath__'):
                kwargs['cwd'] = str(kwargs['cwd'])
            if 'env' in kwargs and kwargs['env'] is not None:
                environment = dict(kwargs['env'])
                startup = os.path.dirname(__file__)
                paths = environment.get('PYTHONPATH', '').split(os.pathsep)
                if startup not in paths:
                    environment['PYTHONPATH'] = os.pathsep.join([startup] + paths)
                kwargs['env'] = environment
            if 'text' in kwargs:
                kwargs['universal_newlines'] = kwargs.pop('text')
            kwargs.pop('encoding', None)
            native_popen.__init__(self, args, *positional, **kwargs)

    subprocess32.Popen = Popen

    def run(*args, **kwargs):
        if kwargs.pop('capture_output', False):
            kwargs['stdout'] = kwargs['stderr'] = subprocess32.PIPE
        if 'text' in kwargs:
            kwargs['universal_newlines'] = kwargs.pop('text')
        return native_run(*args, **kwargs)

    subprocess32.run = run
    sys.modules['subprocess'] = subprocess32
