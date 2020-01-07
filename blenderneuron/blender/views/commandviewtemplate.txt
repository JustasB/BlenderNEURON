
from neuron import h

class Transform[CELL_NAME]:
    def __init__(self):

        # Create a section lookup by section name
        # Note: this assumes each section has a unique name
        self.name2section = { sec.name(): sec for sec in h.allsec() }

        # This will store the new section coordinates
        self.section_coords = { }

    def set_coords(self, sec_name):
        # Lookup the section
        nrn_section = self.name2section[sec_name]

        # Lookup its new coords
        new_coords = self.section_coords[sec_name]

        # Use 3D points as section L and diam sources
        h.pt3dconst(1, sec=nrn_section)

        # Clear the existing points - and allocate room for the incoming points
        h.pt3dclear(len(new_coords["diam"]), sec=nrn_section)

        # Use vectorization to add the points to section
        xvec = h.Vector(new_coords["x"])
        yvec = h.Vector(new_coords["y"])
        zvec = h.Vector(new_coords["z"])
        dvec = h.Vector(new_coords["diam"])

        h.pt3dadd(xvec, yvec, zvec, dvec, sec=nrn_section)

    def set_all(self):
        for sec_name in self.section_coords.keys():
            self.set_coords(sec_name)

    @staticmethod
    def apply_on(prefix):
        t = Transform[CELL_NAME]()
        t.define_coords(prefix)
        t.set_all()

    @staticmethod
    def apply():
        t = Transform[CELL_NAME]()
        t.define_coords()
        t.set_all()

    def define_coords(self, prefix = '[DEFAULT_PREFIX]'):
        if prefix != '':
            prefix += '.'

        self.section_coords = {
[SECTION_COORDS]
        }
