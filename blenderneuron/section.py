from abc import ABCMeta

from blenderneuron.activity import Activity


class Section:
    __metaclass__ = ABCMeta

    def __init__(self):
        self.name = ""

        self.nseg = None
        self.point_count = 0
        self.coords = []
        self.radii = []
        self.segments_3D = []

        self.children = []
        self.parent_connection_loc = -1
        self.connection_end = -1

        self.activity = Activity()

    def __str__(self):
        return self.name

    def to_dict(self,
                include_activity=True,
                include_children=True,
                include_coords_and_radii=True):

        result = {
            "name": self.name,
            "parent_connection_loc": self.parent_connection_loc,
            "connection_end": self.connection_end,
        }

        if include_activity:
            result.update({
                "activity": self.activity.to_dict(),
                "segments_3D": [ seg.to_dict() for seg in self.segments_3D ]
            })

        if include_children:
            result.update({
                "children": [
                    child.to_dict(
                        include_activity,
                        include_children,
                        include_coords_and_radii
                    )
                    for child in self.children
                ]
            })

        if include_coords_and_radii:
            result.update({
                "nseg": self.nseg,
                "point_count": self.point_count,
                "coords": self.coords if type(self.coords) == list else self.coords.tolist(),
                "radii": self.radii if type(self.radii) == list else self.radii.tolist(),
            })

        return result

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