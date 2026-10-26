Offline Simulation Results
==========================

Build a NEURON model, save its cell morphology and optional recorded activity to a file,
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
   - Variable names can be direct (``v``, ``ina``, ``i_pas``) or dotted mechanism paths
     (``pas.i``, ``hh.m``). Do not include ``_ref_``; expressions such as ``ina + ik`` are not supported

3. Initialize and run your simulation using your existing code

   .. code-block:: python

      h.finitialize(-65)
      h.continuerun(100)

   ``prepare()`` installs the same native vector recorder used by
   live imports. It does not initialize or run the model. Configure it before
   ``finitialize`` and keep the export object and model cells alive throughout
   the run. Keep morphology fixed during recording. Each initialization clears
   the previous traces and creates fresh vectors for the current granularity,
   variable and geometry. Samples are requested at ``start + n * recording_period``;
   a finite end time includes its endpoint when it lies on that sampling grid.
   An end time of zero allows recording to continue without knowing the final
   simulation time, including across multiple ``continuerun`` calls.

   Displayed 3D intervals that read the same computational compartment share one
   native trace. Recorded activity exposes live read-only sequences; use
   ``list(...)`` for mutable copies. Exporting formats these directly without
   duplicating every trace into Python float lists.
   Saving does not detach the recorder, so the simulation can continue afterward.
   Retired vectors detach at the next initialization, after NEURON clears queued
   recording events; they are not reused for the new run.

4. After the simulation finishes, save the results:

   .. code-block:: python

      export.save('simulation.bnresults')

   Saving collects the recorded samples without advancing or rerunning the
   simulation. The file contains group membership, full cell morphology,
   recording settings, units, and any collected activity. If a group has no
   samples, it is saved automatically as morphology only.

For a complete example, see ``tutorials/offline_simulation.py`` in the repository.
Run it with ``python tutorials/offline_simulation.py``.

************************
Save Only the Morphology
************************

Call ``save()`` immediately after ``prepare()`` to save cells without initializing
or running NEURON. No extra option is needed:

.. code-block:: python

   export = SimulationExport()
   export.add_group('Network', roots=local_roots)
   export.prepare()
   export.save('morphology.bnresults')

This writes the full section hierarchy, coordinates, and radii without activity
arrays. Import the file with the same 'Import Saved Simulation Results...' button:
Blender builds the cells without animation data.

If you later run the simulation and call ``save()`` again on the same exporter,
the new file includes the collected activity automatically. The choice is made
per group on each save. A group with no samples in its recording window saves
morphology only; a file can contain both recorded and morphology-only groups.

Optionally pass ``record_activity=False`` to ``add_group()`` to disable recording
for a group entirely. No activity collectors are installed for that group, and
the recording variable need not exist in the model.

Morphology-only exports also work with MPI; every rank still calls ``prepare()``
and ``save()``, but the simulation step can be skipped.

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
4. View the morphology, or scrub the timeline if the file contains recorded activity

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
