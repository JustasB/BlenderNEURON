from blenderneuron.blender.views.cellobjectview import CellObjectView
from blenderneuron.blender.views.sectionobjectview import SectionObjectView
from blenderneuron.blender.views.jsonview import JsonView
from blenderneuron.blender.utils import remove_prop_collection_item
from blenderneuron.rootgroup import *
from blenderneuron.blender.views.vectorconfinerview import VectorConfinerView
import bpy
from fnmatch import fnmatch
import json
import os

class BlenderRootGroup(RootGroup):

    @property
    def ui_group(self):
        return self.node.ui_properties.groups[self.name]

    @property
    def color_ramp_material(self):
        return bpy.data.materials.get(self.color_ramp_material_name)

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
        self.segment_subdivisions=2
        self.circular_subdivisions=6
        self.default_brightness = 1.0

        # Animation properties
        self.animate_brightness = True
        self.max_brightness = 5
        self.animate_color = True
        self.animation_range_low = -85
        self.animation_range_high = 20
        self.simplification_epsilon = 0.1
        self.frames_per_ms = 1

        self.state = 'new'
        self.root_filter = '*'

        # Default: Pale yellowish green
        self.color_ramp_material_name = self.create_color_ramp_material([0.14, 0.67, 0.02])

    @property
    def default_color(self):
        return self.color_ramp_material.diffuse_ramp.elements[0].color[0:3]

    @default_color.setter
    def default_color(self, value):
        self.color_ramp_material.diffuse_ramp.elements[0].color = value + [1]

    def create_color_ramp_material(self, default_color):
        name = self.name + '_color_ramp'

        mat = bpy.data.materials.new(name)
        mat.use_diffuse_ramp = True
        mat.diffuse_ramp.elements[0].color = default_color + [1] # alpha
        mat.diffuse_ramp.elements[-1].color = [1] * 4  # All white


        return name


    def highlight(self):
        self.node.ui_properties.groups_index = self.ui_group.index

    def from_full_NEURON_group(self, nrn_group):

        # Update each group root with the NRN root
        for nrn_root in nrn_group["roots"]:

            name = nrn_root["name"]

            if name not in self.roots:
                bpy.ops.blenderneuron.get_cell_list_from_neuron()

            self.roots[name].from_full_NEURON_section_dict(nrn_root)

        if "activity" in nrn_group:
            self.activity.from_dict(nrn_group["activity"])

            # Set activity times from the group time
            for root in self.roots.values():
                self.set_activity_times(root, self.activity.times)
                self.simplify_activity(root)
                
        else:
            self.clear_activity()
            
        self.state = 'imported'

    def set_activity_times(self, root, times):
        root.activity.times = times

        for child in root.children:
            self.set_activity_times(child, times)

    def simplify_activity(self, root):
        root.activity.simplify(self.simplification_epsilon)

        for child in root.children:
            self.simplify_activity(child)

    def import_group(self):
        self.node.import_groups_from_neuron([self])

    def remove_view(self):
        if self.view is not None:

            # Save any view changes
            # Except don't apply changes from an existing physics view
            if type(self.view) != VectorConfinerView:
                self.from_view()

            self.view.remove()

    def show(self, view_class=None, *args, **kwargs):
        if view_class is None:
            if self.interaction_granularity == 'Cell':
                view_class = CellObjectView

            if self.interaction_granularity == 'Section':
                view_class = SectionObjectView

        if not hasattr(view_class, "show"):
            raise Exception(str(view_class) + ' does not implement show() method')

        # If there is an existing view, get any changes made in view, then remove view
        self.remove_view()

        # Show the new view
        self.view = view_class(self, *args, **kwargs)
        self.view.show()

        return self.view

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
            root.add_to_UI_group(new_ui_group)


    def remove(self):
        if self.view is not None:
            self.view.remove()

        # Remove the group roots from the group before deleting group
        self.select_roots('None')

        # remove group from the UI list
        self.remove_from_UI()

        # and from node
        self.node.groups.pop(self.name)

        # Remove color ramp material
        ramp_mat = self.color_ramp_material

        if ramp_mat is not None:
            bpy.data.materials.remove(ramp_mat)

    def remove_from_UI(self):
        remove_prop_collection_item(self.node.ui_properties.groups, self.ui_group)

        self.node.ui_properties.groups_index = max(0, self.node.ui_properties.groups_index - 1)

    def add_groupless_roots(self):
        for root in self.node.root_index.values():
            if root.group is None:
                root.add_to_group(self)

    def select_roots(self, condition='All', pattern='*'):
        if condition == 'None':
            for root in list(self.roots.values()):
                if not fnmatch(root.name.lower(), pattern):
                    continue

                root.remove_from_group()

        else:
            for root in self.node.root_index.values():
                if not fnmatch(root.name.lower(), pattern):
                    continue

                if condition == 'All':
                    root.add_to_group(self)

                elif condition == 'Invert':
                    if root.group == self:
                        root.remove_from_group()
                    else:
                        root.add_to_group(self)



    def set_confiner_layers(self,
                            start_layer_object_name,
                            end_layer_object_name,
                            max_angle,
                            height_start,
                            height_end):

        self.highlight()

        start_layer = bpy.data.objects[start_layer_object_name]
        end_layer = bpy.data.objects[end_layer_object_name]

        settings = self.ui_group.layer_confiner_settings

        settings.start_mesh = start_layer
        settings.end_mesh = end_layer

        settings.max_bend_angle = max_angle
        settings.height_min = height_start
        settings.height_max = height_end

    def setup_confiner(self):
        self.highlight()

        self.show(VectorConfinerView)

    def confine_between_layers(self):
        self.highlight()

        if type(self.view) is VectorConfinerView:
            self.view.confine()

    def include_roots_by_name(self, names, exclude_others=False):
        names = set(names)

        for root in self.node.root_index.values():
            if root.name in names:
                root.add_to_group(self)

            else:
                if exclude_others and root.group is self:
                    root.remove_from_group()

    def to_file(self, file_name):
        self.from_view()

        group_dict = JsonView(self).show()

        dir = os.path.dirname(file_name)

        if dir != '' and not os.path.exists(dir):
            os.makedirs(dir)

        with open(file_name, 'w') as f:
            json.dump(group_dict, f)






