"""Three independent branching cells, served live to Blender (no NEURON GUI)."""
import os
import time
from pathlib import Path

from neuron import h
from blenderneuron.nrn.neuronnode import NeuronNode

# Load NEURON's standard run controls. These define h.run(), h.tstop and
# initialization; importing neuron.gui would be unnecessary in this example.
h.load_file('stdrun.hoc')
h.dt = 0.025
h.tstop = 30
h.v_init = -65

# Keep sections and clamps alive for the entire Blender session.
cells, stimuli = [], []
# Place the somas side by side in XY; the Blender camera looks down the Z axis.
# Explicit 3D points give Blender both the section shapes and their positions.
for index in range(3):
    x = (index - 1) * 100
    soma = h.Section(name='cell%d_soma' % (index + 1))
    h.pt3dadd(x, -10, 0, 20, sec=soma)
    h.pt3dadd(x, 10, 0, 20, sec=soma)
    sections = [soma]
    for branch, dx in enumerate((-32, 32)):
        dendrite = h.Section(name='cell%d_dend%d' % (index + 1, branch + 1))
        dendrite.connect(soma(1))
        h.pt3dadd(x, 10, 0, 3, sec=dendrite)
        h.pt3dadd(x + dx, 65, 0, 2, sec=dendrite)
        dendrite.nseg = 5
        sections.append(dendrite)
    # Built-in Hodgkin–Huxley channels require no custom mechanism compilation.
    # Both branches conduct voltage, so section-level recording shows activity
    # throughout each cell rather than coloring only its soma.
    for section in sections:
        section.Ra = 100
        section.cm = 1
        section.insert('hh')
    # Stagger otherwise identical inputs to make the three responses easy to
    # distinguish in the movie. Delay/duration are ms; amplitude is nA.
    stimulus = h.IClamp(soma(0.5))
    stimulus.delay, stimulus.dur, stimulus.amp = 5 + index * 7, 1, 1
    cells.append(sections)
    stimuli.append(stimulus)

# Publish the live NEURON endpoint after the model is ready. The node services
# incoming Blender requests while this process keeps the model objects alive.
node = NeuronNode()
try:
    (Path(os.environ['BLENDERNEURON_CONFIG_DIR']) / 'model-ready').touch()
    while True:
        time.sleep(0.05)
finally:
    node.stop_server()
