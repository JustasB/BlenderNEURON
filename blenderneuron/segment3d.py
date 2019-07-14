from abc import ABCMeta

from blenderneuron.activity import Activity


class Segment3D:
    __metaclass__ = ABCMeta


    def __init__(self, section, point_index):
        self.section = section

        self.point_index = point_index
        self.name = section.name + "[" + str(point_index - 1) + "]"
        self.activity = Activity()

    def to_dict(self):
        result = {}

        result["point_index"] = self.point_index
        result["name"] = self.name
        result["activity"] = self.activity.to_dict()

        return result

    def from_dict(self, result):

        self.point_index = result["point_index"]
        self.name = result["name"]
        self.activity.from_dict(result["activity"])
