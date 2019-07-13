from blenderneuron.rootgroup import RootGroup, Section, Segment3D


class NeuronRootGroup(RootGroup):

    def __init__(self, blender_group, node):
        self.record_activity = blender_group["record_activity"]
        self.name = blender_group['name']
        self.activity = Activity()
        self.roots = [NeuronSection(root, self) for root in blender_group["roots"]]
        self.record_variable = blender_group["record_variable"]
        self.recording_granularity = blender_group["recording_granularity"]
        self.node = node
        self.recording_period = blender_group["recording_period"]

        # Clear previously recorded activity on h.run()
        self.fih = h.FInitializeHandler(self.clear_activity)

        # Setup to collect activity during h.run()
        self.create_collector()

    def create_collector(self):
        """
        Greates a pair of NetStim and NetCon which trigger an event to recursively collect the activity of the group
        segments. This method does nothing if group.record_activity is False
        """

        if self.record_activity:
            collector_stim = h.NetStim(0.5)
            collector_stim.start = 0
            collector_stim.interval = self.recording_period
            collector_stim.number = 1e9
            collector_stim.noise = 0

            collector_con = h.NetCon(collector_stim, None)
            collector_con.record((self.collect))

            self.collector_stim = collector_stim
            self.collector_con = collector_con

    def collect(self):
        """
        Based on the group's color level, gathers the values of the group's collect_variable. This method is called
        at regular times during the simulation. See :any:`create_cell_group()` for details.

        :return: None
        """

        self.activity.times.append(h.t)

        level = self.recording_granularity

        # Recursively record from every segment of each section of each cell
        if level == '3D Segment':
            for root in self.roots:
                root.collect_segments_recursive()

        # Recursively record from the middle of each section of each cell
        elif level == 'Section':
            for root in self.roots:
                root.collect(recursive=True)

        # Record from the middle of somas of each cell
        elif level == 'Cell':
            for root in self.roots:
                root.collect(recursive=False)

        # Record from the somas of each cell and compute their mean
        else:
            variable = self.record_variable

            # Compute the mean of group cell somas
            value = 0.0
            for root in self.roots:
                value += getattr(root(0.5), variable)
            value = value / len(self.roots)

            self.activity.values.append(value)

    def to_dict(self):
        return {
            "name": self.name,
            "activity": self.activity.to_dict(),
            "roots": [root.to_dict() for root in self.roots]
        }

class NeuronSection(Section):

    """
    COuld be initialized from blender hash - root section hash
    Or a child section of a root

    Could also be updated from blender with new coords
    """
    def __init__(self, source_section, group):
        self.group = group
        self.activity = Activity()

        from_blender = type(source_section) is dict

        if from_blender:
            self.hash = source_section["hash"]
            self.nrn_section = nrn_section = group.node.section_index[self.hash]
        else:
            self.hash = hash(source_section)
            self.nrn_section = nrn_section = source_section

        self.name = nrn_section.name()
        self.children = [NeuronSection(sec, group) for sec in nrn_section.children()]

        self.get_coords_and_radii()

        parent_seg = nrn_section.parentseg()
        self.connection_end = nrn_section.orientation()
        self.parent_connection_loc = parent_seg.x if parent_seg is not None else None

        if group.recording_granularity == '3D Segment':
            self.segments_3D = [NeuronSegment3D(self, i) for i in range(1, self.point_count)]
        else:
            self.segments_3D = []

    def get_coords_and_radii(self):

        nrn_section = self.nrn_section

        # Count 3D points
        point_count = int(h.n3d(sec=nrn_section))

        # Let NEURON create them if missing
        if coord_count == 0:
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


class NeuronSegment3D(Segment3D):
    def __init__(self, section, point_index):
        super(NeuronSegment3D, self).__init__(section, point_index)

        self.name = section.nrn_section.name() + "[" + str(point_index - 1) + "]"
        self.nrn_segment = self.get_nrn_segment()

    def collect(self, variable):
        value = getattr(self.nrn_segment, variable)
        self.activity.values.append(value)

    def get_nrn_segment(self):
        section = self.section.nrn_section
        i = self.point_index

        startL = h.arc3d(i - 1, sec=section)
        endL = h.arc3d(i, sec=section)
        segment_position =  (endL + startL) / 2.0 / section.L
        nrn_segment = section(segment_position)

        return nrn_segment
