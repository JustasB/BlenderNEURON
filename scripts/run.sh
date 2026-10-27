#!/bin/bash
set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_dir="$(cd "$script_dir/.." && pwd -P)"
vnc_password="${VNC_PASSWORD:-blender}"
case "$(uname -m)" in
    x86_64|amd64) host_arch=amd64 ;;
    arm64|aarch64) host_arch=arm64 ;;
    *) echo "Unsupported host architecture: $(uname -m)" >&2; exit 1 ;;
esac
docker_platform="${DOCKER_PLATFORM:-linux/$host_arch}"
vnc_host="127.0.0.1"
vnc_port="5920"

cd "$script_dir"

start_vnc_client() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        open -W "vnc://$vnc_host:$vnc_port"
        return
    fi

    if command -v vinagre >/dev/null 2>&1; then
        vinagre --vnc-scale "$vnc_host:$vnc_port"
        return
    fi

    if command -v vncviewer >/dev/null 2>&1; then
        vncviewer "$vnc_host:$vnc_port"
        return
    fi

    echo "No supported VNC client found."
    echo "Install vinagre or vncviewer, or connect a VNC client to $vnc_host:$vnc_port."
    return 1
}

wait_for_vnc() {
    local banner

    while true; do
        if exec 3<>"/dev/tcp/$vnc_host/$vnc_port" 2>/dev/null; then
            banner="$(dd bs=3 count=1 <&3 2>/dev/null || true)"
            exec 3<&-
            exec 3>&-

            if [[ "$banner" == "RFB" ]]; then
                return
            fi
        fi

        sleep 0.1
    done
}

./build.sh

# -v -> Links the [repo] folder to container's /BlenderNEURON folder
# -p -> Exposes the default VNC port
# --detach -> Runs the container in the background
# -e RESOLUTION=1024x768 # Sets the VNC server resolution

echo "Starting BlenderNEURON Docker container..."
container_id=$(docker run \
    --platform "$docker_platform" \
    -it \
    -e RESOLUTION=1024x768 \
    -e VNC_PASSWORD="$vnc_password" \
    -v "$repo_dir":/BlenderNEURON \
    -p "$vnc_host:$vnc_port:$vnc_port" \
    --detach \
    blenderneuron:latest)

cleanup() {
    echo "Stopping BlenderNEURON container"
    docker stop -t 0 "$container_id" >/dev/null
}
trap cleanup EXIT

# Wait until the container has started and setup the VNC server
echo "Starting VNC client..."
sleep 1
wait_for_vnc

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
echo "VNC LOGIN"
echo " If prompted for a password, use: $vnc_password"
echo ""
echo "The addon code in [repo root]/blenderneuron directory is"
echo " linked to Blender addons directory. Any changes to the"
echo " addon code should be visible after NEURON or Blender are restarted."
echo " -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --"

start_vnc_client
