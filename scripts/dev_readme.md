# Purpose
This folder stores a Dockerfile that builds an image with pre-built NEURON+Python and Blender.
The add-on from this repo is linked and installed into Blender.
The image also creates a VNC server with a windowing system that enables to see the GUI of Blender
running inside the container.
The unit test suite is run from inside the container as well.

The purpose of the image is to provide a development environment with all the dependencies packaged
inside the container.

# How to Use
1 ) From this directory, build the Docker container with:
```
./build.sh
```

2 ) Then run the container with:
```
./run.sh
```
This will start the container and start a VNC client to show the containers's window system.

## Starting new terminal windows
One terminal window can be used to run NEURON, and another to run Blender. This way, a NEURON model
does not need to be re-initialized if Blender needs to be restarted.

Start a new terminal window with:
```
xterm & disown
```

## Starting NEURON
NEURON is pre-installed inside the container, start it with regular commands:
```
nrngui -python
 - or -
python -i -c 'from neuron import h,gui'
```

To start the NEURON part of BlenderNEURON, run the following command inside NEURON's python console:
```
from blenderneuron import neuronstart
```

## Starting Blender
Start pre-installed Blender with the addon linked to this repo with:
```
blender -noaudio
```
The extra flag is optional, but prevents audio-related warnings when running Blender from inside the container.


# Unit Tests
From inside the container, run the test suite with:
```
./test.sh
```

The script also checks code coverage, which can be viewed in this repo path:
```
htmlcov/index.html
```
