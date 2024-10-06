from blenderneuron.section import Section
import numpy as np
import math
import numpy as np


class BlenderSection(Section):

    def __init__(self):
        super(BlenderSection, self).__init__()

        self.was_split = False
        self.split_sections = []

    def from_full_NEURON_section_dict(self, nrn_section_dict):
        """
        Iteratively initializes the BlenderSection instances from NEURON section dictionaries,
        maintaining the original structure.

        :param nrn_section_dict: The dictionary containing NEURON section data.
        :return: None
        """

        # Initialize a stack with tuples: (current_node, current_dict, state)
        # state can be 'pre' or 'post' to represent pre-processing and post-processing
        stack = [(self, nrn_section_dict, 'pre')]

        while stack:
            current_node, current_dict, state = stack.pop()

            if state == 'pre':
                # Pre-processing: set attributes from the dictionary
                current_node.name = current_dict["name"]
                current_node.nseg = current_dict["nseg"]
                current_node.point_count = current_dict["point_count"]
                current_node.coords = current_dict["coords"]
                current_node.radii = current_dict["radii"]
                current_node.parent_connection_loc = current_dict["parent_connection_loc"]
                current_node.connection_end = current_dict["connection_end"]

                # Initialize the children list
                current_node.children = []

                # Push post-processing onto the stack
                stack.append((current_node, current_dict, 'post'))

                # Process children by adding them to the stack in 'pre' state
                # Reverse the children to maintain the original order
                for nrn_child_dict in reversed(current_dict["children"]):
                    child = BlenderSection()
                    # Instead of appending to children here, we'll do it in post-processing
                    # Store parent reference in child for later use
                    child._parent_node = current_node
                    # Push child onto the stack for pre-processing
                    stack.append((child, nrn_child_dict, 'pre'))
            elif state == 'post':
                # Post-processing: after children have been processed
                current_node.segments_3D = []

                if "activity" in current_dict:
                    current_node.activity.from_dict(current_dict["activity"])

                # If the current node has a parent, append it to the parent's children list
                if hasattr(current_node, '_parent_node'):
                    parent_node = current_node._parent_node
                    parent_node.children.append(current_node)
                    # Clean up temporary attributes
                    del current_node._parent_node

    def make_split_sections(self, max_length):
        """
        Splits a section into smaller chained sub-sections if the arc length of the points
        exceeds the specified length. This is used to temporarily split the sections for
        confining dendrites between layers.

        :param max_length: maximum allowed section length in um
        :return: None
        """
        arc_lengths = self.arc_lengths()
        total_length = arc_lengths[-1]
        num_sections = int(math.ceil(total_length / max_length))
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
        split_length = 0
        point_i = 0

        for split_sec_i, split_sec in enumerate(self.split_sections):
            split_length += new_length
            split_sec_coords = []
            split_sec_radii = []

            # Start a 2nd+ split section with the most recent point
            if split_sec_i > 0:
                prev_sec = self.split_sections[split_sec_i-1]
                split_sec_coords.append(prev_sec.coords[-1])
                split_sec_radii.append(prev_sec.radii[-1])

            exact_length_match = False

            # Add 3d points to the split until reached the end of the split
            while arc_lengths[point_i] <= split_length:
                split_sec_coords.append(old_coords[point_i])
                split_sec_radii.append(old_radii[point_i])

                exact_length_match = abs(arc_lengths[point_i] - split_length) < 0.001
                point_i += 1

                if point_i == len(arc_lengths):
                    break

            # If reached the end of the sub-section, but the last real sub-section point is not
            # at the exact end of the sub-section, then create a virtual point, which
            # lies at the exact end of the sub-section
            if not exact_length_match:
                virtual_arc_length_delta = split_length - arc_lengths[point_i-1]
                pt_segment_arc_length_delta = arc_lengths[point_i] - arc_lengths[point_i - 1]

                pt_segment_vector = old_coords[point_i] - old_coords[point_i-1]
                fraction_along = virtual_arc_length_delta / pt_segment_arc_length_delta
                virtual_coord = old_coords[point_i-1] + pt_segment_vector * fraction_along

                pt_segment_radius_delta = old_radii[point_i] - old_radii[point_i-1]
                virtual_radius = old_radii[point_i-1] + pt_segment_radius_delta * fraction_along

                split_sec_coords.append(virtual_coord)
                split_sec_radii.append(virtual_radius)

            split_sec.coords = np.array(split_sec_coords)
            split_sec.radii = np.array(split_sec_radii)
            split_sec.point_count = len(split_sec.radii)
            split_sec.name = self.name + "["+str(split_sec_i)+"]"

        return self.split_sections

    def update_coords_from_split_sections(self):
        if not self.was_split:
            return

        # Reassemble the coords and radii, skipping identical consecutive points
        prev_coord, prev_radius = None, None
        coords, radii = [], []
        for split_i, split_sec in enumerate(self.split_sections):
            for coord_i, coord in enumerate(np.reshape(split_sec.coords, (-1, 3))):
                radius = split_sec.radii[coord_i]

                # Skip if identical to previous point
                if prev_coord is not None and radius == prev_radius and \
                    np.all(np.isclose(coord, prev_coord, rtol=0.001)):
                        continue

                else:
                    coords.append(coord)
                    radii.append(radius)

                prev_coord = coord
                prev_radius = radius

        self.coords = np.array(coords).reshape(-1)
        self.radii = np.array(radii).reshape(-1)
        self.point_count = len(self.radii)

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
        """
        Iteratively removes split sections starting from the current section.

        :param recursive: Whether to process child sections recursively.
        :return: None
        """
        if recursive:
            # Initialize a stack with the current section
            stack = [self]
            while stack:
                current_sec = stack.pop()
                if current_sec.was_split:
                    current_sec.split_sections = []
                    current_sec.was_split = False
                # Add child sections to the stack to process them iteratively
                if current_sec.children:
                    # Reverse the children to maintain traversal order
                    stack.extend(reversed(current_sec.children))
        else:
            # Only process the current section
            if self.was_split:
                self.split_sections = []
                self.was_split = False


class BlenderRoot(BlenderSection):

    def __init__(self, index, name, group=None):
        super(BlenderRoot, self).__init__()

        self.index = index
        self.name = name
        self.group = group

    @property
    def ui_root(self):
        return self.group.ui_group.root_entries[self.name]

    def remove(self, node):
        # Remove view container objects if any
        if self.group is not None and self.group.view is not None:
            self.group.view.remove_container(self.name)

        # remove from UI and from node groups
        self.remove_from_group(delete=True)

        # remove from index
        node.root_index.pop(self.name)

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
        current_group.roots.pop(self.name)

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
        self.group.roots[self.name] = self

        # ui
        group.highlight()

        ui_group = self.group.ui_group
        root_entry = ui_group.root_entries.get(self.name)

        # If not on the list of cells (e.g. when newly added in NRN)
        if root_entry is None:
            root_entry = self.add_to_UI_group(ui_group)

        if root_entry is not None and not root_entry.selected:
            root_entry.selected = True