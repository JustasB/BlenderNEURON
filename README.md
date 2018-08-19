# BlenderNEURON

A Python package and an addon that takes a NEURON simulator model and exports its 3D structure and membrane activity to Blender. The export can be peformed via NEURON GUI or via Python commands.

## NEURON GUI
![NEURON GUI](images/NEURON.JPG)
The tool is integrated with NEURON to provide a simple user interface and a set of Python commands that can be used to visualize and inspect single cell or network morphology and activity.

## Example Cells and Activity

| ![l5pyr](images/l5pyr.gif)       | ![hipca1](images/hipca1pyr.gif)  |
|----------------------------------|----------------------------------|
| Neocortex Layer 5 Pyramidal Cell | Hippocampus CA1 Pyramidal Cell   |
| ![purk](images/purk.gif)         | ![l5basket](images/l5basket.gif) |
| Cerebellum Purkinje Cell         | Neocortex Layer 5 Basket Cell    |

## Example Networks
Example visualizations of an olfactory bulb model (Migliore et. al. 2014).

![60MCs](images/60MCs.gif)
A network of about 60 mitral cells

![5MCs](images/5MCs.gif)
3D structure and activity of a 5 mitral cell network and several accompanying granule cells

![1MCs](images/1MCwGCs.gif)
Activity of 1 mitral cell with several hundred companion granule cells


## Blender GUI:
![Blender GUI](images/Blender.jpg)

## Installation

BlenderNEURON installation is a simple two part process which enables communication between NEURON and Blender. Part 1 has both HOC (NEURON default) or Python versions. Both have identical functionality.

**Part 1: HOC NEURON Client**
 1. Install [NEURON](https://neuron.yale.edu/neuron)
 2. [Download the HOC version](https://github.com/JustasB/BlenderNEURON/releases) 
 3. Extract the zip file and open the BlenderNEURON.hoc file using NEURON. You should see the BlenderNEURON interface.

**Part 1: Python NEURON Client**

 1. Install [NEURON](https://neuron.yale.edu/neuron)
 2. Using the same Python environment as NEURON, use the [`pip install blenderneuron`](https://pypi.org/project/blenderneuron/) command to install the BlenderNEURON client library
 3. Start NEURON+Python, and type `from blenderneuron.quick import bn` to load the BlenderNEURON interface

![NEURON GUI](images/NEURON.JPG)

**Part 2: Blender Addon Server**
 1. Install and open [Blender](https://www.blender.org/download/)
 2. Download the [BlenderNEURON addon](https://github.com/JustasB/BlenderNEURON/releases)
 3. In Blender, click File > User Preferences > Add-ons (tab) > Install Add-on From File > Point to the addon .zip file
 4. Tick the checkbox next to 'Import-Export: NEURON Blender Interface' to load the addon. Then click "Save User Settings".
 5. If you see a NEURON tab on the left side of the screen, the addon has been loaded succesfully.


