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

 - You can download `SampleCell.hoc <https://github.com/JustasB/BlenderNEURON/blob/blender-3-plus-conversion/tutorials/SampleCell.hoc>`_ to test BlenderNEURON with

2. In the NEURON GUI, open Graph > Shape Plot, to ensure the model is loaded correctly
3. Start BlenderNEURON in NEURON/Python by running:

  .. code-block:: python

    from blenderneuron import neuronstart

4. Start Blender with the BlenderNEURON add-on
5. Navigate to the BlenderNEURON tab in the sidebar

 - press 'N' to toggle sidebar

 .. figure:: files_static/sidebar.png
     :alt: Sidebar
     :width: 600

6. Import cells with 'Import Cell Groups to Blender' under 'Import / Export'

 .. figure:: files_static/importcells.png
     :alt: Import Cells
     :width: 200

************************
Editing and Saving Cells
************************

1. With the cells imported, left click a cell in the 3d view to select it (like other Blender objects)

 - For help with navigating Blender: `Blender Fundamentals Videos <https://www.youtube.com/watch?v=MF1qEhBSfq4&list=PLa1F2ddGya_-UvuAqHAksYnB0qL9yWDO6&pp=iAQB>`_ or `Blender Manual <https://docs.blender.org/manual/en/3.5/editors/3dview/navigate/navigation.html>`_
 - 'G' to move
 - 'R' to rotate
 - 'S' to scale

2. To select and rotate individual sections:

 - Under 'Cell Group Options', select 'Interact with Each:' 'Section'
 - Import cells again

3. To export changes to NEURON after editing cell morphology/position in Blender:

 - Click 'Update Groups with View Changes' under 'Import / Export'
 - Then click 'Export Cell Groups to NEURON' under 'Import / Export'

**********************
Adding Cells to Groups
**********************

1. Expand 'Cell Groups' and 'Cells in Group'
2. Add groups with the '+' to the right of the group names
3. Check off cells under 'Cells in Group' to add them to the currently selected group

 - A cell can only be in one group at a time

 .. figure:: files_static/cellgroups.png
     :alt: Adding Cells to Groups
     :width: 200

********************
Changing Cell Colors
********************

1. Select the Cell Group you would like to change display settings for
2. Expand 'Cell Group Options'
3. Next to 'Init. Color', select a color on the color wheel

 .. figure:: files_static/initialcolor.png
     :alt: Select Group Color
     :width: 150

- The cells will be in that color the next time the cell group is imported

******************************
Visualizing Cell Model Voltage
******************************

1. Have your model with activity loaded in NEURON

 - To check activity in NEURON GUI, go to 'Graph' > 'Voltage Axis' and 'Tools > Run Control' and select 'Init & Run'

2. Select Cell Group to animate
3. Expand 'Cell Group Options'
4. Check off 'Record Activity'

 - Activity will be recorded next time the cells are imported

5. Choose Recording Settings

 - Set start and stop recording times (in ms): what time range in the NEURON simulation to record
 - Select 'Sampling Period': how many milliseconds between samples collected of the voltage
 - Select 'Frames per Milliseconds', how many frames of animation will represent each millisecond of NEURON activity
 - Set colors to correspond with the variable low and high values on the color scale
 - Set variable low and high values to encompass the activity in your model

6. Import cells with 'Import Cell Groups to Blender' under 'Import / Export'
7. Scrub the timeline on the bottom to see animation

 - Change in voltage should be visible as change in color and/or brightness (to preview change in brightness, press 'Z' > 'Material Preview')
 - Frame number = NEURON simulation time (ms) X 'Frames per Millisecond'

 .. figure:: files_static/timeline.png
     :alt: Timeline
     :width: 600

******************************
Creating Synapses by Proximity
******************************

1. Make sure to have at least 2 cells instantiated in NEURON
2. Add cells that will form synapses to different groups
3. Expand 'Form Synapses'

 - This section will appear when you have at least two groups

4. Select groups for the 'Source' (presynaptic) and 'Destination' (postsynaptic) cells

 - Must be different groups

5. Select which sections will form synapses next to 'Sections:'

 - Surround characters with asterisks (\*example\*) to include all sections with those characters in the name

6. Select synaptic mechanism next to 'Synapse', if you have additional mechanisms loaded in NEURON

 - By default, NEURON lets you use 'ExpSyn' mechanism
 - For help on compiling mod files to add mechanisms: `Mod Files <https://www.neuron.yale.edu/phpBB/viewtopic.php?t=3263&sid=2c672c89ff0c1c17a90f35d3c44696d0>`_

7. Press 'Find Synapse Locations'

 - Synapse locations will be shown in orange

 .. figure:: files_static/synapsepreview.png
     :alt: Synapse Preview
     :width: 300

8. Create the synapses in NEURON by pressing 'Create Synapses'

******************************
Confining Cells between Layers
******************************

1. Import cells with 'Import Cell Groups to Blender'
2. Import or create mesh object(s) to confine the cells between
3. Expand 'Confine Between Layers'

 - Section will appear once at least 1 cell is imported

4. Select objects for the confinement 'Start Layer' and 'End Layer'
5. Next to 'Name Contains:', select sections that will be confined

 - Surround characters with asterisks (\*dend\*) to confine all sections with those characters

6. Press 'Confine' to confine the sections between the layers
7. Save changes in Blender by pressing 'Update Groups with Confinement Results'
8. Save confinement results to NEURON by pressing 'Export Cell Groups to NEURON' under 'Import / Export'
