import bpy
import threading
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

from blenderneuron.blender.views.curvecontainer import CurveContainer


class ObjectViewAbstract:
    __metaclass__ = ABCMeta

    has_linked = False
    link_lock = threading.Lock()

    def __init__(self, rootgroup):
        self.group = rootgroup

        self.containers = OrderedDict()
        self.make_curve_template()

    def make_curve_template(self):
        self.curve_template = bpy.data.curves.new("bezier", type='CURVE')
        self.curve_template.dimensions = '3D'
        self.curve_template.resolution_u = self.group.segment_subdivisions
        self.curve_template.fill_mode = 'FULL'
        self.curve_template.bevel_depth = 0.0 if self.group.as_lines else 1.0
        self.curve_template.bevel_resolution = int((self.group.circular_subdivisions - 4) / 2.0)

    def on_first_link(self):
        # Set viewport params
        for area in bpy.data.screens["Default"].areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        # Set grid size - One cell 100 um
                        space.grid_scale = 100.0

                        # Set viewport clipping distance
                        space.clip_end = 99999

        # Add a sun lamp - at 500,500,500 um
        sun_exists = False
        for lamp in bpy.data.lamps:
            if lamp.type == 'SUN':
                sun_exists = True
                break

        if not sun_exists:
            bpy.ops.object.lamp_add(type="SUN", location=[500] * 3)

        # Set camera clip distance
        for camera in bpy.data.cameras:
            camera.clip_end = 99999

    def link_containers(self):

        # Ensure no concurrent object linking
        with self.link_lock:

            # On first export
            if not self.has_linked:
                self.on_first_link()
                self.has_linked = True

            # Add any unlinked objects to the scene
            for container in self.containers.values():
                if not container.linked:
                    container.link()

        self.zoom_to_containers()

    def get_operator_context_override(self, selected_object = None):
        override = {}

        try:
            for area in bpy.data.screens["Default"].areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            override['area'] = area
                            override['region'] = region
                            raise StopIteration()

        except StopIteration:
            pass

        override["window"]        = bpy.context.window_manager.windows[0]
        override["scene"]         = bpy.data.scenes['Scene']
        override["screen"]        = bpy.data.screens["Default"]

        if selected_object:
            override["object"]        = selected_object
            override["active_object"] = selected_object
            override["edit_object"]   = selected_object

        return override

    def select_containers(self, select):
        for container in self.containers.values():
            container.object.select = select

    def zoom_to_containers(self):
        # Unselect everything
        bpy.ops.object.select_all(action='DESELECT')

        # Select the container objects
        self.select_containers(True)

        # Zoom to selected
        context = self.get_operator_context_override()
        bpy.ops.view3d.view_selected(context, use_all_regions=False)

        # Unselect containers
        self.select_containers(False)

    def remove_container(self, container):
        # Lookup if passed in a hash
        if type(container) == str:
            container = self.containers.get(container)
            if container is None:
                return

        container.remove()
        self.containers.pop(container.root_hash)

    def remove(self):
        # Remove any previous containers
        containers = list(self.containers.values())
        for container in containers:
            self.remove_container(container)

        # Remove curve template
        bpy.data.curves.remove(self.curve_template)

    @abstractmethod
    def show(self):
        pass

    @abstractmethod
    def update_group(self):
        pass

    def create_section_container(self, section, include_children, origin_type):

        container = CurveContainer(
            section,
            self.curve_template,
            self.group.smooth_sections,
            include_children,
            origin_type
        )

        self.containers[container.root_hash] = container