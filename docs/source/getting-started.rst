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

3. To export changes to NEURON after editing cell morphology/position in Blender:
 - Press 'Update Groups with View Changes' under 'Import / Export'
 - Then Press 'Export Cell Groups to NEURON' under 'Import / Export'

**********************
Adding Cells to Groups
**********************

1. Expand 'Cell Groups' and 'Cells in Group'
2. Add groups with the '+' on the right of the group names
3. Check off cells under 'Cells in Group' to add them to the currently selected group
 - A cell can only be in one group at a time

***************
Coloring Groups
***************

1. Select the Cell Group you would like to change display settings for
2. Expand 'Cell Group Options'
3. Next to 'Init. Color', click the colored block and select a color on the color wheel
 - Now, the next time the cell group is imported, the cells will be in that color

******************************
Visualizing Cell Model Voltage
******************************
...
****************************
Adding Synapses by Proximity
****************************

1. Load a model with at least 2 cells
2. Add cells that will form synapses to different groups
3. Expand 'Form Synapses'
 - This section will appear when you have at least two cell groups
4. Select groups for the 'Source' (presynaptic) and 'Destination' (postsynaptic) cells.
 - Must be different groups

******************************
Confining Cells between Layers
******************************

1. Import at least two cells
2. Import or create mesh object(s) to confine the cells between
3. Expand 'Confine Between Layers'
 - Section will appear once at least two cells are imported
...
