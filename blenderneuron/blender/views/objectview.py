import threading
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from blenderneuron.blender.utils import get_operator_context_override

import bpy

from blenderneuron.blender.views.curvecontainer import CurveContainer


class ViewAbstract(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def show(self):
        pass

    @abstractmethod
    def update_group(self):
        pass


class ObjectViewAbstract(ViewAbstract):
    __metaclass__ = ABCMeta

    has_linked = False
    link_lock = threading.Lock()

    def __init__(self, rootgroup):
        self.group = rootgroup

        self.containers = OrderedDict()
        self.make_curve_template()

        self.closed_ends = True

    def make_curve_template(self):
        curve_template = bpy.data.curves.new("bezier", type='CURVE')
        curve_template.dimensions = '3D'
        curve_template.resolution_u = self.group.segment_subdivisions
        curve_template.fill_mode = 'FULL'
        curve_template.bevel_depth = 0.0 if self.group.as_lines else 1.0
        curve_template.bevel_resolution = int((self.group.circular_subdivisions - 4) / 2.0)
        curve_template.show_normal_face = False
        curve_template.show_handles = False

        self.curve_template_name = curve_template.name

    @property
    def curve_template(self):
        return bpy.data.curves[self.curve_template_name]

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

                        # Disable relationship lines
                        space.show_relationship_lines = False

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

    def select_containers(self, select=True, pattern=None, pattern_inverse=False):
        # First, unselect everything
        bpy.ops.object.select_all(action='DESELECT')

        # Then select the containers
        for container in self.containers.values():
            if pattern is None or \
                    (not pattern_inverse and pattern in container.name) or \
                    (pattern_inverse and pattern not in container.name):
                container.get_object().select = select

    def zoom_to_containers(self):

        # Select the container objects
        self.select_containers(True)

        # Zoom to selected
        context = get_operator_context_override()
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

    def create_section_container(self, section, include_children, origin_type,
                                 split_longer_than=0, container_material=None):
        if split_longer_than > 0 and include_children:
            raise Exception("Cannot include child sections in a container when splitting long sections")

        to_containers = [section]

        if split_longer_than > 0:
            split_sections = section.make_split_sections(split_longer_than)

            if split_sections is not None:
                to_containers = split_sections

        for sec in to_containers:
            container = CurveContainer(
                sec,
                self.curve_template,
                self.group.smooth_sections,
                include_children,
                origin_type,
                self.closed_ends,
                container_material,
            )

            self.containers[container.root_hash] = container


    def containers_to_mesh(self):
        self.select_containers()

        # Convert the selected container curves to mesh
        active_ob = next(o for o in bpy.context.scene.objects if o.select)
        bpy.context.scene.objects.active = active_ob
        
        #context = get_operator_context_override(selected_object=active_ob)
        bpy.ops.object.convert(target='MESH', keep_original=False)

    def mesh_containers_to_curves(self):
        self.select_containers()

        # Convert the selected container meshes to curves
        bpy.context.scene.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.convert(target='CURVE', keep_original=False)