from abc import ABCMeta

from blenderneuron.activity import Activity


class Section:
    __metaclass__ = ABCMeta

    def __init__(self):
        self.name = ""
        self.hash = ""

        self.point_count = 0
        self.coords = []
        self.radii = []
        self.segments_3D = []

        self.children = []
        self.parent_connection_loc = -1
        self.connection_end = -1

        self.activity = Activity()

    def to_dict(self):
        return {
            "name": self.name,
            "hash": self.hash,
            "point_count": self.point_count,
            "coords": self.coords,
            "radii": self.radii,
            "children": [child.to_dict() for child in self.children],
            "parent_connection_loc": self.parent_connection_loc,
            "connection_end": self.connection_end,
            "activity": self.activity.to_dict(),
            "segments_3D": [ seg.to_dict() for seg in self.segments_3D ]
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