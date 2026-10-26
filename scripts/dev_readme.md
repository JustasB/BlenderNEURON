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

CircleCI runs six independent native x86-64 compatibility jobs in parallel,
using one parameterized job and `compatibility/Dockerfile.integration`:

| Lane | NEURON | NEURON Python | Blender |
| --- | --- | --- | --- |
| `baseline` | 8.2.7 | 3.13.17 | 5.2.3 |
| `python2` | 8.0.2 | 2.7.18 | 5.2.3 |
| `neuron7` | 7.8.2 | 3.9.25 | 5.2.3 |
| `neuron9` | 9.0.2 | 3.14.9 | 5.2.3 |
| `blender2` | 8.2.7 | 3.13.17 | 2.93.18 |
| `blender4` | 8.2.7 | 3.13.17 | 4.5.15 |

Pins were verified on October 26, 2026. Blender always uses its own bundled
Python. The baseline serves both axes, avoiding a duplicate seventh run.
Python 2 wheels exist only in NEURON's 8.0.x series; 8.0.2 is the latest release
with them. No published NEURON 7 release has Python 2 wheels. The Python 2 lane
therefore assesses 8.0.2, while the NEURON 7 lane uses its newest supported
Python 3 wheel minor. Latest NEURON 8/9 no longer support Python 2.

Every lane installs a prebuilt NEURON wheel and a checksum-verified official
Blender archive. No Blender, Python or NEURON source compilation is required.
The existing `scripts/install_blender.py` installer is shared with the development
Dockerfile. CircleCI's machine executor supplies the native x86-64 Docker daemon and bind
mounts. Docker layer caching retains dependency images between runs; repository
code is mounted read-only and copied into a private checkout at runtime, so code
changes do not invalidate dependency layers. DLC does not guarantee that sibling
jobs can reuse a newly uploaded cache from the same workflow. CircleCI charges
additional credits for DLC; see its [cache documentation](https://circleci.com/docs/guides/optimize/docker-layer-caching/).
The existing development Dockerfile and tutorial/Windows jobs remain separate.
There is no native ARM64 compatibility source-build path.

All Python 3 lanes run `test.sh`, including Blender integration, MPI, process
cleanup, and the unchanged 91% coverage threshold. Failures do not prevent later
tests from being attempted. Each lane still fails on test or coverage failure;
there are no expected-failure exemptions. Python 2 executes every test module
under Python 2 and reports blocked imports/collection separately from executed
failures in `python2-assessment.json`. A Python 3 supervisor only supplies
cleanup/deadlines/reporting. The current package requires Python >=3.7; the
Python 2 lane measures the backport gap rather than claiming support. Coverage
5.5 records Python 2 execution; Blender's bundled Python produces the combined
reports while retaining the 91% threshold. Only the baseline uploads to Codecov;
all lanes publish their build/test logs, coverage XML/HTML, and result JSON as
CircleCI artifacts, including when a lane fails.

The suite deadline is ten minutes, each test defaults to 180 seconds, startup
waits are capped at 60 seconds, and image setup has a separate 30-minute deadline.
A deadline failure remains a failure to investigate. Test containers are removed
on completion, failure, timeout or keyboard interruption. Reports live in
`.compatibility-results/<lane>/`. Local commands share a lock; separate CI jobs
have their own VMs and run concurrently.

```sh
# Print the matrix without starting Docker:
python3 scripts/test-compatibility.py --list
# On a native x86-64 Docker host:
python3 scripts/test-compatibility.py baseline
python3 scripts/test-compatibility.py
# Reuse existing dependency images after changing tests or application code:
python3 scripts/test-compatibility.py baseline --skip-build
```

The compatibility runner requires a native x86-64 Docker host. Use CI on ARM
hosts. The standard development image continues to support native ARM64 with
the distribution's Blender.

Version sources: [NEURON releases](https://github.com/neuronsimulator/nrn/releases),
[Python 2 wheel policy](https://www.neuronsimulator.org/en/8.0.1/install/install_instructions.html),
[NEURON 8.0.2 wheels](https://pypi.org/project/neuron/8.0.2/#files),
and [Blender's official release archive](https://download.blender.org/release/).

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


## Saved group files

`group.to_file(path)` writes version 2 flat JSON so deeply nested cells can be
encoded and decoded safely. Regenerate group files when upgrading; legacy
transport formats are unsupported. Synapse files retain their existing format.

Read a saved group in either Blender or NEURON using the shared API:

```python
from blenderneuron.rootgroup import RootGroup

group = RootGroup.from_file(path)
# Inspect group["roots"] or apply the geometry to existing NEURON cells:
node.update_groups([group])
```

`from_file()` handles file reading and reconstructs the hierarchy. It returns
a dictionary; it does not create cells or display geometry. It is also inherited
by `BlenderRootGroup` and `NeuronRootGroup`. Application code must traverse deep
hierarchies iteratively. Use matching add-on versions in Blender and NEURON.

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

Blender 2.93 uses native cylindrical somas; spherical styling requires Blender 4+.
Its full suite exercises cylindrical geometry, editing, animation, rendering and
round trips. Coverage retains the 91% threshold for supported code; the sphere-only
module is measured by the Blender 4/5 lanes. Individual test output is streamed
to the CircleCI step console and also saved in each lane’s `tests.log` artifact.
