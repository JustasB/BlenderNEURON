from math import sqrt, pi
import bpy
import numpy as np
from .utils import create_many_copies
from .. import controller

def _get_default_color(name):
    # Color ramps don't exist in 2.9 anymore
    # name = name + '_color_ramp'
    #
    # mat = bpy.data.materials.new(name)
    # mat.use_diffuse_ramp = True
    # mat.diffuse_ramp.elements[0].color = default_color + [1] # alpha
    # mat.diffuse_ramp.elements[-1].color = [1] * 4  # All white

    return (0.013, 0.011, 0.163, 1)
    # return (0.671, 0.760, 0.440, 1)


def _get_curve_template(name):
    # TODO: When CellGroups are implemented the curve template should be provided by
    # the CellGroup.
    curve_template = bpy.data.curves.new(name + "_bezier", type='CURVE')
    curve_template.dimensions = '3D'
    curve_template.resolution_u = 2 # self.group.segment_subdivisions
    curve_template.fill_mode = 'FULL'
    curve_template.bevel_depth = 1.0 # 0.0 if self.group.as_lines else 1.0
    curve_template.bevel_resolution = 1.0 # int((self.group.circular_subdivisions - 4) / 2.0)
    # Not found in 2.91:
    # curve_template.show_normal_face = False
    # curve_template.show_handles = False
    return curve_template

class CurveContainer:

    def __init__(
        self,
        cell,
        curve_template,
        smooth_sections,
        color,
        brightness,
        recursive=True,
        origin_type="center",
        closed_ends=True,
        container_material=None):

        self.name = controller.get_blender_name(cell)
        self.smooth_sections = smooth_sections
        self.closed_ends = closed_ends
        self.assigned_container_material = container_material
        self.default_color = color
        self.default_brightness = brightness

        # copy the curve template and make a new blender object out of it
        curve_template = _get_curve_template(self.name)
        self._bn_obj = bpy.data.objects.new(self.name, curve_template)

        self.linked = False
        self.material_indices = []

        # Quickly find the spline of a given section
        self.name2spline_index = {}
        self.spline_index2section = {}

        # Recursively add section splines and corresponding materials to the container
        for root in cell.roots:
            self.add_branch(root, recursive, in_top_level=True, origin_type=origin_type)

        bpy.context.scene.collection.objects.link(self._bn_obj)

    def get_object(self):
        return bpy.data.objects.get(self.name)

    @property
    def object(self):
        return bpy.data.objects[self.name]

    @property
    def curve(self):
        ob = self.get_object()

        return ob.data

    def set_parent_object(self, parent_container):

        child = self.get_object()
        parent = parent_container.get_object()

        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()

        # Children have their location and scale editing locked (to prevent disconnects)
        # Rotations are allowed
        child.lock_location = child.lock_scale = [True] * 3

    def remove(self):
        self.unlink()

        bl_objects = bpy.data.objects
        ob = self.get_object()
        object_name = ob.name

        # materials
        for mat in ob.data.materials:
            if mat is not None:
                # remove material animation if any
                if mat.animation_data is not None:
                    bpy.data.actions.remove(mat.animation_data.action)

                # remove material node animation
                if mat.node_tree is not None and mat.node_tree.animation_data is not None:
                    bpy.data.actions.remove(mat.node_tree.animation_data.action)

                # remove material
                bpy.data.materials.remove(mat)



        # curve
        bpy.data.curves.remove(ob.data)

    @property
    def origin(self):
        return self.get_object().location

    @origin.setter
    def origin(self, value):
        self.curve.location = value

    def diam0version(self, start, end):
        lengths = end - start

        # Versor extension
        length = sqrt(np.power(lengths,2).sum())

        # Extend in the same direction by a small amount
        if length > 0:
            versor = lengths / length
            extended = end + versor * 0.01

        # If the points are identical (should not happen), return the end point
        else:
            return end

        return extended

    def add_spline(self, coords, radii, smooth):
        curve = self.curve

        sec_spline = curve.splines.new('BEZIER')

        # This line is necessary due to a bug in Blender
        # see: https://developer.blender.org/T54112
        curve.resolution_u = curve.resolution_u

        # Subtract the container origin (as bezier points are
        # relative to the object origin)
        coords = coords - self.origin

        if self.closed_ends:
            # Add closed, 0-diam caps (to avoid open-ended cylinders)
            cap1 = self.diam0version(coords[1], coords[0])
            cap2 = self.diam0version(coords[-2], coords[-1])

            coords = np.concatenate(([cap1], coords, [cap2]))
            radii = np.concatenate(([0],radii,[0]))

        # Flatten the coords back (needed by the foreach_set() functions below)
        coords.shape = (-1)

        bezier_points = sec_spline.bezier_points

        # Allocate space for bezier points
        #bezier_points.clear() # can't clear the one initial point
        bezier_points.add(len(radii)-1)

        bezier_points.foreach_set('radius', radii)
        bezier_points.foreach_set('co', coords)

        if not smooth:
            # Fast
            bezier_points.foreach_set('handle_right', coords)
            bezier_points.foreach_set('handle_left', coords)

        else:
            # Slower
            for p in bezier_points:
                p.handle_right_type = p.handle_left_type = 'AUTO'

        return sec_spline


    @staticmethod
    def create_material(name, color, brightness):
        mat = bpy.data.materials.new(name)

        mat.diffuse_color = color
        # Doesn't exist in Blender 2.9
        # mat.emit = brightness

        # # Ambient and back lighting
        # mat.ambient = 0.85
        # mat.translucency = 0.85
        #
        # # Raytraced reflections
        # mat.raytrace_mirror.use = True
        # mat.raytrace_mirror.reflect_factor = 0.1
        # mat.raytrace_mirror.fresnel = 2.0

        # Add Blender render and Cycles nodes
        mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        links.clear()
        nodes.clear()

        # Cycles nodes
        cl_out = nodes.new('ShaderNodeOutputMaterial')
        cl_emit = nodes.new('ShaderNodeEmission')
        cl_emit.location = [-200, 0]
        cl_emit.inputs['Strength'].default_value = brightness
        cl_emit.inputs['Color'].default_value = list(mat.diffuse_color)

        # cl_trans = nodes.new('ShaderNodeBsdfTransparent')
        # cl_trans.location = [-200, 100]
        # links.new(cl_trans.outputs['BSDF'], cl_out.inputs['Surface'])

        links.new(cl_emit.outputs['Emission'], cl_out.inputs['Surface'])

        # Not Blender 2.9
        # # Blender render nodes
        # br_out = nodes.new('ShaderNodeOutput')
        # br_out.location = [0, -200]
        # br_mat = nodes.new('ShaderNodeExtendedMaterial')
        # br_mat.location = [-200, -200]
        # br_mat.material = mat
        #
        # links.new(br_mat.outputs['Color'], br_out.inputs['Color'])
        # links.new(br_mat.outputs['Alpha'], br_out.inputs['Alpha'])

        return mat

    def add_material_to_object(self, material):
        mats = self.curve.materials
        mats.append(material)
        mat_idx = len(mats)-1
        return mat_idx

    def to_global(self, local_coords):
        """
        This function performs the fancy fast vectorized multiplication of the container object's
        world matrix (trans, rot, scale) by the local points to obtain the global
        version of the coordinates.

        :param local_coords: Local coords as returned by bezier_points.foreach_get("co")
        :return: Global version of the local_coords
        """

        # Get the world matrix
        matrix = self.get_object().matrix_world

        # Reshape coords to Nx3 matrix
        local_coords.shape = (-1, 3)

        # Add an extra 1.0s column (for matrix dot prod)
        local_coords = np.c_[local_coords, np.ones(local_coords.shape[0])]

        # Dot product matrix with the coords transpose
        # Keep the first 3 rows (x,y,z)
        # Transpose result to Nx3
        # Flatten
        global_coords = np.dot(matrix, local_coords.T)[0:3].T.reshape((-1))

        return global_coords

    def update_group_section(self, root, recursive=True):

        ob = self.get_object()

        # Find the spline that corresponds to the section
        spline_i = self.name2spline_index[root.name]

        try:
            spline = self.curve.splines[spline_i]

        except IndexError:
            print("Could not find spline with index " + str(spline_i) + " in " + self.name +
                  ". This can happen if a spline is deleted in Edit Mode.")
            raise

        point_source = spline.bezier_points

        del spline

        # Get the 3d points
        num_coords = len(point_source)

        coords = np.zeros(num_coords * 3)
        point_source.foreach_get("co", coords)

        # Adjust coords for container origin and rotation
        coords = self.to_global(coords)

        if self.closed_ends:
            # Discard the 0-radius end caps
            coords = coords[3:-3]

        root.coords = coords.tolist()

        # Get radii
        radii = np.zeros(num_coords)
        point_source.foreach_get("radius", radii)
        root.radii  = (radii[1:-1] if self.closed_ends else radii).tolist()
        del radii

        # Cleanup before recursion
        del point_source, num_coords, coords

        if recursive:
            for child in root.children:
                self.update_group_section(child, recursive=True)

    def add_branch(self, branch, recursive=True, in_top_level=True, origin_type="center"):
        # Reshape the coords to be n X 3 array (for xyz)
        coords = np.array(branch.coords)
        coords.shape = (-1, 3)

        if in_top_level:
            self.set_origin(coords, origin_type)

        # Add section spline to the cell object
        spline = self.add_spline(coords, branch.radii, self.smooth_sections)

        # If material is not provided, create one
        if self.assigned_container_material is None:
            material = CurveContainer.create_material(
                str(branch),
                self.default_color,
                self.default_brightness
            )

        # If material is provided, assign it to the spline
        else:
            material = self.assigned_container_material

        mat_idx = self.add_material_to_object(material)

        # Assign the material to the new spline
        spline.material_index = mat_idx


        # Save spline index for later lookup
        # Note: In Blender, using edit-mode on a curve object, results in creation of
        # new spline instances when returning to object-mode. If references to the
        # old splines are kept, Blender usually crashes. Here we retain the spline index,
        # which is preserved (if splines are not deleted in edit-mode).
        spline_index = len(self.curve.splines) - 1
        self.name2spline_index[str(branch)] = spline_index
        self.spline_index2section[spline_index] = branch

        # Cleanup before starting recursion
        del spline, material, mat_idx

        # Do same with the children
        if recursive:
            for child in branch.children:
                self.add_branch(child, recursive=True, in_top_level=False)

    def set_origin(self, coords, type = "center"):
        if type == "center":
            point_count = coords.shape[0]

            center_i = int(point_count / 2)

            # If even number of 3D points, use the mean of the
            # two points closest to the section middle
            if point_count % 2 == 0:
                center_i2 = center_i - 1
                center = (coords[center_i] + coords[center_i2]) / 2.0
            else:
                center = coords[center_i]

            self.get_object().location = center

        if type == "first":
            self.get_object().location = coords[0]

    def link(self):
        link = bpy.context.scene.objects.link
        bl_objects = bpy.data.objects

        link(self.get_object())

        self.linked = True

    def unlink(self):
        unlink_from_scene = bpy.context.scene.objects.unlink

        try:
            ob = self.get_object()
            unlink_from_scene(ob)

        except RuntimeError:
            pass  # ignore if already unlinked

        self.linked = False
