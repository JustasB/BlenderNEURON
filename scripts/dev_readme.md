# Purpose
This folder stores a Dockerfile that builds an image with pre-built NEURON+Python and Blender.
The add-on from this repo is linked and installed into Blender.
The image also creates a VNC server with a windowing system that enables to see the GUI of Blender
running inside the container.
The unit test suite is run from inside the container as well.

The purpose of the image is to provide a development environment with all the dependencies packaged
inside the container.

The `./run.sh` file supports Ubuntu/Linux and macOS.
On macOS, it opens the built-in Screen Sharing VNC client.
On Linux, it uses `vinagre` or `vncviewer` when available.
The Docker image selects your host architecture automatically: `linux/amd64`
uses Blender 5.2.3 (the same archive as CircleCI), while `linux/arm64` uses
Ubuntu's native Blender package.
Set `DOCKER_PLATFORM=linux/amd64` or `DOCKER_PLATFORM=linux/arm64` before
`./run.sh` or `./build.sh` to select a specific image variant.
The default VNC password is `blender`; set `VNC_PASSWORD=yourpass ./run.sh`
to use a different one. VNC passwords should be 8 characters or fewer.

# How to Use
From this directory, run the container with:
```
./run.sh
```
This will pull a pre-build container image from Docker Hub, start the container, 
and start a VNC client to show the containers's window system.

You can edit the `./run.sh` file to use a different VNC client, link own folders to
the container, etc...

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

During test execution you should see movement within the Blender window. Printed messages
are normal. At the end there should be coverage table, and above it it should say
`Ran 1 test in YY.ZZs` for each isolated test. Each must report `OK`, and the
coverage commands must also succeed.

The runner gives each test 180 seconds and exits with status 124 on timeout.
Override this for slower machines with
`BLENDERNEURON_TEST_TIMEOUT=300 sh ./test.sh`. Startup probes and worker waits
also have deadlines. Blender and NEURON are launched in owned process groups;
cleanup sends TERM, then KILL if necessary, and waits for their exit. The Linux
runner adopts and reaps orphaned descendants after each test, including failures
and handled interruptions. Use Docker's `--init` flag when starting a test
container so its init process also reaps children after an abrupt runner exit.
After a forcibly killed runner or container-level failure, use a fresh container.


## Modifying the Addon
The container links the `[repo]/blenderneuron` folder to Blender addon folder. 
It also puts the linked folder into PYTHONPATH environment variable.
Any changes to BlenderNEURON code will be visible once Blender or NEURON are
restarted.

Majority of code for the **NEURON** part of BlenderNEURON is stored in:
```
[repo]/blenderneuron/nrn
```

Majority of code for the **Blender** part of BlenderNEURON (the addon) is stored in:
```
[repo]/blenderneuron/blender
```
