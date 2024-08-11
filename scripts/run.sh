#!/bin/bash
set -e
./build.sh

# -v -> Links the [repo] folder to container's /BlenderNEURON folder
# -p -> Exposes the default VNC port
# --detach -> Runs the container in the background
# -e RESOLUTION=1024x768 # Sets the VNC server resolution

echo "Starting BlenderNEURON Docker container..."
container_id=$(docker run \
    -it \
    -e RESOLUTION=1024x768 \
    -v $(readlink -f ../):/BlenderNEURON \
    -p 5920:5920 \
    --detach \
    blenderneuron:latest)

# Wait until the container has started and setup the VNC server
echo "Starting VNC client..."
sleep 1
while ! nc -z localhost 5920; do
  sleep 0.1 # sec
done

echo "VNC connected"
sleep 5
echo " -- -- -- -- -- -- -- Quick Start Guide -- -- -- -- -- -- -- -- -- -- -- -- --"
echo "The basic steps are:"
echo " 1) Start NEURON"
echo " 2) Start BlenderNEURON within NEURON"
echo " 3) Start Blender (BlenderNEURON addon is pre-installed)"
echo ""
echo "1. START NEURON:"
echo " Inside the VNC window terminal, type:"
echo " 'ipython' then type 'from neuron import h, gui'"
echo " You should see the familiar NEURON GUI"
echo ""
echo "2. START BlenderNEURON WITHIN NEURON"
echo " Inside NEURON's iPython session, type:"
echo " 'from blenderneuron import neuronstart'"
echo " No errors means BlenderNEURON has started inside NEURON"
echo " Once Blender is started, the addon will establish communication with NEURON"
echo ""
echo "3. START BLENDER"
echo " Inside NEURON iPython session, type:"
echo " '!blender'"
echo " This will launch Blender with pre-installed BlenderNEURON addon"
echo " It will also establish communication with NEURON"
echo " On the far left side, there should be 'BlenderNEURON' tab"
echo " Within the tab, Node Status section should show 'Connected'"
echo " If not, follow step 2 above."
echo ""
echo "TO QUIT"
echo " Close the VNC window. This will stop NEURON, Blender, and the container."
echo ""
echo "The addon code in [repo root]/blenderneuron directory is"
echo " linked to Blender addons directory. Any changes to the"
echo " addon code should be visible after NEURON or Blender are restarted."
echo " -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --"

# Assumes Ubuntu, where vinagre VNC client is pre-installed
# Change the line below to use your own VNC client
vinagre --vnc-scale 0.0.0.0:5920

echo "Stopping BlenderNEURON container"
docker stop -t 0 $container_id