from blenderneuron.nrn.neuronnode import NeuronNode

BlenderNEURON = globals()["BlenderNEURON"] = NeuronNode()

print(f'BlenderNEURON running in NEURON and accessible by Blender with BlenderNEURON addon at: {BlenderNEURON.server_address}')
