from abc import ABCMeta, abstractmethod
from math import acos, pi
import random
from mathutils import Euler, Vector, Matrix
from blenderneuron.blender.views.sectionobjectview import SectionObjectView
import bpy
from fnmatch import fnmatch

class VectorConfinerView(SectionObjectView):
    __metaclass__ = ABCMeta

    def __init__(self, group):
        super(VectorConfinerView, self).__init__(group)

        self.closed_ends = False

    @property
    def max_bend_angle(self):
        return self.group.ui_group.layer_confiner_settings.max_bend_angle

    @property
    def max_section_length(self):
        return self.group.ui_group.layer_confiner_settings.max_section_length

    def show(self):
        # This will create section objects using the new split sections
        for root in self.group.roots.values():
            self.create_container_for_each_section(root)

        self.link_containers()

        self.parent_containers()

    def create_container_for_each_section(self, root, recursive=True, is_top_level=True):
        """
        Iteratively creates a container for each section starting from the root section.

        :param root: The root section to start creating containers from.
        :param recursive: Whether to process child sections recursively.
        :param is_top_level: Indicates if the root is the top-level section.
        :return: None
        """

        # Initialize the stack with the root node and its is_top_level status
        stack = [(root, is_top_level)]

        while stack:
            current_node, current_is_top_level = stack.pop()

            if current_is_top_level:
                origin_type = "center"
            else:
                origin_type = "first"

            self.create_section_container(
                current_node,
                include_children=False,
                origin_type=origin_type,
                split_longer_than=self.max_section_length
            )

            if recursive:
                # Add child sections to the stack to process them iteratively
                # Reverse the children to maintain traversal order
                for child in reversed(current_node.children):
                    stack.append((child, False))

    def remove(self):
        super(VectorConfinerView, self).remove()

        self.remove_split_sections()

    def remove_split_sections(self):
        for root in self.group.roots.values():
            root.remove_split_sections(recursive=True) # already-iterative

    @abstractmethod
    def confine(self):
        settings = self.group.ui_group.layer_confiner_settings

        random.seed(settings.seed)

        for root in self.group.roots.values():
            container = root.name if not root.was_split else root.split_sections[0].name

            self.confine_curve(
                self.containers[container].object,
                settings.start_mesh,
                settings.end_mesh,
                settings.moveable_sections_pattern,
                [settings.height_min, settings.height_max],
                settings.max_bend_angle
            )

    @staticmethod
    def confine_between_meshes(obj, start_mesh, end_mesh, height_low, height_high, max_angle, iters=11):
        self = VectorConfinerView

        # A random height fraction between start and end layers
        height_fraction = height_low + (height_high - height_low) * random.random()

        # Section proximal location in global coords
        sec_start_loc = obj.matrix_world @ obj.data.splines[0].bezier_points[0].co

        for i in range(iters):
            # Section distal location in global coords
            tip_loc = obj.matrix_world @ obj.data.splines[0].bezier_points[-1].co

            # Section direction vector
            vec_sec_dir = (tip_loc - sec_start_loc).normalized()

            # Closest point on start mesh from the tip
            closest_on_start, dist_to_start = self.closest_point_on_object(tip_loc, start_mesh)

            # Closest point on end mesh from tip
            closest_on_end, dist_to_end = self.closest_point_on_object(tip_loc, end_mesh)

            # Normal vector from closest point on start to end mesh
            vec_start2end = (closest_on_end - closest_on_start).normalized()

            # Normal vector from closest on start mesh to section tip
            vec_start2tip = (tip_loc - closest_on_start).normalized()

            # Degree angle between start2tip and start2end vectors
            angle = acos(min(max(vec_start2end.dot(vec_start2tip), -1), 1)) * 180 / pi

            # Tip is above start mesh (between start and end meshes)
            above = angle < 90 - 0.02

            # Above = when on the same side as the end_mesh, below when on the other side
            if not above:
                vec_start2tip *= -1  # Flip direction

            # Total dist between closest points on start and end meshes
            height = (closest_on_end - closest_on_start).length

            # Target is a random location along the closest start-end point vector
            align_target = closest_on_start + vec_start2end * height * height_fraction

            # With each iteration, the target approaches a stable limit
            self.align_object_towards(obj, align_target, max_angle / iters)

    @staticmethod
    def closest_point_on_object(global_pt, mesh_obj):
        local_pt = mesh_obj.matrix_world.inverted() @ global_pt

        _, mesh_pt, _, _ = mesh_obj.closest_point_on_mesh(local_pt)

        mesh_pt_global = mesh_obj.matrix_world @ mesh_pt

        dist = (global_pt - mesh_pt_global).length

        return mesh_pt_global, dist

    @staticmethod
    def align_object_towards(ob, pt_global, max_angle):
        max_angle = max_angle / 180.0 * 3.141592

        ob_mw = ob.matrix_world
        end = ob.data.splines[0].bezier_points[-1].co
        start = ob.data.splines[0].bezier_points[0].co
        desired = ob_mw.inverted() @ pt_global
        v_start = end - start
        v_des = desired - start
        q = v_start.rotation_difference(v_des).to_euler()

        # Clamp rotation angles
        q = Euler(list(map(lambda angle: min(max(angle, -max_angle), max_angle), q))).to_quaternion()

        ob.matrix_basis = ob.matrix_basis.copy() @ q.to_matrix().to_4x4()

        # Update matrices
        if ob.parent is None:
            ob.matrix_world = ob.matrix_basis
        else:
            ob.matrix_world = ob.parent.matrix_world @ ob.matrix_parent_inverse @ ob.matrix_basis

    @staticmethod
    def confine_curve(curve_obj, mesh, outer_mesh, name_pattern, height_range, max_angle):
        """
        Confines the curve objects between the specified meshes, iteratively traversing child curves.

        :param curve_obj: The curve object to start confinement from.
        :param mesh: The inner mesh to confine to.
        :param outer_mesh: The outer mesh to confine to.
        :param name_pattern: The name pattern to match curve objects.
        :param height_range: A tuple specifying the min and max height range.
        :param max_angle: The maximum angle allowed for confinement.
        :return: None
        """
        self = VectorConfinerView

        # Use a stack to iteratively traverse the curve objects
        stack = [curve_obj]

        while stack:
            current_curve = stack.pop()
            # Check if the current curve matches the name pattern or if no pattern is provided
            if name_pattern is None or fnmatch(current_curve.name, name_pattern):
                # Confine the current curve between the meshes
                self.confine_between_meshes(
                    current_curve, mesh, outer_mesh,
                    height_range[0], height_range[1], max_angle
                )

            # If the current curve has children, add them to the stack for processing
            if len(current_curve.children) > 0:
                # Reverse the children to maintain traversal order
                stack.extend(reversed(current_curve.children))


