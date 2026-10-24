Remote connections and MPI
==========================

Local connections
-----------------

The Node Status panel defaults to Automatic local. One Blender instance and
one NEURON instance discover each other using private per-user files.
Pairing credentials survive either or both applications restarting. Reconnection
restores communication, not simulation data, groups, or Blender objects.
Startup attempts a connection; use Connect or Reconnect to retry manually.
There are no periodic retries for application nodes.

Pairing grants arbitrary Python execution with the receiving process's account
permissions. Pair only trusted processes. Requests are authenticated but HTTP
traffic is not encrypted; use user-managed SSH tunnels between machines.
No additional Python packages or built-in SSH management are required.

Remote pairing
--------------

In Node Status, click **Connect to NEURON...** (or **Change connection...**
for a saved connection), then choose **In Docker or on another computer**.
The dialog explains where to get pairing information: use **Copy Python command**,
paste that command into the Python session running your NEURON model, and run it.
Copy the full JSON output, including the braces, return to Blender and choose
**Paste from clipboard**. This loads the credentials and suggested NEURON address.
The masked **Pairing secret** field also supports manual entry: enter the NEURON
address, port, and 64-character secret instead of importing the full JSON.
A preview shows only the first four and last two characters of the saved secret.
The secret stays in private connection settings, outside the ``.blend`` file.
Adjust the address and port for Docker or an SSH tunnel, then confirm **Connect**
(**OK** in Blender 4.0). The settings stay remembered; use **Reconnect** after restarting.

The dialog's **Advanced** section shows Blender's actual listening address and
port, labeled as automatic or fixed. Automatic selection chooses an available
port. Enable **Use a fixed listening port** to enter a predictable port for a
tunnel or callback. The current port is suggested when enabling this option.
Changes are applied when connecting, and **Copy Blender connection information**
for configuring NEURON's callback. The callback must use an address reachable
from NEURON (or its tunnel), which can differ from the local listener address.
**Forget saved connection** revokes credentials. The clipboard contains a secret:
do not post it in logs or issues.

In NEURON, the same operations are available on the node:

.. code-block:: python

   from blenderneuron.neuronstart import BlenderNEURON
   BlenderNEURON.configure_connection(
       mode="manual", listen_port="8001",
       peer_address="http://127.0.0.1:8002")
   # Restart the NEURON node/process to apply the listening port.
   pairing = BlenderNEURON.pairing_information()
   # Transfer pairing privately to Blender and paste it there.
   BlenderNEURON.test_connection()  # True when authenticated and reachable

Either endpoint can supply the secret. To accept Blender's exported string:

.. code-block:: python

   BlenderNEURON.configure_connection(
       mode="manual", pairing=blender_pairing_string,
       peer_address="http://127.0.0.1:8002", listen_port="8001")

SSH tunnels
-----------

For example, Blender listens on laptop port 8000; NEURON listens on remote
port 8001. From the laptop, keep this terminal command running:

.. code-block:: sh

   ssh -N -L 8001:127.0.0.1:8001 -R 8002:127.0.0.1:8000 user@remote

Blender's peer is 127.0.0.1:8001; NEURON's peer is 127.0.0.1:8002.
Both servers can keep listening on loopback. Both directions are required.
The command uses the system SSH client, outside either Python environment.
Keep the two machines' clocks synchronized (requests allow 60 seconds of skew).
For a cluster, SSH must reach the host running rank zero; use a jump host
(``ssh -J user@login ... user@compute``) when required by the cluster.
Follow the cluster's access policies and forwarding restrictions.

Containers and operating systems
--------------------------------

Settings live in LOCALAPPDATA/BlenderNEURON on Windows,
~/Library/Application Support/BlenderNEURON on macOS, and
$XDG_CONFIG_HOME/blenderneuron (or ~/.config/blenderneuron) on Linux.
Unix directories/files use private permissions; Windows relies on the user's
profile directory ACLs. Processes running as the same user can read credentials.
BLENDERNEURON_CONFIG_DIR can select a private persistent directory, for example
on a container volume. Never put credentials in a shared repository.

A container has its own loopback interface. For host-to-container connections,
bind the container server to 0.0.0.0 inside the container and publish its port
on the host's loopback, for example ``-p 127.0.0.1:8001:8001``. Route the reverse
direction explicitly through an SSH forward or a host address accessible from
the container. Automatic discovery requires a shared private directory and
mutually reachable addresses; otherwise use Manual connection. Windows/macOS
Docker hosts still run Linux containers; their files and network are separate.

Recovery and forgetting
-----------------------

Retain the same ports and credentials to reuse tunnels after restarting.
If disconnected, check the tunnel, addresses and ports, then click Reconnect or call test_connection(). Restarting does not reconstruct model state.
Forget connection immediately invalidates that node's credentials and clears
its client. Pair again to reconnect. It does not delete model or scene data.
The matching Python helper is ``BlenderNEURON.forget_connection()``.

*******************
Use NEURON with MPI
*******************

Blender communicates only with MPI rank 0. BlenderNEURON distributes requests
to worker ranks and rank 0 merges their results before replying, so no Blender
configuration is MPI-specific.

Start the same model script on every rank (for example with ``mpiexec``) and
import ``blenderneuron.neuronstart`` on every rank after the local model is
built. ``mpimap`` is the optional mapping from a Blender-visible cell name to
its MPI-local cell name and owning rank. BlenderNEURON derives it automatically.

For example, if rank 0 and rank 1 each independently instantiate
``MitralCell.hoc``, both local cells may be named ``MitralCell[0]``. Automatic
discovery gives Blender distinct, rank-qualified names while preserving each
rank's local name:

.. code-block:: python

   MitralCell_rank0[0]  -> rank 0 local MitralCell[0]
   MitralCell_rank1[0]  -> rank 1 local MitralCell[0]

After model setup, initialize and start the coordinator on every rank:

.. code-block:: python

   from neuron import h
   from blenderneuron.neuronstart import BlenderNEURON

   pc = h.ParallelContext()
   BlenderNEURON.init_mpi(pc)  # derive mpimap, or pass an explicit override
   BlenderNEURON.start_mpi_coordinator()

On rank 0 this returns and Blender connects normally. Worker ranks wait for
requests from rank 0. Call ``BlenderNEURON.stop_mpi_coordinator()`` on rank 0
to release workers before further rank-local script work or shutdown.

Rank 0 knows the expected count from ``pc.nhost()``, but cannot force
already-running MPI processes to import Python. Launching the same script with
``mpiexec`` is what ensures every rank loads BlenderNEURON and reaches the
coordinator loop.

Manual Windows smoke test
-------------------------

On a Windows machine, start Blender and NEURON locally and confirm automatic
connection, cell import, and a command sent in each direction. Restart each
application separately and reconnect without copying credentials. Confirm that
Forget connection rejects the old pairing. For a Linux container on Windows,
repeat in Manual connection mode with a loopback-published container port and
an explicitly routed reverse connection. Recreate groups/model data as needed;
only connection settings persist. Native Windows CI checks storage,
authentication, sockets, and peer restart using standard Python; it does not
install Blender or NEURON.
