from blenderneuron.nrn.neuronsection import NeuronSection
from blenderneuron.rootgroup import RootGroup
from blenderneuron.activity import Activity
from neuron import h


class NeuronRootGroup(RootGroup):
    def from_updated_blender_group(self, blender_group):

        self.save_recording_params(blender_group)

        # Update selected roots and their children
        for blender_root in blender_group["roots"]:
            sec_name = self.node.rank_section_name(blender_root["name"])

            if sec_name is not None:
                section = self.roots[sec_name]
                section.from_updated_blender_root(blender_root)

    def from_skeletal_blender_group(self, blender_group, node):
        self.node = node
        self.name = blender_group['name']

        self.save_recording_params(blender_group)

        # Initialize selected roots and their children
        for blender_root in blender_group["roots"]:
            section = NeuronSection()
            section.from_skeletal_blender_root(blender_root, group=self)

            if section.name != '':
                self.roots[section.name] = section

        # Clear previously recorded activity on h.run()
        self.fih = h.FInitializeHandler(self.clear_activity)

        # Setup to collect activity during h.run()
        self.create_collector()

    def save_recording_params(self, blender_group):
        self.record_activity = blender_group["record_activity"]
        self.record_variable = blender_group["record_variable"]
        self.recording_granularity = blender_group["recording_granularity"]
        self.recording_period = blender_group["recording_period"]
        self.recording_time_start = blender_group["recording_time_start"]
        self.recording_time_end = blender_group["recording_time_end"]

    def create_collector(self):
        """
        Greates a pair of NetStim and NetCon which trigger an event to recursively collect the activity of the group
        segments. This method does nothing if group.record_activity is False
        """

        if self.record_activity:
            collector_stim = h.NetStim(0.5)
            collector_stim.start = self.recording_time_start
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

        time = h.t

        if time < self.recording_time_start or \
                (self.recording_time_end != 0 and time > self.recording_time_end):
            return

        self.activity.times.append(time)

        level = self.recording_granularity

        # Recursively record from every segment of each section of each cell
        if level == '3D Segment':
            for root in self.roots.values():
                root.collect_segments_recursive()

        # Recursively record from the middle of each section of each cell
        elif level == 'Section':
            for root in self.roots.values():
                root.collect(recursive=True)

        # Record from the middle of somas of each cell
        elif level == 'Cell':
            for root in self.roots.values():
                root.collect(recursive=False)

        # Record from the somas of each cell and compute their mean
        else:
            variable = self.record_variable

            # Compute the mean of group cell somas
            value = 0.0
            for root in self.roots.values():
                value += getattr(root(0.5), variable)
            value = value / len(self.roots)

            self.activity.values.append(value)
