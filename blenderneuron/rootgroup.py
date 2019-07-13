from abc import ABCMeta, abstractmethod


class Activity:
    times = []
    values = []

    def clear(self):
        self.times = []
        self.values = []

    def to_dict(self):
        return {
            "times": self.times,
            "values": self.values,
        }

class RootGroup:
    __metaclass__ = ABCMeta

    name = ""
    roots = []

    import_synapses = False
    interaction_granularity = 'Cell'

    record_activity = True
    recording_granularity = "Section"
    record_variable = "v"
    recording_period = 1.0

    activity = Activity()

    """
    Init options:
        within blender by selecting the root sections to include
        within neuron - by passing basic info about selected roots from blender

        update of a group within blender by getting full info from nrn 
    """

    def clear_activity(self):
        level = self.recording_granularity

        if level == '3D Segment':
            for root in self.roots:
                root.clear_3d_segment_activity()

        elif level == 'Section':
            for root in self.roots:
                root.clear_activity(recursive=True)

        elif level == 'root':
            for root in self.roots:
                root.clear_activity(recursive=False)

        else:
            self.activity.clear()

    @abstractmethod
    def to_dict(self):
        pass



class Section:
    __metaclass__ = ABCMeta

    name = ""
    hash = ""

    point_count = 0
    coords = []
    radii = []
    segments_3D = []

    children = []
    parent_connection_loc = -1
    connection_end = -1

    activity = Activity()

    def to_dict(self):
        return {
            "name": self.name,
            "hash": self.hash,
            "coords": self.coords,
            "radii": self.radii,
            "children": [child.to_dict() for child in self.children],
            "parent_connection_loc": self.parent_connection_loc,
            "connection_end": self.connection_end,
            "activity": self.activity.to_dict(),
            "segment_3d_activity": [ seg.activity.to_dict() for seg in self.segments_3D ]
        }

    def clear_3d_segment_activity(self):
        for seg in self.segments_3D:
            seg.activity.clear()

        for child in self.children:
            child.clear_3d_segment_activity()

    def clear_activity(self, recursive):
        self.activity.clear()

        if recursive:
            for child in self.children:
                child.clear_activity(recursive=True)


class Segment3D:
    __metaclass__ = ABCMeta

    section = None
    activity = Activity()
    point_index = -1

    def __init__(self, section, point_index):
        self.section = section
        self.point_index = point_index

