Docker Tutorial
===============

With Docker installed, you can run a complete BlenderNEURON example without
following the manual installation steps. The container provides Blender, NEURON,
and their dependencies. Clone the repository, build the image, and run the example
to produce a preview, an activity video, and an editable Blender scene. No GUI,
VNC, display server, or GPU is required on the host.

The example builds three independent branching Hodgkin–Huxley cells in NEURON,
injects staggered currents, and transfers morphology and membrane voltage to
Blender through BlenderNEURON's live connection. Blender renders all three cells
in one fixed orthographic view.

.. raw:: html

   <video controls autoplay muted loop playsinline preload="metadata" width="960"
          style="display: block; width: 100%; height: auto;"
          poster="_static/docker-tutorial-preview.png"
          aria-label="Three cells showing simulated membrane voltage over 30 milliseconds">
     <source src="_static/docker-tutorial-activity.mp4" type="video/mp4">
     <p>Your browser does not support embedded video.
       <a href="_static/docker-tutorial-activity.mp4">Download the activity video</a>.</p>
   </video>

.. only:: not html

   .. image:: files_static/docker-tutorial-preview.png
      :alt: Three cells with the middle cell near its voltage peak.
      :width: 960px

Build
-----

If you have not already cloned the `BlenderNEURON GitHub repository
<https://github.com/JustasB/BlenderNEURON>`_, clone it and enter its directory:

.. code-block:: sh

   git clone https://github.com/JustasB/BlenderNEURON.git
   cd BlenderNEURON

With Docker running, build the shared NEURON + Blender image from the root of
your local BlenderNEURON checkout:

.. code-block:: sh

   ./scripts/build.sh

The first build downloads the runtime dependencies and takes considerably longer
than the example itself. Subsequent builds reuse Docker's cache. The build script
selects the host architecture, including Apple Silicon. All commands below also
run from the repository root.

Simple example
--------------

Run with the default smoke-test settings: 320 × 240 pixels, 60 frames, four Cycles
samples per pixel, 20 FPS, and a 600-second deadline.

.. code-block:: sh

   mkdir -p "$PWD/tutorials/02-docker-script/output"
   docker run --rm --init \
     -v "$PWD:/BlenderNEURON:ro" \
     -v "$PWD/tutorials/02-docker-script/output:/output" \
     -w /BlenderNEURON blenderneuron:latest \
     python -u tutorials/02-docker-script/run.py

The terminal reports model startup, live transfer, frame-rendering progress, and
video encoding. Detailed runtime output is saved in ``neuron.log`` and ``blender.log``
inside the results folder. Long operations print a waiting update every 15 seconds.

The repository mount includes the editable tutorial scripts. Edit them on the
host, then repeat the same ``docker run`` command to use your changes. Each run
creates a new results subfolder without overwriting previous output. The ``:ro``
mount lets the container read the scripts without modifying them.

Full example with render options
--------------------------------

This complete command uses higher resolution, more frames, and more samples,
with a longer deadline. Change the values to suit your machine and desired
quality:

.. code-block:: sh

   mkdir -p "$PWD/tutorials/02-docker-script/output"
   docker run --rm --init \
     -v "$PWD:/BlenderNEURON:ro" \
     -v "$PWD/tutorials/02-docker-script/output:/output" \
     -w /BlenderNEURON blenderneuron:latest \
     python -u tutorials/02-docker-script/run.py \
     --width 960 \
     --height 720 \
     --frames 180 \
     --samples 32 \
     --fps 30 \
     --timeout 1800

Width and height must be even for H.264 video. The simulation remains 30 ms long
regardless of movie FPS or frame count. FPS controls playback speed; frame count
controls how finely the animation samples the simulation. Very sparse frames
can miss brief spikes. The timeout is in seconds and covers model startup,
transfer, rendering, and video encoding. Append ``--help`` after ``run.py`` to list
all options.

The convenience launcher builds the image and runs the same workflow:

.. code-block:: sh

   ./tutorials/02-docker-script/run.sh

It accepts the same render options. Set ``OUTPUT_DIR`` to change the host results
directory when using this launcher.

Output
------

The default render is deliberately small: 60 frames, 320 × 240 pixels, four
Cycles samples per pixel. Each run creates a dated subfolder inside the
``tutorials/02-docker-script/output/`` directory containing:

- ``preview.png``: one rendered frame at the first soma's voltage peak.
- ``activity.mp4``: voltage animation with simulation time in milliseconds
  (blue at −80 mV, red at +40 mV).
- ``frames/``: the individual PNG frames.
- ``scene.blend``: imported cells, voltage animation, orthographic camera, and
  the built-in neon glare compositor, ready for scrubbing or rendering.
- ``activity.json``: morphology and recorded activity received by Blender.
- ``summary.json``: soma peak voltages and basic run information. The example
  fails unless all three somas produce an action potential above 0 mV.
- ``settings.json``, ``neuron.log``, and ``blender.log``: configuration and diagnostics.

Reading and adapting the code
-----------------------------

``model.py`` defines the cells, their XY positions, membrane mechanisms, current
clamps, and simulation settings. Replace this section with your own model while
keeping references to cells and stimuli alive. The NEURON process stays running
so Blender can request data through the normal live API. This is a single-process
NEURON example; no MPI launch or custom compiled mechanisms are needed.

``render.py`` runs in Blender's Python interpreter. It registers the addon, connects
to NEURON, configures section-level voltage recording, and imports the group.
That import asks NEURON to run the simulation and return the recorded data over
the live connection. It then checks for spikes, frames all the cells from their
combined bounds, and renders using Cycles on CPU. Adjust the voltage range,
color ramp, camera margin, and caption there. Changing the model's duration also
requires updating the 30 ms animation mapping in this file.

``run.py`` starts and stops the two runtimes, limits the total execution time,
and writes logs. ``render.py`` uses Blender's video sequencer to assemble the
PNGs into an MP4. Width and height must be even for H.264 video. ``run.sh`` reuses
the repository build command and runtime image.
The run command overrides the development image's VNC startup command;
no display services are started and no network ports are published. The repository
and tutorial scripts are mounted, so edits take effect without rebuilding.
Rebuild with ``./scripts/build.sh`` only when changing the runtime dependencies.

Open ``scene.blend`` in Blender and scrub the timeline (frames 0–59 by default).
The baked material keyframes work without a running NEURON process or an addon
installation. In solid view the material colors show activity; use rendered view
or render a frame to see emission and the neon glare effect. Install BlenderNEURON
if you also want to use its model controls for a new live session. The saved
scene starts with a ``t = 0.0 ms`` caption; the tutorial rendering loop updates
that text for each frame in the PNG sequence and movie.
