from blenderneuron.section import Section
from blenderneuron.blender.blendersegment3d import BlenderSegment3D
import numpy as np
import math
import numpy as np


class BlenderSection(Section):

    def __init__(self):
        super(BlenderSection, self).__init__()

        self.was_split = False
        self.split_sections = []


    def from_full_NEURON_section_dict(self, nrn_section_dict):
        self.hash = nrn_section_dict["hash"]
        self.name = nrn_section_dict["name"]

        self.point_count = nrn_section_dict["point_count"]
        self.coords = nrn_section_dict["coords"]
        self.radii = nrn_section_dict["radii"]
        self.parent_connection_loc = nrn_section_dict["parent_connection_loc"]
        self.connection_end = nrn_section_dict["connection_end"]

        # Parse the children
        self.children = []
        for nrn_child in nrn_section_dict["children"]:
            child = BlenderSection()
            child.from_full_NEURON_section_dict(nrn_child)
            self.children.append(child)

        self.segments_3D = []

        if "segments_3D" in nrn_section_dict:
            for i, nrn_seg_3D in enumerate(nrn_section_dict["segments_3D"]):
                seg = BlenderSegment3D(self, i+1)
                seg.from_dict(nrn_seg_3D)
                self.segments_3D.append(seg)

        if "activity" in nrn_section_dict:
            self.activity.from_dict(nrn_section_dict["activity"])

    def make_split_sections(self, max_length):
        """
        Splits a section into smaller chained sub-sections if the arc length of the points
        exceeds the specified length. This is used to temporarily split the sections for
        physics simulations.

        :param max_length: maximum allowed section length in um
        :return: None
        """
        arc_lengths = self.arc_lengths()
        total_length = arc_lengths[-1]
        num_sections = math.ceil(total_length / max_length)
        is_too_long = num_sections > 1

        if not is_too_long:
            return None

        # Mark the the section as having been split
        self.was_split = True

        # Get the maximum length of the new sections
        new_length = total_length / num_sections

        # Create new sections
        self.split_sections = [BlenderSection() for i in range(num_sections)]

        old_coords = np.array(self.coords).reshape((-1, 3))
        old_radii = np.array(self.radii)

        # Split the coords and radii
        split_length = new_length
        split_idxs = []

        for pi in range(len(old_radii)):
            if arc_lengths[pi] >= split_length:
                split_idxs.append(pi)
                split_length += new_length

                if len(split_idxs) == num_sections-1:
                    break

        split_coords = np.split(old_coords, split_idxs)
        split_radii = np.split(old_radii, split_idxs)

        # Assign them to the split sections
        for i, sec in enumerate(self.split_sections):
            sec.coords = split_coords[i].reshape(-1)
            sec.radii = split_radii[i]
            sec.point_count = len(sec.radii)

            sec.name = self.name + "["+str(i)+"]"
            sec.hash = hash(sec)

        # Total number of points should be preserved
        assert self.point_count == sum(len(sec.radii) for sec in self.split_sections)

        return self.split_sections

    def update_coords_from_split_sections(self):
        if not self.was_split:
            return

        # Reassemble the coords and radii
        coords = np.concatenate([sec.coords for sec in self.split_sections])
        radii = np.concatenate([sec.radii for sec in self.split_sections])

        self.coords = coords.reshape(-1)
        self.radii = radii.reshape(-1)

        # This should not change
        assert self.point_count == len(self.radii)

    def arc_lengths(self):
        coords = np.array(self.coords).reshape(-1, 3)
        start = coords[0:-1]
        end = coords[1:]
        diff = end - start
        sq = np.square(diff)
        sum = np.sum(sq, axis=1)
        dist = np.sqrt(sum)
        tot_len = np.concatenate(([0],np.cumsum(dist)))
        return tot_len

    def dist_to_closest_coord(self, target):
        coords = np.array(self.coords).reshape(-1, 3)
        target = np.array(target).reshape((1, 3))

        diff = coords - target
        sq = np.square(diff)
        sum = np.sum(sq, axis=1)
        dists = np.sqrt(sum)

        return np.min(dists)

    def remove_split_sections(self, recursive=True):
        if self.was_split:
            self.split_sections = []
            self.was_split = False

        if recursive:
            for child_sec in self.children:
                child_sec.remove_split_sections(recursive=True)

class BlenderRoot(BlenderSection):

    def __init__(self, index, hash, name, group=None):
        super(BlenderRoot, self).__init__()

        self.index = index
        self.hash = hash
        self.name = name
        self.group = group

    @property
    def ui_root(self):
        return self.group.ui_group.root_entries[self.name]

    def remove(self, node):
        # Remove view container objects if any
        if self.group is not None and self.group.view is not None:
            self.group.view.remove_container(self.hash)

        # remove from UI and from node groups
        self.remove_from_group(delete=True)

        # remove from index
        node.root_index.pop(self.hash)

    def remove_from_group(self, delete=False):
        if self.group is None:
            return

        # Keep a reference to group
        current_group = self.group

        # Remove group from 3D view
        if self.group.view is not None:
            self.group.view.remove()
            self.group.view = None

        # Set group to none in the root_index
        self.group = None

        # remove from node group
        current_group.roots.pop(self.hash)

        # from ui group
        root_entry = current_group.ui_group.root_entries.get(self.name)

        if root_entry is not None and root_entry.selected:
            root_entry.selected = False

        if delete:
            # Remove the root entry from all the UI groups
            for group in current_group.node.groups.values():
                entries = group.ui_group.root_entries
                ui_root = entries.get(self.name)

                if ui_root is not None:
                    remove_idx = entries.find(self.name)
                    entries.remove(remove_idx)

    def add_to_UI_group(self, ui_group):
        ui_root = ui_group.root_entries.add()

        ui_root.index = self.index
        ui_root.hash = self.hash
        ui_root.name = self.name

        return ui_root

    def add_to_group(self, group):
        if self.group == group:
            return

        if self.group is not None:
            self.remove_from_group()

        # index
        self.group = group

        if group is None:
            return

        # node group
        self.group.roots[self.hash] = self

        # ui
        root_entry = self.group.ui_group.root_entries.get(self.name)

        # If not on the list of cells (e.g. when newly added in NRN)
        if root_entry is None:
            root_entry = self.add_to_UI_group(self.group.ui_group)

        if root_entry is not None and not root_entry.selected:
            root_entry.selected = True