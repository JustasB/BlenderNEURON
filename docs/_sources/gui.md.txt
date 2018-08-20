Visualizing Using the GUI 
=========================================

For all of these tasks, make sure you have done the following:

1. Load your model in NEURON
2. Load BlenderNEURON in NEURON (by either opening the BlenderNEURON.hoc file or running ``from blenderneuron.quick import bn``)
3. Load Blender with the BlenderNEURON add-on (NEURON tab should be visible in Blender left panel)
4. Test the connectivity between NEURON and Blender (Should say "Ready")

See `Installation <installation.html>`_ for how to perform steps 2-4.

***************************
Visualizing Morphology
***************************

Follow these steps to visualize the cell morphology of a NEURON model:

1. Once your model is loaded, click "Send to Blender" button
2. A moment later, your model should appear in Blender
3. Navigate around the Blender scene to inspect the model. If you're not familiar with Blender, `these tutorials <https://cloud.blender.org/p/blender-inside-out/560414b7044a2a00c4a6da98>`_ will give an overview of basic scene navigation.

By default, BlenderNEURON will export the morphology of all cells (sections) in the model. It will use NEURON's x/y/z3d() and diam3d() values to build the 3D meshes in Blender.

In BlenderNEURON, 1 cm corresponds to 1 micron in NEURON.

If you add or make changes to your model's sections/cells, click the "Re-Gather Sections" before clicking "Send to Blender" to ensure that they are included in the export. 

***************************
Visualizing Activity
***************************

Follow these steps to visualize the morphology and simulated activity of a NEURON model:

1. Once your model is loaded, click "Prepare For Simulation" button. This will add a handler to gather section voltage values during the simulation.
2. Run your simulation
3. Once the simulation is finished, click the "Send to Blender" button
4. A moment later, your model should appear in Blender
5. Use the buttons under the bottom timeline in Blender to re-play the simulation. If your cells emit action potentials (Vm > -20mV), you should be able to see them as glowing compartments. By default, 1 frame in Blender corresponds to 0.5ms in NEURON.
6. You can scrub the timeline to re-play any part of the simulation and use the left/right arrow keys to step through the frames.

.. image:: files_static/timeline.JPG



