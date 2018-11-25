Visualizing Using Python Commands
=========================================

The following tutorial assumes you are familiar `with visualizing using the GUI <gui.html>`_.

****************
Before starting:
****************

1. Load Blender with the BlenderNEURON add-on (NEURON tab should be visible in Blender left panel)
2. Load your model in NEURON
3. Load BlenderNEURON in NEURON by running ``from blenderneuron.quick import bn``
4. Test the connectivity between NEURON and Blender with ``bn.is_blender_ready()`` (Should say "True")

See `Installation <installation.html>`_ for how to install the python library and the Blender addon.

***************************
Visualizing Morphology
***************************

Follow these steps to visualize the cell morphology of a NEURON model:

1. Once your model is loaded, run `bn.to_blender()`
2. A moment later, your model should appear in Blender
3. Navigate around the Blender scene to inspect the model. If you're not familiar with Blender, `these tutorials
   <https://cloud.blender.org/p/blender-inside-out/560414b7044a2a00c4a6da98>`_ will give an overview of basic scene
   navigation.



By default, BlenderNEURON will export the morphology of all cells (sections) in the model. It will use NEURON's
x/y/z3d() and diam3d() values to build the 3D meshes in Blender.

In within Blender, 1 cm is set to correspond to 1 micron in NEURON.

If you add or make changes to your model's sections/cells, run `bn.refresh()` before running `bn.to_blender()` to ensure
that the changes are included in the export.

For a more detailed control of the export process, see the `client library API <client.html>`_


A complete example of exporting a model to Blender::

    from blenderneuron.quick import bn # import the BlenderNEURON library

    assert bn.is_blender_ready()       # check if communication with Blender can be established

    #bn.refresh()                      # uncomment this if there has been a model change since last run

    bn.to_blender()                    # send section morphology data to Blender


***************************
Visualizing Activity
***************************

Follow these steps to visualize the morphology and simulated activity of a NEURON model:

1. Once your model is loaded, run `bn.prepare_for_collection()`. This will add a handler to gather section
   voltage values during the simulation.
2. Run your simulation (e.g. `h.run()`)
3. Once the simulation is finished, run `bn.to_blender()`
4. A moment later, your model should appear in Blender
5. Use the buttons under the bottom timeline in Blender to re-play the simulation. If your cells emit action
   potentials (Vm > -20mV), you should be able to see them as glowing compartments. By default, 1 frame in Blender
   corresponds to 0.5ms in NEURON.
6. You can scrub the timeline to re-play any part of the simulation and use the left/right arrow keys to step
   through the frames.

.. image:: files_static/timeline.JPG

A complete example of exporting a model with activity to Blender::

    from blenderneuron.quick import bn # import the BlenderNEURON library

    assert bn.is_blender_ready()       # check if communication with Blender can be established

    bn.prepare_for_collection()        # adds a NEURON handler to collect section activity data

    #bn.refresh()                      # uncomment this if there has been a model change since last run

    h.run()                            # run the simulation

    bn.to_blender()                    # send section morphology and activity data to Blender


************************************
Customizing Visualization Parameters
************************************

The default visualization parameters used by `bn.to_blender()` method can be customized. Each visualization group, 
composed of cell root sections, can have its own visualization parameters. By default one group, `all`, is created and contains the root sections of all cells in the model. 

Groups are stored in the `bn.groups` dictionary. To customize the default group's parameters, use the example script below.

In this example, the render detail of each cell will be reduced to improve performance (fewer polygons) in Blender::

    # Build and prepare your model
    prepare_model()

    # import BlenderNEURON
    from blenderneuron.quick import bn 

    # Create the default "all" group. Accessible with `bn.groups['all']`
    bn.setup_default_group()           

    # The whole group of cells is treated as one selectable Blender object (use 'Cell' to make cells individually selectable)
    bn.groups['all']['3d_data']['interaction_level'] = 'Group'     

    # Each cell will get its own color (each cell will have it's own Blender material)
    bn.groups['all']['3d_data']['color_level'] = 'Cell'  
          
    # Section compartments will be connected with straight-line cylinders (instead of curvy beziers)
    bn.groups['all']['3d_data']['smooth_sections'] = False  

    # Extra subdivisions are not necessary for straight-line cylinders
    bn.groups['all']['3d_data']['segment_subdivisions'] = 1

    # The cylinders will have pentagonal cross sections
    bn.groups['all']['3d_data']['circular_subdivisions'] = 5

    # Send all groups with the updated parameters to Blender
    bn.to_blender()                    






See documentation of the `create_cell_group </docs/client.html#blenderneuron.client.BlenderNEURON.create_cell_group>`_ 
method for values of other parameters.




