"""Small compatibility boundary for the NEURON-side Python 2 interpreter."""
import binascii
import math
import os
import sys

PY2 = sys.version_info[0] == 2
if PY2:
    from future import standard_library
    standard_library.install_aliases()
    from pathlib2 import Path
    from collections import Sequence
    from backports.weakref import finalize
    string_types = (basestring,)
    integer_types = (int, long)
else:
    from pathlib import Path
    from collections.abc import Sequence
    from weakref import finalize
    string_types = (str,)
    integer_types = (int,)


def token_hex(size):
    return binascii.hexlify(os.urandom(size)).decode('ascii')


def isfinite(value):
    return not math.isinf(value) and not math.isnan(value)


def replace(source, destination):
    if hasattr(os, 'replace'):
        return os.replace(source, destination)
    if os.name == 'nt':
        import ctypes
        if not ctypes.windll.kernel32.MoveFileExW(unicode(source), unicode(destination), 1):
            raise ctypes.WinError()
    else:
        os.rename(source, destination)
