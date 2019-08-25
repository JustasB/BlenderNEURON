try:
    import numpy as np
    numpy_available = True

    from blenderneuron.blender.utils import rdp
except:
    numpy_available = False

class Activity:

    def __init__(self):
        self.times = []
        self.values = []

    def clear(self):
        self.times = []
        self.values = []

    def to_dict(self):
        return {
            "times": self.times if type(self.times) is list else list(self.times),
            "values": self.values if type(self.values) is list else list(self.values),
        }

    def from_dict(self, source):
        self.times, self.values = source["times"], source["values"]

    def simplify(self, epsilon=0.0):
        if not numpy_available:
            return

        try:
            # Make a matrix where times and values are columns
            formatted = np.vstack((self.times, self.values)).T

            # Run simplification algorithm
            simplified = rdp(formatted, epsilon).T

            # Split the result back to individual times and values columns
            self.times, self.values = simplified[0:2]
        except:

            import pydevd
            pydevd.settrace('192.168.0.100', port=4200)
            raise

