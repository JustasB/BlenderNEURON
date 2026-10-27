import threading
from blenderneuron.datablocknames import get_registry, entity_key
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
        raise NotImplementedError()

    @abstractmethod
    def update_group_with_view_data(self):
        raise NotImplementedError()


class ObjectViewAbstract(ViewAbstract):
    __metaclass__ = ABCMeta

    frame_view = True
    has_linked = False
    link_lock = threading.Lock()

    def __init__(self, rootgroup):
        for root in rootgroup.roots.values():
            if len(root.coords) == 0:
                raise Exception(
                    "Section '"+root.name+"' has no 3D coordinates. Make sure the Cell Group "
                                          "has been imported from NEURON into Blender.")

        self.group = rootgroup
        self.registry = get_registry()
        self.identity_scope = self.group.name
        self.materials = {}

        self.containers = OrderedDict()
        self.make_curve_template()
        self.material_template = CurveContainer.create_material(
            self.group.name + "_section_material_template",
            self.group.default_color,
            self.group.default_brightness, self.registry, self.identity_scope,
            role="material-template",
        )

        self.closed_ends = True

    def reserve_import(self, cell_view=False, split_length=0, group_view=False):
        """Reserve the complete geometry/material batch before building splines."""
        keys = []
        if group_view:
            keys.extend(entity_key(namespace, role, self.group.name, self.identity_scope)
                        for namespace, role in [('objects', 'section-container'), ('curves', 'section-geometry')])
        seen_sections = set()
        for root in self.group.roots.values():
            stack = [root]
            if self.group.recording_granularity == 'Cell' and not split_length:
                keys.append(entity_key('materials', 'section-material', root.name, self.identity_scope))
            while stack:
                section = stack.pop()
                if section.name in seen_sections:
                    raise self.registry.error(entity_key('objects', 'section-container', section.name, self.identity_scope),
                                              'Duplicate canonical section in import batch')
                seen_sections.add(section.name)
                sections = (section.make_split_sections(split_length) or [section]) if split_length else [section]
                for part in sections:
                    if not group_view and (not cell_view or section is root):
                        keys.extend(entity_key(namespace, role, part.name, self.identity_scope)
                                    for namespace, role in [('objects', 'section-container'), ('curves', 'section-geometry')])
                    if self.group.recording_granularity != 'Cell' or split_length:
                        names = ([part.name] if self.group.recording_granularity in ('Cell', 'Section') else
                                 ['%s[%s]' % (part.name, i) for i in range(len(part.radii)-1)])
                        keys.extend(entity_key('materials', 'section-material', name, self.identity_scope) for name in names)
                stack.extend(section.children)
        # Actions use the canonical owner identity, including embedded node trees.
        for key in list(keys):
            if key[1] == 'materials':
                keys.extend(entity_key('actions', key[2] + suffix, key[3] + 'Action', key[4])
                            for suffix in ('-action', '-nodes-action'))
        self.reserved_keys = keys
        # Protect readable planned names before allocating shortened candidates.
        for key in sorted(keys, key=lambda key: len(key[3].encode('utf-8')) > self.registry.maximum_bytes):
            self.registry.reserve(key)

    def make_curve_template(self):
        key = entity_key('curves', 'curve-template', self.group.name+"_bezier", self.identity_scope)
        curve_template = self.registry.create(key, lambda name: bpy.data.curves.new(name, type='CURVE'))
        self.curve_template_key = key
        curve_template.use_fake_user = True
        curve_template.dimensions = '3D'
        curve_template.resolution_u = self.group.segment_subdivisions
        curve_template.fill_mode = 'FULL'
        curve_template.bevel_depth = 0.0 if self.group.as_lines else 1.0
        curve_template.bevel_resolution = int((self.group.circular_subdivisions - 4) / 2.0)

        self.curve_template_name = curve_template.name

    @property
    def curve_template(self):
        return self.registry.resolve(self.curve_template_key)

    def on_first_link(self):
        # Set grid to 100um squares
        # Extend camera clipping so large cells are visible
        # Hide parent-child section relationship lines
        ObjectViewAbstract.configure_viewport()

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

    @staticmethod
    def configure_viewport():
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Grid size
                            space.overlay.grid_scale = 100.0

                            # Relationship lines
                            space.overlay.show_relationship_lines = False

                            # View clipping (SpaceView3D, NOT RegionView3D)
                            space.clip_start = 0.01
                            space.clip_end = 99999


    def link_containers(self):

        from blenderneuron.blender.somadisplay import attach
        if getattr(self.group, 'spherize_soma_if_DeqL', False):
            for container in self.containers.values():
                attach(container)

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

        if self.frame_view:
            self.zoom_to_containers()
        else:
            # Synapse searches still need current world transforms after linking.
            bpy.context.view_layer.update()

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
        # Framing must not select and deselect thousands of section objects.
        # Update once so bounds and world transforms include newly linked curves.
        from math import atan, sin
        from mathutils import Vector
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        if not self.containers:
            return
        low = Vector((float('inf'),) * 3)
        high = -low
        for container in self.containers.values():
            ob = container.get_object()
            for corner in ob.bound_box:
                point = ob.matrix_world @ Vector(corner)
                for axis in range(3):
                    low[axis] = min(low[axis], point[axis])
                    high[axis] = max(high[axis], point[axis])
        center = (low + high) / 2
        radius = max((high - low).length / 2, 0.01)
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                space = area.spaces.active
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region is None:
                    continue
                aspect = max(region.width, 1) / max(region.height, 1)
                # A bounding sphere fits for any view rotation. Account for the
                # narrower viewport dimension, lens and a 15% framing margin.
                tangent = 16 / max(space.lens, 1) * min(1, 1 / aspect)
                space.region_3d.view_location = center
                space.region_3d.view_distance = 1.15 * radius / sin(atan(tangent))

    def remove_container(self, container):
        # Lookup if passed in a name
        if type(container) == str:
            container = self.containers.get(container)
            if container is None:
                return

        container.remove()
        self.containers.pop(container.name)

    def remove(self):
        for key in getattr(self, 'reserved_keys', ()):
            self.registry.release(key)
        # Remove any previous containers
        containers = list(self.containers.values())
        for container in containers:
            self.remove_container(container)

        # The template is never assigned to a curve. Its independent copies
        # are removed by CurveContainer.remove above.
        if self.material_template is not None:
            self.registry.remove(self.material_template)
            self.material_template = None

        # Remove curve template
        try:
            if self.curve_template is not None:
                self.curve_template.use_fake_user = False
            self.registry.remove(self.curve_template) # already-iterative
        except TypeError:
            pass

    def create_section_container(self, section, include_children, origin_type,
                                 split_longer_than=0, container_material=None):
        if split_longer_than > 0 and include_children:
            raise Exception("Cannot include child sections in a container when splitting long sections")

        to_containers = [section]

        if split_longer_than > 0:
            split_sections = section.split_sections if section.was_split else section.make_split_sections(split_longer_than)

            if split_sections is not None:
                to_containers = split_sections

        for sec in to_containers:
            container = CurveContainer(
                sec,
                self.curve_template,
                self.group.smooth_sections,
                self.group.default_color,
                self.group.default_brightness,
                self.group.recording_granularity,
                include_children,
                origin_type,
                self.closed_ends,
                container_material,
                self.material_template, self.registry, self.identity_scope,
            )

            self.containers[container.name] = container
            self.materials.update(container.materials)

        return container

    def containers_to_mesh(self):
        """Create display mesh copies; managed morphology curves remain intact."""
        from blenderneuron.datablocknames import METADATA
        copies = []
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for container in self.containers.values():
            source = container.object
            mesh = bpy.data.meshes.new_from_object(source.evaluated_get(depsgraph))
            if METADATA in mesh:
                del mesh[METADATA]
            copy = bpy.data.objects.new(source.name + '_display', mesh)
            copy.matrix_world = source.matrix_world.copy()
            bpy.context.collection.objects.link(copy)
            copies.append(copy)
        return copies

    def mesh_containers_to_curves(self):
        raise RuntimeError('Display meshes cannot be restored as morphology. Use the original curves or reimport.')

    def animate_activity(self, activity, material_name):
        if activity is None:
            return

        # Public helper callers may pass an actual data-block or an actual Blender
        # name. Model-facing calls always resolve through the canonical dictionary.
        if isinstance(material_name, str):
            mat = (self.materials.get(material_name) if hasattr(self, 'materials')
                   else bpy.data.materials.get(material_name))
        else:
            mat = material_name

        if mat is None:
            return

        times = activity.times
        values = activity.values
        group = self.group

        max_brightness = group.max_brightness

        if len(times) * len(values) == 0:
            return

        # Convert times to frames
        frames_per_ms = bpy.context.scene.BlenderNEURON.simulator_settings.frames_per_ms
        frames = np.round(times * frames_per_ms).astype(int)

        # Store the values in a custom material property
        # This allows inspecting raw values in the Graph editor
        mat["recorded_value"] = values[-1]
        self.add_keyframes(mat, '["recorded_value"]', frames, values)

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
            strengths = intensity * max_brightness
            emit_strength.default_value = strengths[-1]
            self.add_keyframes(
                mat.node_tree,
                emit_strength.path_from_id("default_value"),
                frames,
                strengths,
            )

        if group.animate_color:
            # Get the Cycles emission node input color
            node_color = mat.node_tree.nodes['Emission'].inputs['Color']

            # Color ramp eval function
            color_value_at = group.color_ramp_material.node_tree.nodes[COLOR_RAMP_NAME].color_ramp.evaluate

            colors = np.asarray([color_value_at(value) for value in intensity])
            node_color.default_value = mat.diffuse_color = colors[-1]

            material_color_path = mat.path_from_id("diffuse_color")
            node_color_path = node_color.path_from_id("default_value")
            for component in range(4):
                self.add_keyframes(
                    mat,
                    material_color_path,
                    frames,
                    colors[:, component],
                    component,
                )
                self.add_keyframes(
                    mat.node_tree,
                    node_color_path,
                    frames,
                    colors[:, component],
                    component,
                )

    @staticmethod
    def add_keyframes(id_data, data_path, frames, values, array_index=0):
        """Append animation samples to an F-curve in Blender's bulk API."""
        animation_data = id_data.animation_data_create()
        if animation_data.action is None:
            registry = get_registry()
            owner_key = registry.identity(id_data)
            if owner_key is None:
                # Compatibility for callers animating their own Blender data-block.
                owner_key = entity_key('actions', 'external-animation', id_data.name, id_data.bl_rna.identifier)
            key = entity_key('actions', owner_key[2] + '-action', owner_key[3] + 'Action', owner_key[4])
            animation_data.action = registry.create(key, bpy.data.actions.new)

        action = animation_data.action
        if hasattr(action, "fcurve_ensure_for_datablock"):
            # Blender 4.4+ stores curves in slots/channelbags; the legacy
            # action.fcurves collection was removed in Blender 5.0.
            fcurve = action.fcurve_ensure_for_datablock(
                id_data, data_path, index=array_index)
        else:
            fcurve = action.fcurves.find(data_path, index=array_index)

        # Imported materials are new, so the normal fast path creates a fresh
        # F-curve.  Preserve Blender's replace semantics if this helper is
        # ever called for an already animated property.
        if fcurve is not None and len(fcurve.keyframe_points):
            for frame, value in zip(frames, values):
                fcurve.keyframe_points.insert(frame, value, options={'REPLACE'})
            fcurve.update()
            return

        if fcurve is None:
            fcurve = action.fcurves.new(data_path, index=array_index)

        point_count = len(frames)
        fcurve.keyframe_points.add(point_count)
        coordinates = np.empty(point_count * 2, dtype=np.float32)
        coordinates[0::2] = frames
        coordinates[1::2] = values
        fcurve.keyframe_points.foreach_set("co", coordinates)
        fcurve.update()



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

                if self.group.recording_granularity in  ('Cell','Section'):
                    self.animate_activity(activity=node.activity, material_name=node.name)

                else: # '3D Segment'
                    for iseg in range(len(node.radii)-1):
                        self.animate_activity(
                            activity=node.segment_activity.get(iseg),
                            material_name=f"{node.name}[{iseg}]"
                        )

                # Add child sections to the stack to process them iteratively
                stack.extend(reversed(node.children))
        else:
            # Only animate the root section materials
            if self.group.recording_granularity in ('Cell', 'Section'):
                self.animate_activity(activity=root.activity, material_name=root.name)

            else:  # '3D Segment'
                for iseg in range(len(root.radii) - 1):
                    self.animate_activity(
                        activity=root.segment_activity.get(iseg),
                        material_name=f"{root.name}[{iseg}]"
                    )
