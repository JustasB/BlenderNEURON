# Build with 'python setup.py build_ext --inplace'

import sys
if sys.version_info[0] < 3:
    print("WARNING: Must be using Python 3+ to compile for Blender. Ignore this if you're using non-Blender-bundled version of Python.")

from distutils.core import setup, Extension
from Cython.Build import cythonize

from Cython.Compiler.Options import get_directive_defaults
directive_defaults = get_directive_defaults()

#directive_defaults['linetrace'] = True
#directive_defaults['binding'] = True

#extensions = [Extension(name='neuroserver', sources=[])]

setup(
    ext_modules = cythonize(["server.pyx", "colors.pyx"], gdb_debug=False)
)
