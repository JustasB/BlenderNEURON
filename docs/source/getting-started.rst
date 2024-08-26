Getting Started 
=========================================

Below are text guides for BlenderNEURON

Video tutorials are available on the `Tutorials Page <https://blenderneuron.org/tutorials/>`_.

Have you installed BlenderNEURON? See `Installation <installation.html>`_ for help on installing BlenderNEURON in Blender and NEURON.

***************
Importing Cells
***************

1. Load your model in NEURON and start BlenderNEURON
 - sample of code to run in terminal:
  .. code-block:: python

     python
     from neuron import h, gui
     h.load_file('path/to/SampleCell.hoc')
     cell1 = h.SampleCell()
     cell2 = h.SampleCell()
     cell2.position(0, 200, 0)

2. In NEURON GUI, open Graph > Shape Plot, to ensure cell is loaded correctly
 .. figure:: files_static/shapeplot.png
     :alt: Shape Plot
     :width: 400
3. Start BlenderNEURON with:
 ::

     from blenderneuron import neuronstart

3. Start Blender with BlenderNEURON add-on
4. Navigate to the BlenderNEURON tab in the sidebar
 
 .. figure:: files_static/sidebar.png
     :alt: Sidebar
     :width: 820

5. Import cells with 'Import Cell Groups to Blender' under 'Import / Export'

************************
Editing and Saving Cells
************************

Under Construction...

**********************
Adding Cells to Groups
**********************
...
******************************
Visualizing Cell Model Voltage
******************************
...
***************
Adding Synapses
***************
...
