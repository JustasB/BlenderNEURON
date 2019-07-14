from blenderneuron.section import Section
from blenderneuron.blender.blendersegment3d import BlenderSegment3D

class BlenderSection(Section):

    def from_full_NEURON_section(self, nrn_section):
        self.point_count = nrn_section["point_count"]
        self.coords = nrn_section["coords"]
        self.radii = nrn_section["radii"]
        self.parent_connection_loc = nrn_section["parent_connection_loc"]
        self.connection_end = nrn_section["connection_end"]


        # Parse the children
        self.children = []
        for nrn_child in nrn_section["children"]:
            child = BlenderSection()
            child.from_full_NEURON_section(nrn_child)
            self.children.append(child)

        self.segments_3D = []
        for i, nrn_seg_3D in enumerate(nrn_section["segments_3D"]):
            seg = BlenderSegment3D(self, i+1)
            seg.from_dict(nrn_seg_3D)
            self.segments_3D.append(seg)

        self.activity.from_dict(nrn_section["activity"])


class BlenderRoot(BlenderSection):

    def __init__(self, index, hash, name, group=None):
        super(BlenderRoot, self).__init__()

        self.index = index
        self.hash = hash
        self.name = name
        self.group = group

    @property
    def ui_root(self):
        return self.node.ui_group[self.name]

    def remove(self, node):
        # remove from UI and from node groups
        self.remove_from_group()

        # remove from index
        node.root_index.pop(self.hash)

    def remove_from_group(self):
        if self.group is None:
            return

        # Keep a reference to group
        current_group = self.group

        # Set group to none in the root_index
        self.group = None

        # remove from node group
        current_group.roots.pop(self.hash)

        # from ui group
        root_entry = current_group.ui_group.root_entries[self.name]

        if root_entry.selected:
            root_entry.selected = False



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
        root_entry = self.group.ui_group.root_entries[self.name]

        if not root_entry.selected:
            root_entry.selected = True