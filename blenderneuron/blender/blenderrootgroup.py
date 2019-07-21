from blenderneuron.blender.utils import remove_prop_collection_item
from blenderneuron.rootgroup import *
from blenderneuron.blender.views.physicsmeshsectionobjectview import PhysicsMeshSectionObjectView

class BlenderRootGroup(RootGroup):

    @property
    def ui_group(self):
        return self.node.ui_properties.groups[self.name]

    def __init__(self, name, node):
        super(BlenderRootGroup, self).__init__()

        self.selected = True
        self.name = name
        self.node = node

        self.view = None

        # Group display properties
        self.smooth_sections = True
        self.spherize_soma_if_DeqL=True
        self.as_lines=False
        self.segment_subdivisions=3
        self.circular_subdivisions=12
        self.default_color = [1, 1, 1]

        self.state = 'new'


    def from_full_NEURON_group(self, nrn_group):
        self.state = 'imported'

        # Update each group root with the NRN root
        for nrn_root in nrn_group["roots"]:
            self.roots[nrn_root["hash"]].from_full_NEURON_section(nrn_root)

        self.activity.from_dict(nrn_group["activity"])

    def show(self, view_class):
        if not hasattr(view_class, "show"):
            raise Exception(str(view_class) + ' does not implement show() method')

        # If there is an existing view, get any changes made to it, and remove it
        if self.view is not None:
            self.from_view()
            self.view.remove()

        # Show the new view
        self.view = view_class(self)
        self.view.show()

    def from_view(self):
        if self.view is None:
            return

        if not hasattr(self.view, "update_group"):
            raise Exception(str(self.view.__class__) + ' does not implement update_group() method')

        self.view.update_group()

    def add_to_UI(self):
        i = len(self.node.groups.keys())-1

        new_ui_group = self.node.ui_properties.groups.add()
        new_ui_group.name = self.name
        new_ui_group.index = i
        new_ui_group.selected = True

        # Highlight the UI group
        self.node.ui_properties.groups_index = i

        # Fill UI group list with not-selected root sections
        for root in self.node.root_index.values():

            # List all roots as available for selection in the group root UI list
            ui_root = new_ui_group.root_entries.add()
            ui_root.index = root.index
            ui_root.hash = root.hash
            ui_root.name = root.name


    def remove(self):
        if self.view is not None:
            self.view.remove()

        # Remove the group roots from the group before deleting group
        roots = list(self.roots.values())
        for root in roots:
            root.remove_from_group()

        # remove group from the UI list
        self.remove_from_UI()

        # and from node
        self.node.groups.pop(self.name)

    def remove_from_UI(self):
        remove_prop_collection_item(self.node.ui_properties.groups, self.ui_group)

        self.node.ui_properties.groups_index = max(0, self.node.ui_properties.groups_index - 1)

    def add_groupless_roots(self):
        for root in self.node.root_index.values():
            if root.group is None:
                root.add_to_group(self)

    def align_to_layer(self):

        self.show(PhysicsMeshSectionObjectView)




