Offline Simulation Results
==========================

Run a NEURON script, save the cell morphology and recorded activity to a file,
then import that file into Blender. Blender does not need to be running during
the simulation. This works for a local script or an MPI job, including jobs on
a remote cluster. No live connection, pairing, or SSH forwarding is needed.

***********************
Record and Save Results
***********************

1. Build your cells, connections, and stimuli in your NEURON script
2. Configure the groups you want to visualize, before initializing the simulation:

   .. code-block:: python

      from blenderneuron.nrn.offline import SimulationExport

      export = SimulationExport()
      export.add_group(
          'Network', roots=[cell.soma for cell in cells],
          recording_granularity='Section',
          record_variable='v', recording_period=0.1,
          recording_time_start=0.0, recording_time_end=0.0,
      )
      export.prepare()

   - Pass NEURON root sections in ``roots``; a cell can belong to only one group
   - Add more groups with additional ``add_group`` calls
   - 'Cell' records the root section midpoint; 'Section' records every section midpoint
   - '3D Segment' records between adjacent morphology points, matching Blender's segment animation
   - Recording is enabled by default, using voltage (``v``) at cell level with a 1 ms sampling period
   - Start and end times are in milliseconds; an end time of 0 includes samples through the end of the run
   - For a variable other than voltage, supply ``variable_units`` to describe its units

3. Initialize and run your simulation using your existing code

   .. code-block:: python

      h.finitialize(-65)
      h.continuerun(100)

   ``prepare()`` installs recording vectors. It does not initialize or run the
   model. Configure it before ``finitialize`` and keep the export object and
   model cells alive throughout the run. Keep morphology fixed during recording.
   Recording vectors retain the latest initialized run; the start/end window is
   applied when saving.

4. After the simulation finishes, save the results:

   .. code-block:: python

      export.save('simulation.bnresults')

   Saving collects the recorded samples without advancing or rerunning the
   simulation. The file contains group membership, full cell morphology,
   recording settings, activity, and units. Saving before recording any samples
   fails rather than writing an empty results file.

For a complete example, see ``tutorials/offline_simulation.py`` in the repository.
Run it with ``python tutorials/offline_simulation.py``.

************
Run with MPI
************

1. Create the exporter with your model's parallel context:

   .. code-block:: python

      export = SimulationExport(parallel_context=pc)

2. On each rank, add groups using that rank's local root sections

   - Use the same name for groups whose cells should be combined
   - Recording settings and supplied display settings must agree for a shared group
   - A rank may have different groups, empty groups, or no groups

3. Call ``export.prepare()`` on every rank before running the simulation
4. Run your parallel simulation normally, for example with ``pc.psolve()``
5. Call ``export.save('simulation.bnresults')`` on every rank

   - Results gather on rank 0, which writes one combined file
   - Cell and section names include a ``rank0::``, ``rank1::``, etc. prefix to distinguish identical local names
   - Setup and save errors are reported to all ranks; do not catch an error and continue the simulation
   - Rank 0 must have enough memory for the combined results

For example, launch the supplied example with:

.. code-block:: sh

   mpiexec -n 2 nrniv -mpi -python tutorials/offline_simulation.py

Use your cluster's launcher or submission command as appropriate. After the job
finishes, copy the results file to your Blender computer. No coordinator loop
or interactive Blender session is needed in the MPI script.

*******************
Import into Blender
*******************

1. Start Blender with the BlenderNEURON add-on
2. In the BlenderNEURON sidebar, expand 'Import / Export'
3. Press 'Import Saved Simulation Results...' and select your ``.bnresults`` file
4. Scrub the timeline to view the recorded activity

   - Use 'Cell Group Options' to change interaction level, colors, and brightness
   - After changing display options, press 'Show Imported Groups'
   - Under 'NEURON', adjust 'Blender frames per millisecond' to change animation speed
   - Recording settings describe what is already in the file and cannot be changed for this import

Node Status shows 'Offline Results' and the source filename. If you have a live
NEURON connection or dataset, importing the file asks for confirmation before
replacing it. Canceling leaves the connection and cells unchanged. Accepting
switches to offline mode and disconnects the NEURON client; saved pairing settings
are kept for later use.

Importing another results file replaces the previously imported dataset and its
cell objects. Other scene objects are kept. Matching group names retain their
Blender display settings unless the new file explicitly overrides them.

You can edit and render the visualization without NEURON running. Live simulation
and export controls are disabled for offline results. To collect a different
variable or recording detail, change the script, rerun the simulation, and import
the new file.

Saving a ``.blend`` keeps the offline mode, source filename, and a copy of the
simulation snapshot. Reopening it restores the offline dataset even if NEURON is
running or the original results file has been moved or deleted.

To return to live use, press 'Switch to Live NEURON...' in Node Status and confirm.
This removes the offline cells and groups before opening connection setup. Other
scene objects are kept. The live dataset starts empty, including if the subsequent
connection attempt fails. Add groups after connecting to your live model.

A live disconnection does not switch modes or delete cells. After reconnecting,
exporting retained cells asks for confirmation because the running model may have
changed. A process restart does not prove that it is a different model; review
the warning and choose whether to export or import the live cells again.

***************************
Set Optional Display Values
***************************

Supply ``display`` when declaring a group to set its initial appearance:

.. code-block:: python

   export.add_group(
       'Network', roots=local_roots,
       recording_granularity='Section',
       display={
           'default_color': [0.1, 0.3, 0.8, 1.0],
           'interaction_granularity': 'Cell',
           'animation_range_low': -85,
           'animation_range_high': 20,
       },
   )

Each supplied value overrides the corresponding Blender setting on every import.
Omitted values retain the existing group's settings, or use the add-on defaults
for a new group. Animation speed stays in Blender and is not stored in the file.

Other supported display values are ``smooth_sections``, ``spherize_soma_if_DeqL``,
``as_lines``, ``segment_subdivisions``, ``circular_subdivisions``,
``default_brightness``, ``animate_brightness``, ``max_brightness``,
``animate_color``, and ``simplification_epsilon``.
