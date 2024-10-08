import threading
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from blenderneuron.blender.utils import get_operator_context_override, rdp, COLOR_RAMP_NAME
from fnmatch import fnmatch
import bpy
import numpy as np

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
        for root in rootgroup.roots.values():
            if len(root.coords) == 0:
                raise Exception(
                    "Section '"+root.name+"' has no 3D coordinates. Make sure the Cell Group "
                                          "has been imported from NEURON into Blender.")

        self.group = rootgroup

        self.containers = OrderedDict()
        self.make_curve_template()

        self.closed_ends = True

    def make_curve_template(self):
        curve_template = bpy.data.curves.new(self.group.name+"_bezier", type='CURVE')
        curve_template.dimensions = '3D'
        curve_template.resolution_u = self.group.segment_subdivisions
        curve_template.fill_mode = 'FULL'
        curve_template.bevel_depth = 0.0 if self.group.as_lines else 1.0
        curve_template.bevel_resolution = int((self.group.circular_subdivisions - 4) / 2.0)

        self.curve_template_name = curve_template.name

    @property
    def curve_template(self):
        return bpy.data.curves.get(self.curve_template_name)

    def on_first_link(self):
        # for window in bpy.context.window_manager.windows:
        #     for area in window.screen.areas:
        #         if area.type == 'VIEW_3D':
        #             for space in area.spaces:
        #                 if space.type == 'VIEW_3D': 
        #                     # Set grid size - One cell 100 um
        #                     # space.grid_scale = 100.0

        #                     # Set viewport clipping distance
        #                     # space.clip_end = 99999

        #                     # Disable relationship lines
        #                     # space.show_relationship_lines = False

        # Add a sun lamp - at 500,500,500 um
        sun_exists = False
        for light in bpy.data.lights:
            if light.type == 'SUN':
                sun_exists = True
                break

        if not sun_exists:
            bpy.ops.object.light_add(type="SUN", location=[500] * 3)

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
                    (not pattern_inverse and fnmatch(container.name, pattern)) or \
                    (pattern_inverse and not fnmatch(container.name, pattern)):
                container.get_object().select_set(state=select)

    def zoom_to_containers(self):

        # Select the container objects
        self.select_containers(True)

        # Zoom to selected
        context = get_operator_context_override()
        if bpy.app.version[0] < 4:
            # Before Blender 4, context override could be passed into the operator
            bpy.ops.view3d.view_selected(context, use_all_regions=False)
        else:
            with bpy.context.temp_override(**context): # pragma: no cover
                bpy.ops.view3d.view_selected(use_all_regions=False) # pragma: no cover

        # Unselect containers
        self.select_containers(False)

    def remove_container(self, container):
        # Lookup if passed in a name
        if type(container) == str:
            container = self.containers.get(container)
            if container is None:
                return

        container.remove()
        self.containers.pop(container.name)

    def remove(self):
        # Remove any previous containers
        containers = list(self.containers.values())
        for container in containers:
            self.remove_container(container)

        # Remove curve template
        try:
            bpy.data.curves.remove(self.curve_template) # already-iterative
        except TypeError:
            pass

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
                self.group.default_color,
                self.group.default_brightness,
                include_children,
                origin_type,
                self.closed_ends,
                container_material,
            )

            self.containers[container.name] = container

        return container

    def containers_to_mesh(self):
        self.select_containers()

        # Convert the selected container curves to mesh
        active_ob = next(o for o in bpy.context.collection.objects if o.select_get())
        bpy.context.view_layer.objects.active = active_ob
        
        #context = get_operator_context_override(selected_object=active_ob)
        bpy.ops.object.convert(target='MESH', keep_original=False)

    def mesh_containers_to_curves(self):
        self.select_containers()

        # Convert the selected container meshes to curves
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        bpy.ops.object.convert(target='CURVE', keep_original=False)

    def animate_activity(self, activity, material_name):
        if activity is None:
            return

        mat = bpy.data.materials.get(material_name)

        if mat is None:
            return

        times = activity.times
        values = activity.values
        group = self.group

        max_brightness = group.max_brightness

        if len(times) * len(values) == 0:
            return

        # Convert times to frames
        frames = np.round(times * self.group.frames_per_ms).astype(int)

        # Store the values in a custom material property
        # This allows inspecting raw values in the Graph editor
        for i, frame in enumerate(frames):
            mat["recorded_value"] = values[i]
            mat.keyframe_insert(data_path='["recorded_value"]', frame=frame)

        # Map values to 0-1 range
        # These are then used to determine the brightness and color
        if group.animate_brightness or group.animate_color:
            intensity = self.change_range(
                values,
                group.animation_range_low, group.animation_range_high,
                0.0, 1.0
            )

        if group.animate_brightness:
            # Get the Cycles emission shader node strength input
            emit_strength = mat.node_tree.nodes['Emission'].inputs['Strength']

            for i, frame in enumerate(frames):
                # Set the Cycles emit node intensity
                emit_strength.default_value = intensity[i] * max_brightness

                # Set the node emit keyframe
                emit_strength.keyframe_insert(data_path="default_value", frame=frame)

        if group.animate_color:
            # Get the Cycles emission node input color
            node_color = mat.node_tree.nodes['Emission'].inputs['Color']

            # Color ramp eval function
            color_value_at = group.color_ramp_material.node_tree.nodes[COLOR_RAMP_NAME].color_ramp.evaluate

            for i, frame in enumerate(frames):
                # Get the color value from the ramp widget
                frame_color4 = color_value_at(intensity[i])

                # Set the material color and Cycles node color
                node_color.default_value = mat.diffuse_color = frame_color4

                # Set the material and node color keyframes
                mat.keyframe_insert(data_path="diffuse_color", frame=frame)
                node_color.keyframe_insert(data_path="default_value", frame=frame)



    def change_range(self, values, in_min, in_max, out_min, out_max):
        """
        Map the values from in_ range to out_ range. Clamping them to be within out_ range.
        :param values:
        :param in_min:
        :param in_max:
        :param out_min:
        :param out_max:
        :return:
        """

        in_span = in_max - in_min
        range_position = (values - in_min) / in_span

        out_span = out_max - out_min
        result = out_span * range_position + out_min

        # Clamp to out range
        result = np.clip(result, out_min, out_max)

        return result

    def animate_section_material(self, root, recursive=True):
        """
        Animates the section materials starting from the root section. If recursive is True, it iteratively animates
        all child sections as well.

        :param root: The root section to start animation from
        :param recursive: Whether to process child sections recursively
        :return: None
        """
        if recursive:
            # Use a stack to iteratively traverse the section hierarchy
            stack = [root]
            while stack:
                node = stack.pop()
                self.animate_activity(node.activity, node.name)
                # Add child sections to the stack to process them iteratively
                stack.extend(reversed(node.children))
        else:
            # Only animate the root section
            self.animate_activity(root.activity, root.name)
