Getting Started 
=========================================
Under Construction...
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
 - Press 'N' to toggle sidebar 
 .. figure:: files_static/sidebar.png
     :alt: Sidebar
     :width: 800

5. Import cells with 'Import Cell Groups to Blender' under 'Import / Export'

************************
Editing and Saving Cells
************************
Under Construction...

1. With cells imported, left click on a cell in the 3D view to select (like other Blender objects)
 - For help with navigating Blender: `Blender Fundamentals Videos <https://www.youtube.com/watch?v=MF1qEhBSfq4&list=PLa1F2ddGya_-UvuAqHAksYnB0qL9yWDO6&pp=iAQB>`_ or `Blender Manual <https://docs.blender.org/manual/en/3.5/editors/3dview/navigate/navigation.html>`_
2. To select and rotate individual sections:
 - under 'Cell Group Options', select 'Interact with Each:' 'Section'
 - Import cells again
3. To export changes to NEURON after editing cell morphology/position in Blender:
 - Press 'Update Groups with View Changes' under 'Import / Export'
 - Then Press 'Export Cell Groups to NEURON' under 'Import / Export'

**********************
Adding Cells to Groups
**********************

1. Expand 'Cell Groups' and 'Cells in Group'
2. Add groups with the '+' to the right of the group names
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
1. Have your model with activity loaded in NEURON
2. Select Cell Group to animate
3. Expand 'Cell Group Options'
4. Check off 'Record Activity'
 - Activity will be recorded next time the cells are imported
5. Choose Recording Settings
 - Set start and stop recordings to capture activity in your simulation
 - Select variable to record (v/voltage by default)
 - Select 'Sampling Period'; how many milliseconds between samples collected of the variable
 - Select 'Frames per Milliseconds', the number of frames of animation will be taken up by each millisecond of NEURON activity
 - Set colors to correspond with the variable low and high values
6. Import cells with 'Import Cell Groups to Blender' under 'Import / Export'
7. Scrub the timeline on the bottom to see animation

****************************
Adding Synapses by Proximity
****************************

1. Have at least 2 cells instantiated in NEURON
2. Add cells that will form synapses to different groups
3. Expand 'Form Synapses'
 - This section will appear when you have at least two groups
4. Select groups for the 'Source' (presynaptic) and 'Destination' (postsynaptic) cells
 - Must be different groups
5. Select synaptic mechanism next to 'Synapse', if you have additional mechanisms loaded in NEURON
 - By default, NEURON lets you use 'ExpSyn' mechanism
 - For help on compiling mod files to add mechanisms: `Mod Files <https://www.neuron.yale.edu/phpBB/viewtopic.php?t=3263&sid=2c672c89ff0c1c17a90f35d3c44696d0>`_
6. Select sections that will form synapses next to 'Sections:'
 - Surround characters with asterisks (\*example\*) to include all sections with those characters in the name
7. Press 'Find Synapse Locations' to display locations
8. Create the synapses in NEURON by pressing 'Create Synapses'
9. Or save synapses to a JSON file by pressing 'Save Synapse Set to JSON File'

******************************
Confining Cells between Layers
******************************

1. Import at least one cell
2. Import or create mesh object(s) to confine the cells between
3. Expand 'Confine Between Layers'
 - Section will appear once at least one cells is imported
4. Select objects for the confinement 'Start Layer' and 'End Layer'
5. Next to 'Name Contains:', select sections that will be confined
 - Surround characters with asterisks to confine all sections with those characters
6. To confine the sections between the layers, press 'Confine'
7. Save changes in Blender by pressing 'Update Groups with Confinement Results'
8. Save confinement results to NEURON by pressing 'Export Cell Groups to NEURON' under 'Import / Export'
