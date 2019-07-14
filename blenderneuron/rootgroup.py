from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from blenderneuron.activity import Activity

class RootGroup:
    __metaclass__ = ABCMeta

    def __init__(self):
        self.name = ""
        self.roots = OrderedDict()

        self.import_synapses = False
        self.interaction_granularity = 'Cell'

        self.record_activity = True
        self.recording_granularity = "Section"
        self.record_variable = "v"
        self.recording_period = 1.0

        self.activity = Activity()

    """
    Init options:
        within blender by selecting the root sections to include
        within neuron - by passing basic info about selected roots from blender

        update of a group within blender by getting full info from nrn 
    """

    def clear_activity(self):
        level = self.recording_granularity

        if level == '3D Segment':
            for root in self.roots.values():
                root.clear_3d_segment_activity()

        elif level == 'Section':
            for root in self.roots.values():
                root.clear_activity(recursive=True)

        elif level == 'root':
            for root in self.roots.values():
                root.clear_activity(recursive=False)

        else:
            self.activity.clear()

    def to_dict(self):
        return {
            "name": self.name,
            "roots": [root.to_dict() for root in self.roots.values()],
            "import_synapses": self.import_synapses,
            "interaction_granularity": self.interaction_granularity,
            "record_activity": self.record_activity,
            "recording_granularity": self.recording_granularity,
            "record_variable": self.record_variable,
            "recording_period": self.recording_period,
            "activity": self.activity.to_dict(),
        }



