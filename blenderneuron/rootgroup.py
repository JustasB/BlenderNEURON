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

        self.record_activity = False
        self.recording_granularity = 'Cell'
        self.record_variable = "v"
        self.recording_period = 1.0
        self.recording_time_start = 0
        self.recording_time_end = 0

        self.activity = Activity()

    def __str__(self):
        return self.name

    def clear_activity(self):
        # Clear group level activity
        self.activity.clear()

        # Cell and section level activity
        for root in self.roots.values():
            root.clear_activity(recursive=True)

        # Segment level
        for root in self.roots.values():
            root.clear_3d_segment_activity()


    def to_dict(self,
                include_activity=False,
                include_root_children=False,
                include_coords_and_radii=False):
        """

        :param include_activity:
        :param include_root_children:
        :param include_coords_and_radii:
        :return:
        """
        result = {
            "name": self.name,
            "roots": [root.to_dict(include_activity, include_root_children, include_coords_and_radii) for root in self.roots.values()],
            "import_synapses": self.import_synapses,
            "interaction_granularity": self.interaction_granularity,
            "record_activity": self.record_activity,
            "recording_granularity": self.recording_granularity,
            "record_variable": self.record_variable,
            "recording_period": self.recording_period,
            "recording_time_start": self.recording_time_start,
            "recording_time_end": self.recording_time_end,
        }

        if include_activity:
            result.update({
                "activity": self.activity.to_dict(),
            })

        return result

