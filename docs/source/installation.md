Installation
=========================================

BlenderNEURON installation is a simple two part process which enables communication between NEURON and Blender. 

For Part 1, you can choose either the HOC (NEURON default) or Python versions. Both have identical functionality (HOC version has a wrapper that allows loading the library by opening a .hoc file).

.. _hoc-install:

***************************
HOC GUI Installation
***************************

Install this part if you generally use NEURON HOC interface (NEURON default).

**Part 1: HOC NEURON Client**

 1. If you haven't already, install NEURON
 2. `Download the latest HOC version <https://github.com/JustasB/BlenderNEURON/releases>`_ (e.g. blender_neuron_HOC_xxx.zip)
 3. Extract the zip file and open the BlenderNEURON.hoc file using NEURON. You should see the BlenderNEURON interface.

.. image:: files_static/NEURON.JPG

.. _python-install:

**************************************
Python Library Installation (Optional)
**************************************

Install this part if you generally use NEURON+Python interface. The library will work if you use the ``-python`` flag to launch NEURON or you have compiled NEURON Python module and can `from neuron import h` from Python console.

**Part 1: Python NEURON Client**

 1. If you haven't already, install NEURON
 2. Using the same Python environment as NEURON, use the ``pip install blenderneuron`` command to install the `BlenderNEURON client library <https://pypi.org/project/blenderneuron/>`_
 3. Start NEURON+Python, and type ``from blenderneuron.quick import bn`` to load the BlenderNEURON interface

.. image:: files_static/NEURON.JPG

.. _addon-install:

***************************
Blender Addon Installation
***************************

.. note:: The steps below assume that the Blender-bundled instance of Python is being used in Blender. If you've modified Blender to use a different version of Python, you will need to `manually Cythonize the addon <building.html>`_.

**Part 2: Blender Addon Server**
 1. If you haven't already, install and open `Blender <https://www.blender.org/download/>`_
 2. Download the `BlenderNEURON addon <https://github.com/JustasB/BlenderNEURON/releases>`_  (e.g.
    blender_neuron_addon_xxx.zip). Note: On MacOS, Safari browser may `automatically extract the zip file
    <https://www.addictivetips.com/mac-os/stop-automatically-unzipping-files-in-safari/>`_, make sure you use the unextracted
    .zip file in the next step.
 3. In Blender, click File > User Preferences > Add-ons (tab) > Install Add-on From File > Point to the addon .zip file
 4. Tick the checkbox next to 'Import-Export: NEURON Blender Interface' to load the addon. Then click "Save User Settings".
 5. If you see a NEURON tab on the left side of the screen, the addon has been loaded successfully.

.. image:: files_static/addon-loaded.jpg


********************************
Test NEURON-Blender Connectivity
********************************

Once you have the NEURON HOC/Python module and Blender Add-on activated, check whether NEURON can communicate with Blender with the following steps:

 1. From NEURON, at the bottom of the BlenderNEURON window, click "Test Connection" button
 2. If you have Blender running, with the add-on installed and loaded (checkbox checked), the connection status should say "Ready". It means that NEURON can succesfully communicate with Blender.


.. image:: files_static/connection-ready.jpg
