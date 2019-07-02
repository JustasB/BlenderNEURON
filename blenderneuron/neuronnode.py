from neuron import h
from blenderneuron.commnode import CommNode

class NeuronNode(CommNode):
    roots = []

    def __init__(self, *args, **kwargs):
        super(NeuronNode, self).__init__("NEURON", *args, **kwargs)

        self.server.register_function(self.get_root_section_names)

    def get_cell_data(self, root_ids, render_options):
        result = []

        for id in root_ids:
            root = self.roots[id]


    def get_root_section_names(self):
        self.roots = h.SectionList()
        self.roots.allroots()
        self.roots = list(self.roots)

        return [(i, sec.name()) for i, sec in enumerate(self.roots)]

