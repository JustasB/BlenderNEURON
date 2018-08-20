Introduction
=========================================

***************
Overview
***************

.. image:: files_static/logo.png

BlenderNEURON is a software tool that takes a NEURON simulator model and exports its 3D structure and membrane activity to Blender. It is easy to install and requires no model translation or modification.

Once in Blender, users can inspect/debug cell morphology and network connectivity, re-play/step through/scrub compartment membrane voltage, add render the model as beutiful images or videos/animated GIFs.

The tool is useful for debugging biophysically realistic neural models, easily creating visually impressive figures, and as a virtual laboratory for teaching neuroscience concepts.

The export can be peformed via NEURON GUI or automated via Python commands.

***************
Architecture
***************

.. image:: files_static/architecture.jpg

The tool consists of two parts: 

1) The Python/HOC library, which acts as a client
2) The Blender addon, which acts as the server

Users interact with the client library, which sends commands to the Blender addon, which then creates the meshes, materials, and animations in Blender. The user can then interact and modify the model in Blender.

***************
Getting Started
***************

Follow these steps to display a NEURON model and its voltage potential propagation in Blender:

 1. Make sure you have the required software: working installations of `NEURON <https://neuron.yale.edu>`_ and `Blender <https://www.blender.org/download/>`_
 2. Install the `BlenderNEURON HOC GUI <installation.html#hoc-install>`_ or `Python library <installation.html#python-install>`_
 3. Install the `Blender Addon <installation.html#blender-addon-installation>`_
 4. Load your model in NEURON
 5. Load the `BlenderNEURON GUI <gui.html>`_ or `Python module <python.html>`_, and use them to export the model to Blender
