class Activity:

    def __init__(self):
        self.times = []
        self.values = []

    def clear(self):
        self.times = []
        self.values = []

    def to_dict(self):
        return {
            "times": self.times,
            "values": self.values,
        }

    def from_dict(self, source):
        self.times = source["times"]
        self.values = source["values"]