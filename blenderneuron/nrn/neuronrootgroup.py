from blenderneuron.nrn.neuronsection import NeuronSection
from blenderneuron.rootgroup import RootGroup
from blenderneuron.activity import Activity
from neuron import h
import weakref
from blenderneuron.nrn.recording import VectorRecorder


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

        # Set up activity collection for the next simulation.
        self.create_collector()

    def prepare_activity(self, queue_cleared=False):
        """Clear traces and refresh geometry before the first sample of a run.

        Rebuilding also captures direct NEURON pt3d edits between runs. Direct
        pt3d edits during collection require an explicit cache rebuild; Blender
        coordinate updates invalidate the affected sections automatically.
        """
        self.clear_activity(queue_cleared)
        if self.record_activity and self.recording_granularity == '3D Segment':
            for root in self.roots.values():
                root.rebuild_segment_midpoints_recursive()

    def save_recording_params(self, blender_group):
        self.clear_activity()
        self.record_activity = blender_group["record_activity"]
        self.record_variable = blender_group["record_variable"]
        self.recording_granularity = blender_group["recording_granularity"]
        self.recording_period = blender_group["recording_period"]
        self.recording_time_start = blender_group["recording_time_start"]
        self.recording_time_end = blender_group["recording_time_end"]

    def clear_activity(self, queue_cleared=False):
        recorder = getattr(self, '_recorder', None)
        if recorder is not None:
            recorder.close(queue_cleared)
            self._recorder = None
        RootGroup.clear_activity(self)

    def close(self):
        """Detach owned recordings and initialization callbacks."""
        self.clear_activity()
        self.fih = None
        self.recording_fih = None

    def _initialize_recording(self):
        self.prepare_activity(queue_cleared=True)
        if self.record_activity and self.roots:
            try:
                self._recorder = VectorRecorder(self)
            except Exception:
                self.clear_activity()
                raise

    def create_collector(self):
        """Install weak initialization hooks; rebuild native vectors each run."""
        self.close()
        group_ref = weakref.ref(self)

        def initialize():
            group = group_ref()
            if group is not None:
                group._initialize_recording()

        def schedule():
            group = group_ref()
            if group is not None and getattr(group, '_recorder', None) is not None:
                group._recorder.schedule_extension()

        self.fih = h.FInitializeHandler(1, initialize)
        self.recording_fih = h.FInitializeHandler(2, schedule)

    def collect(self):
        """
        Based on the group's color level, gathers the values of the group's collect_variable. This method is called
        at regular times during the simulation.

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
                root.collect(recursive=True) # already-iterative

        # Record from the middle of somas of each cell
        elif level == 'Cell':
            for root in self.roots.values():
                root.collect(recursive=False) # already-iterative

        # Record from the somas of each cell and compute their mean
        else:
            variable = self.record_variable

            # Compute the mean of group cell somas
            value = 0.0
            for root in self.roots.values():
                value += getattr(root(0.5), variable)
            value = value / len(self.roots)

            self.activity.values.append(value)
