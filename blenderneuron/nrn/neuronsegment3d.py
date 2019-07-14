from blenderneuron.segment3d import Segment3D
from neuron import h

class NeuronSegment3D(Segment3D):
    def __init__(self, section, point_index):
        super(NeuronSegment3D, self).__init__(section, point_index)

        self.nrn_segment = self.get_nrn_segment()

    def collect(self, variable):
        value = getattr(self.nrn_segment, variable)

        self.activity.values.append(value)

    def get_nrn_segment(self):
        section = self.section.nrn_section
        i = self.point_index

        startL = h.arc3d(i - 1, sec=section)
        endL = h.arc3d(i, sec=section)
        segment_position =  (endL + startL) / 2.0 / section.L
        nrn_segment = section(segment_position)

        return nrn_segment