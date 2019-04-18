Building BlenderNEURON
=========================================

The Blender addon (the server) uses Cython to improve performance and has to be built for every platform on which it is used. By default, 
the addon includes cythonized binaries for Win, Mac, and Ubuntu Linux versions of Python that come bundled with Blender. On the other hand, 
the HOC/Python library for NEURON (the client) is written in pure Python and does not need to be cythonized.

If you use a different minor version of Python than the one that comes bundled with Blender (e.g. 3.6 vs bundled 3.5) you will need to manually 
cythonize the addon using your version of Python. Without this step, you will receive the following error in Blender: ``ModuleNotFound: No module named 'blender_neuron.blender_neuron.server'``

.. _addon-build:

***************************
Blender Addon Building
***************************

Perform the following steps using the Python version that you are using with Blender.

 1. Clone the BlenderNEURON repository: ``git clone https://github.com/JustasB/BlenderNEURON``
 2. Change into addon folder: ``cd BlenderNEURON/ForBlender/blender_neuron``
 3. Ensure you have Cython package installed: ``pip install cython``
 4. Cythonize the addon code: ``python setup.py build_ext --inplace``
 5. Change to parent ForBlender folder: ``cd ..``
 6. Create a .zip file (recursively, including directory structure) using only ``__init__.py``, ``.so``, and ``.pyd`` files. On Linux, use command ``./buildzip.sh``, which will create the ``blender_neuron_v.zip`` file.
 7. The .zip file now contains the compiled version of the Blender addon. Follow `the installation steps to install the addon <installation.html#blender-addon-installation>`_.

