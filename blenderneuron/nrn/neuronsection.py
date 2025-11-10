from blenderneuron.section import Section
from neuron import h
import numpy as np


class NeuronSection(Section):

    def from_updated_blender_root(self, blender_section):
        """
        Update the coordinates and radii from the updated blender_section, iteratively for all child sections.

        :param blender_section: The updated blender section data
        :return: None
        """

        stack = [(self, blender_section)]
        while stack:
            node, b_section = stack.pop()
            node.update_coords_and_radii(b_section)

            for i, blender_child in enumerate(b_section["children"]):
                section = node.children[i]
                # Add child section and its corresponding blender_child to the stack
                stack.append((section, blender_child))

    def from_skeletal_blender_root(self, source_section, group):
        try:
            sec_name = group.node.rank_section_name(source_section["name"])

            if sec_name is not None:
                self.from_nrn_section(group.node.section_index[sec_name], group)
        except KeyError:
            raise Exception("Could not find section: " + sec_name + " loaded in NEURON")

    def from_nrn_section(self, nrn_section, group):
        """
        Iteratively initializes the NeuronSection instances from NEURON sections, maintaining the original structure.

        :param nrn_section: The NEURON section to initialize from
        :param group: The group to which the sections belong
        :return: None
        """

        stack = [(self, nrn_section, False)]
        while stack:
            node, nrn_sec, visited = stack.pop()
            if visited:
                # Code to run after processing all children
                node.get_coords_and_radii()

                parent_seg = nrn_sec.parentseg()
                node.parent_connection_loc = parent_seg.x if parent_seg is not None else None
                node.connection_end = nrn_sec.orientation()

            else:
                # Initial processing of the node
                node.group = group
                node.nrn_section = nrn_sec
                node.name = nrn_sec.name()

                # Mark the node as visited and process children
                stack.append((node, nrn_sec, True))
                for nrn_child_sec in nrn_sec.children():
                    child = NeuronSection()
                    node.children.append(child)
                    stack.append((child, nrn_child_sec, False))

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

        stack = [self]

        while stack:
            node = stack.pop()
            nrn_sec = node.nrn_section
            record_var = node.group.record_variable

            # Number of 3D points that define the section
            npts = int(h.n3d(sec=nrn_sec))

            # Skip degenerate sections
            if npts < 2:
                stack.extend(reversed(list(nrn_sec.children())))
                continue

            # Collect per-3D segment activity
            for i in range(1, npts):
                seg_index = i - 1
                if seg_index not in node.segment_activity:
                    node.segment_activity[seg_index] = Activity()

                startL = h.arc3d(i - 1, sec=nrn_sec)
                endL = h.arc3d(i, sec=nrn_sec)

                if nrn_sec.L == 0:
                    continue  # degenerate geometry

                x_mid = (startL + endL) / (2.0 * nrn_sec.L)
                x_mid = min(max(x_mid, 0.0), 1.0)  # clamp to [0,1]
                value = getattr(nrn_sec(x_mid), record_var)

                node.segment_activity[seg_index].values.append(value)

            # Traverse child sections
            stack.extend(reversed(list(nrn_sec.children())))

    def collect(self, recursive=True):
        """
        Recursively collects the section midpoint values of a group's collect_variable (e.g. 'v')

        :param recursive: Whether to collect child section values (otherwise stop at root/soma)
        :return: None
        """

        stack = [self]
        while stack:
            node = stack.pop()
            value = getattr(node.nrn_section(0.5), node.group.record_variable)
            node.activity.values.append(value)
            if recursive:
                # Add children to stack in reverse order to maintain traversal order
                stack.extend(reversed(node.children))
