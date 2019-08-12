from abc import ABCMeta, abstractmethod
from math import acos, pi
from random import random
from mathutils import Euler, Vector
from blenderneuron.blender.views.sectionobjectview import SectionObjectView
import bpy

class VectorConfinerView(SectionObjectView):
    __metaclass__ = ABCMeta

    def __init__(self, group):
        super(VectorConfinerView, self).__init__(group)

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
        if is_top_level:
            origin_type = "center"
        else:
            origin_type = "first"

        self.create_section_container(root,
                                      include_children=False,
                                      origin_type=origin_type,
                                      split_longer_than=self.max_section_length)

        if recursive:
            for child in root.children:
                self.create_container_for_each_section(child, recursive=True, is_top_level=False)

    def remove(self):
        super(VectorConfinerView, self).remove()

        self.remove_split_sections()

    def remove_split_sections(self):
        for root in self.group.roots.values():
            root.remove_split_sections(recursive=True)

    @abstractmethod
    def confine(self):
        settings = self.group.ui_group.layer_confiner_settings

        for root in self.group.roots.values():
            self.confine_curve(
                self.containers[root.hash].object,
                settings.start_mesh,
                settings.end_mesh,
                settings.moveable_sections_pattern,
                [settings.height_min, settings.height_max],
                settings.max_bend_angle
            )

    @staticmethod
    def confine_between_meshes(obj, start_mesh, end_mesh, height_low, height_high, max_angle=89, iters=3):
        self = VectorConfinerView

        height_fraction = height_low + (height_high - height_low) * random()

        for i in range(iters):
            tip_loc = obj.matrix_world * obj.data.splines[0].bezier_points[-1].co

            closest_on_start, _ = self.closest_point_on_object(tip_loc, start_mesh)
            closest_on_end, _ = self.closest_point_on_object(tip_loc, end_mesh)

            vec_start2end = (closest_on_end - closest_on_start).normalized()
            vec_start2tip = (tip_loc - closest_on_start).normalized()
            angle = acos(min(max(vec_start2end.dot(vec_start2tip), -1), 1)) * 180 / pi
            above = angle < 90 - 0.02

            # Above = when on the same side as the end_mesh, below when on the other side
            if not above:
                vec_start2tip *= -1  # Flip direction

            height = (closest_on_end - closest_on_start).length
            align_target = closest_on_start + vec_start2tip * height * height_fraction

            self.align_object_towards(obj, align_target, max_angle / iters)

            bpy.context.scene.update()

    @staticmethod
    def closest_point_on_object(global_pt, mesh_obj):
        local_pt = mesh_obj.matrix_world.inverted() * global_pt

        _, mesh_pt, _, _ = mesh_obj.closest_point_on_mesh(local_pt)

        mesh_pt_global = mesh_obj.matrix_world * mesh_pt

        dist = (global_pt - mesh_pt_global).length

        return mesh_pt_global, dist

    @staticmethod
    def align_object_towards(ob, pt_global, max_angle):
        max_angle = max_angle / 180.0 * 3.141592

        ob_mw = ob.matrix_world
        end = ob.data.splines[0].bezier_points[-1].co
        start = ob.data.splines[0].bezier_points[0].co
        desired = ob_mw.inverted() * pt_global
        v_start = end - start
        v_des = desired - start
        q = v_start.rotation_difference(v_des).to_euler()

        # Clamp rotation angles
        q = Euler(list(map(lambda angle: min(max(angle, -max_angle), max_angle), q))).to_quaternion()

        ob.matrix_local = ob.matrix_local.copy() * q.to_matrix().to_4x4()

        ob.rotation_euler[2] *= 1  # This updates the scene

    @staticmethod
    def confine_curve(curve_obj, mesh, outer_mesh, name_pattern, height_range, max_angle):
        self = VectorConfinerView

        if name_pattern is None or name_pattern in curve_obj.name:
            self.confine_between_meshes(curve_obj, mesh, outer_mesh, height_range[0], height_range[1], max_angle)

        if len(curve_obj.children) > 0:
            for child in curve_obj.children:
                self.confine_curve(child, mesh, outer_mesh, name_pattern, height_range, max_angle)