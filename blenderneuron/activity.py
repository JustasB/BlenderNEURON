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
        # Ensure times are a python list
        times = self.times if type(self.times) is list else list(self.times)

        # Trim value floats to 4 sig digits - using sci notation
        # Using more for display purposes is not necessary
        # Trimming helps with compression when sending values from NRN to Blender
        values = [float('%.3E' % v) for v in self.values]

        return {
            "times": times,
            "values": values,
        }

    def from_dict(self, source):
        self.times, self.values = source["times"], source["values"]

    def simplify(self, epsilon=0.0):
        if len(self.values) * len(self.times) == 0 or not numpy_available:
            return


        # Make a matrix where times and values are columns
        formatted = np.vstack((self.times, self.values)).T

        # Run simplification algorithm
        simplified = rdp(formatted, epsilon).T

        # Split the result matrix back to individual times and values columns
        self.times, self.values = simplified[0:2]


