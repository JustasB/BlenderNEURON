Remote Connections and MPI
==========================

BlenderNEURON normally connects Blender and NEURON automatically on the same
computer. Each application listens on ``127.0.0.1``, selects an available port,
and writes its address to a file in the user's private settings directory. The
two applications discover each other's addresses there and read the same
``local-secret`` file to authenticate requests. The secret is saved between
sessions; it is not a temporary file that must be exchanged again at each start.

When NEURON runs in Docker or on another computer, it has a separate network
and settings directory. Keep Blender on your local computer and configure the
connection manually using the steps below. After connecting, use
:doc:`getting-started` to import and edit cells.

For MPI jobs or scripts that run to completion, use :doc:`offline-simulation`
instead. Configure recording in the script, run the simulation, and save a
``.bnresults`` file to import into Blender later. Blender does not need to be
running during the job, and no pairing or network connection is needed. The
Docker and SSH instructions below apply to live connections.

Connection addresses
--------------------

Both applications receive requests, so both need a listening address and an
address for the other application:

- The listening address controls which interface an application receives requests on
- The peer address tells that application how to reach the other application
- Blender's 'NEURON address' is interpreted from Blender's computer
- NEURON's ``peer_address`` is interpreted from NEURON's computer or container

``127.0.0.1`` always refers to the computer or container using the address. It
does not refer to the other computer. With SSH forwarding, it can point to a
tunnel entrance on the same computer, which carries requests to the other end.
``0.0.0.0`` is a listening address for all interfaces; do not use it as a peer
address.

Throughout the manual connection examples, Blender uses port 8000 and NEURON
uses port 8001. These are example fixed ports, not the automatically selected
ports used for same-computer discovery. Choose available ports and update all
matching settings and forwarding rules if you change them.

Where settings are saved
------------------------

- Windows: ``%LOCALAPPDATA%/BlenderNEURON``
- macOS: ``~/Library/Application Support/BlenderNEURON``
- Linux: ``$XDG_CONFIG_HOME/blenderneuron`` (or ``~/.config/blenderneuron``)

This directory holds the local secret, discovery address files, and saved
connection settings. Set ``BLENDERNEURON_CONFIG_DIR`` to use another private
directory, such as a persistent container volume. Credentials are stored outside
the ``.blend`` file. Do not put them in a shared repository. Unix files use
private permissions; Windows uses the user profile directory's permissions.
Processes running as the same user can read them.

Pairing information
-------------------

Manual pairing gives both applications the same authentication secret. In the
Python session running your NEURON model, run:

.. code-block:: python

   from blenderneuron.neuronstart import BlenderNEURON
   print(BlenderNEURON.pairing_information())

The output is a JSON string with three fields. For example (the secret below is
a placeholder)::

   {"version": 1, "secret": "<64 hexadecimal characters>", "address": "http://127.0.0.1:8001"}

- ``version`` identifies the pairing information format, currently 1
- ``secret`` is the 64-character authentication secret that both applications must share
- ``address`` is the exporting application's listening URL, including its port

The exported address is not necessarily reachable from the other application.
For example, NEURON's ``127.0.0.1`` inside Docker refers to the container, while
Blender's ``127.0.0.1`` refers to the host. After importing pairing information,
replace the address and port with the ones reachable from the receiving
application, as shown in each example below. Keep the secret unchanged.

1. In Blender's 'Node Status', press 'Connect to NEURON...' (or 'Change connection...' for a saved connection)
2. Choose 'In Docker or on another computer'
3. Use 'Copy Python command' to get the command above and run it in NEURON
4. Copy the full JSON output, including the braces, and press 'Paste from clipboard' in Blender

   - You can also enter 'NEURON address', 'NEURON port', and 'Pairing secret' manually

5. Set the addresses and listening ports for your setup using the Docker or SSH steps below
6. Press 'Connect' ('OK' in Blender 4.0)

The settings are remembered. Use 'Reconnect' after restarting either application.
Reconnecting restores communication; it does not reload the model or recreate
cell groups and Blender objects.

.. warning::

   Pair only with processes you trust: a paired process can execute Python in
   the other application. Keep the JSON and secret private, including clipboard
   contents. Authentication does not encrypt HTTP traffic. Use SSH tunnels
   between computers.

Connection settings in Python
-----------------------------

``configure_connection`` sets NEURON's listening interface and port, the address
it uses to reach Blender, and optionally pairing information copied from Blender:

.. code-block:: python

   BlenderNEURON.configure_connection(
       mode="manual",
       listen_host="127.0.0.1", listen_port="8001",
       peer_address="http://127.0.0.1:8000",
       pairing=blender_pairing_string)

In this example, NEURON receives requests on port 8001 and reaches Blender on
port 8000. The loopback addresses work when both applications are on the same
computer, or when using the SSH tunnels below. For Docker, use the host address
reachable from the container as shown in the next section.

``blender_pairing_string`` is the JSON copied with 'Copy Blender connection
information' in the dialog's 'Advanced' section. Omit ``pairing`` when using
NEURON's secret and importing its JSON into Blender instead. The explicit
``peer_address`` overrides the address in the imported JSON.

Restart the NEURON node/process after changing its listening interface or port.
Then retrieve its pairing information. Use ``BlenderNEURON.test_connection()``
to check whether Blender is authenticated and reachable from NEURON.

*****************
Connect to Docker
*****************

In this example, Blender runs on the host and NEURON runs inside a container.
NEURON listens on container port 8001; Blender listens on host port 8000.
Docker publishes NEURON's port on the host, so Blender sends requests to host
port 8001. NEURON sends requests back directly to Blender's host port 8000.

.. list-table::
   :header-rows: 1
   :widths: 15 40 45

   * - Port
     - On the host (Blender's computer)
     - Inside the container
   * - 8000
     - Blender listens here
     - No listener; NEURON sends requests to the host's port 8000
   * - 8001
     - Docker publishes this port and forwards to container port 8001
     - NEURON listens here

1. Publish NEURON's port when starting the container by adding this option to ``docker run``:

   .. code-block:: sh

      -p 127.0.0.1:8001:8001

   The format is ``host-address:host-port:container-port``. Here, host port
   8001 forwards to container port 8001. Blender reaches the published port at
   ``127.0.0.1:8001`` on the host; this is Blender's 'NEURON address' and port,
   not Blender's own listening address and port.

2. Choose a host IP address reachable from the container

   For this example, assume the host has address ``192.168.1.10`` and the
   container can reach it. Replace this example IP with your host's reachable
   address in both Blender's listening settings and NEURON's ``peer_address``.
   Do not use the container's IP here.

3. In Blender's connection dialog, select 'In Docker or on another computer' and expand 'Advanced'

   - Set 'Listen address' to the host's reachable IP (``192.168.1.10`` in this example)
   - Enable 'Use a fixed listening port' and set it to 8000
   - Allow connections from the container to this interface and port through the host firewall

4. In the container's NEURON Python session, configure:

   .. code-block:: python

      from blenderneuron.neuronstart import BlenderNEURON
      BlenderNEURON.configure_connection(
          mode="manual", listen_host="0.0.0.0", listen_port="8001",
          peer_address="http://192.168.1.10:8000")

   ``listen_host="0.0.0.0"`` lets NEURON receive Docker's forwarded requests
   on container port 8001. ``peer_address="http://192.168.1.10:8000"`` tells
   NEURON to send requests to Blender's port 8000 on the host. Using
   ``127.0.0.1`` here would send requests to the container itself.

5. Restart the NEURON node/process and copy its pairing JSON into Blender as described above
6. In Blender, set 'NEURON address' to ``127.0.0.1`` and 'NEURON port' to 8001, then press 'Connect'

The two request paths are::

   Blender on host -> host 127.0.0.1:8001 -> Docker forwarding -> NEURON container :8001
   NEURON container -> host 192.168.1.10:8000 -> Blender

The host address used for the return path depends on your Docker network setup.
Publishing NEURON's port sets up only the first path; it does not make Blender's
host loopback listener reachable from inside the container. Docker on Windows
and macOS also uses a separate container network.

***************************************
Connect to a Remote Machine through SSH
***************************************

Blender and NEURON both send requests to each other. SSH therefore needs two
tunnels: one to reach NEURON from Blender, and one to reach Blender from NEURON.
This example uses port 8000 for Blender and port 8001 for NEURON:

.. list-table::
   :header-rows: 1
   :widths: 15 35 50

   * - Port
     - On your local computer
     - On the remote computer
   * - 8000
     - Blender listens here
     - SSH listens here and forwards to local Blender port 8000
   * - 8001
     - SSH listens here and forwards to remote port 8001
     - NEURON listens here

Each port number is used on both computers. Port 8000 belongs to Blender
locally and to its SSH tunnel entrance remotely. Port 8001 belongs to NEURON
remotely and to its SSH tunnel entrance locally. Reusing the numbers works
because the listeners are on different computers. All listeners use
``127.0.0.1`` on their own computer.

These port numbers are examples. Choose available ports and keep the application
settings and SSH forwarding command consistent if you change them.

1. In Blender's connection dialog, choose 'In Docker or on another computer' and expand 'Advanced'

   - Set 'Listen address' to ``127.0.0.1`` (Blender's local computer)
   - Enable 'Use a fixed listening port' and set it to 8000

2. In the remote NEURON Python session, configure:

   .. code-block:: python

      from blenderneuron.neuronstart import BlenderNEURON
      BlenderNEURON.configure_connection(
          mode="manual", listen_host="127.0.0.1", listen_port="8001",
          peer_address="http://127.0.0.1:8000")

   ``listen_port="8001"`` is NEURON's own receiving port on the remote computer.
   ``peer_address="http://127.0.0.1:8000"`` tells NEURON where to send requests
   for Blender: to SSH's port 8000 on that same remote computer. SSH forwards
   those requests to Blender's port 8000 on your local computer. The SSH command
   below creates this tunnel.

3. Restart the NEURON node/process to apply its listening settings
4. On your local computer, run:

   .. code-block:: sh

      ssh -N -L 8001:127.0.0.1:8001 -R 8000:127.0.0.1:8000 user@remote

   - Replace ``user@remote`` with your SSH account and the remote hostname or IP
   - Leave this terminal running while using BlenderNEURON
   - ``-L 8001:127.0.0.1:8001`` creates a local SSH listener on port 8001 and forwards requests to NEURON's remote port 8001
   - ``-R 8000:127.0.0.1:8000`` creates a remote SSH listener on port 8000 and forwards requests to Blender's local port 8000

   The request paths are::

      Local computer                         Remote computer
      ----------------                       ----------------
      Blender
        | requests to local :8001
        v
      SSH listener :8001 ---- SSH ---------> NEURON :8001

      Blender :8000 <-------- SSH ---------- SSH listener :8000
                                               ^
                                               | requests to remote :8000
                                             NEURON

   All listeners in this diagram use ``127.0.0.1`` on their own computer.

5. Copy NEURON's pairing JSON into Blender using the pairing steps above
6. In Blender, set 'NEURON address' to ``127.0.0.1`` and 'NEURON port' to 8001, then press 'Connect'

   Blender's address points to the SSH listener on your local computer, rather
   than directly to the remote computer. NEURON's peer address points to the
   SSH listener on the remote computer.

Keep the computers' clocks synchronized; authenticated requests allow 60 seconds
of clock difference. If a jump host is required, add ``-J user@login`` and use
the computer running NEURON as the destination. Follow your site's access and
port forwarding rules.

*******************
Use NEURON with MPI
*******************

Use the saved-results workflow for MPI simulations:

1. Configure groups and activity recording in your simulation script after building the local cells on each rank
2. Run the simulation using your model's initialization and solver code
3. Call ``SimulationExport.save()`` on every rank; rank 0 writes one combined ``.bnresults`` file
4. After the job finishes, copy the file to your Blender computer
5. In Blender's 'Import / Export' panel, press 'Import Saved Simulation Results...' and select the file

For a complete example, run this command from the repository root on the machine
running NEURON:

.. code-block:: sh

   mpiexec -n 2 nrniv -mpi -python tutorials/offline_simulation.py

This script configures recording, runs a short simulation, and saves
``simulation.bnresults`` in the working directory. Use your cluster's launcher
or job submission command as appropriate. Blender can remain closed until you
are ready to import the file.

See :doc:`offline-simulation` for the script API, group settings, and importing
recorded activity. To collect different activity or change the model, update
and rerun the script, then import the new results file.
