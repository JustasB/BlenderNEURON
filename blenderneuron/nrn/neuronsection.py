from blenderneuron.section import Section
from neuron import h
import numpy as np

class NeuronSection(Section):

    def from_updated_blender_root(self, blender_section):

        self.update_coords_and_radii(blender_section)
        self.segments_3D = []

        for i, blender_child in enumerate(blender_section["children"]):
            section = self.children[i]

            section.from_updated_blender_root(blender_child)


    def from_skeletal_blender_root(self, source_section, group):
        try:
            sec_name = group.node.rank_section_name(source_section["name"])

            if sec_name is not None:
                self.from_nrn_section(group.node.section_index[sec_name], group)
        except KeyError:
            raise Exception("Could not find section: " + sec_name + " loaded in NEURON")



    def from_nrn_section(self, nrn_section, group):
        self.group = group
        self.nrn_section = nrn_section

        self.name = nrn_section.name()

        for nrn_child_sec in nrn_section.children():
            child = NeuronSection()
            child.from_nrn_section(nrn_child_sec, group)
            self.children.append(child)

        self.get_coords_and_radii()

        parent_seg = nrn_section.parentseg()
        self.parent_connection_loc = parent_seg.x if parent_seg is not None else None
        self.connection_end = nrn_section.orientation()

        self.segments_3D = []

    def update_coords_and_radii(self, blender_section):
        self.nseg = blender_section["nseg"]
        self.point_count = blender_section["point_count"]
        self.coords = blender_section["coords"]
        self.radii = blender_section["radii"]

        nrn_section = self.nrn_section

        # Use 3D points as the L and diam sources
        h.pt3dconst(1,sec=nrn_section)

        # Clear the existing points - and allocate room for the incoming points
        h.pt3dclear(self.point_count, sec=nrn_section)

        # Use vectorization to add the points to section
        coords = np.array(self.coords).reshape((-1, 3))
        diams = np.array(self.radii) * 2.0

        xvec = h.Vector(coords[:,0])
        yvec = h.Vector(coords[:,1])
        zvec = h.Vector(coords[:,2])
        dvec = h.Vector(diams)

        h.pt3dadd(xvec, yvec, zvec, dvec, sec=nrn_section)

    def get_coords_and_radii(self):

        nrn_section = self.nrn_section

        # Count 3D points
        point_count = int(h.n3d(sec=nrn_section))

        # Let NEURON create them if missing
        if point_count == 0:
            h.define_shape(sec=self.nrn_section)
            point_count = int(h.n3d(sec=self.nrn_section))

        # Collect the coordinates
        coords = [None] * point_count * 3 # 3 for xy and z
        radii = [None] * point_count

        for c in range(point_count):
            ci = c * 3
            coords[ci]     = h.x3d(c, sec=nrn_section)
            coords[ci + 1] = h.y3d(c, sec=nrn_section)
            coords[ci + 2] = h.z3d(c, sec=nrn_section)

            radii[c] = h.diam3d(c, sec=nrn_section) / 2.0

        self.nseg = int(nrn_section.nseg)
        self.point_count = point_count
        self.coords = coords
        self.radii = radii

    def collect_segments_recursive(self):
        """
        Recursively collects the values of segments of a root section. Segments are given sequential 0-based
        names similar to NEURON cells and sections. For example, TestCell[0].dend[3][4] refers to first TestCell, 4th
        dendrite, 5th segment. Segment order is determined by the order in which they appear in NEURON's xyz3d() function.

        :return: None
        """

        for seg in self.segments_3D:
            seg.collect(self.group.record_variable)

        for child in self.children():
            child.collect_segments_recursive()

    def collect(self, recursive=True):
        """
        Recursively collects the section midpoint values of a group's collect_variable (e.g. 'v')

        :param recursive: Whether to collect child section values (otherwise stop at root/soma)
        :return: None
        """

        value = getattr(self.nrn_section(0.5), self.group.record_variable)
        self.activity.values.append(value)

        if recursive:
            for child in self.children:
                child.collect(recursive=True)