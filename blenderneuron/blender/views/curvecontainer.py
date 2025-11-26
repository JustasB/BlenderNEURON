from math import sqrt, pi
import bpy
import numpy as np
from blenderneuron.blender.utils import create_many_copies

class CurveContainer:

    def __init__(self, root, curve_template, smooth_sections, color, brightness,
                 recording_granularity, recursive=True, origin_type="center", closed_ends=True,
                 container_material=None):

        self.name = root.name
        self.smooth_sections = smooth_sections
        self.closed_ends = closed_ends
        self.assigned_container_material = container_material
        self.default_color = color
        self.default_brightness = brightness
        self.recording_granularity = recording_granularity

        # copy the curve template and make a new blender object out of it
        bpy.data.objects.new(self.name, curve_template.copy())

        self.linked = False
        self.material_indices = []

        # Quickly find the spline of a given section
        self.name2spline_index = {}
        self.spline_index2section = {}

        # Recursively add section splines and corresponding materials to the container
        self.add_section(root, recursive, in_top_level=True, origin_type=origin_type)

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
                    bpy.data.actions.remove(mat.animation_data.action) # already-iterative

                # remove material node animation
                if mat.node_tree is not None and mat.node_tree.animation_data is not None:
                    bpy.data.actions.remove(mat.node_tree.animation_data.action) # already-iterative

                # remove material
                bpy.data.materials.remove(mat) # already-iterative



        # curve
        bpy.data.curves.remove(ob.data) # already-iterative

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

        # Add Cycles nodes
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
        cl_emit.inputs['Color'].default_value = mat.diffuse_color

        links.new(cl_emit.outputs['Emission'], cl_out.inputs['Surface'])

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
        """
        Iteratively updates the group sections starting from the root section. If recursive is True, it updates all child
        sections as well.

        :param root: The root section to start updating from.
        :param recursive: Whether to process child sections recursively.
        :return: None
        """

        # Initialize a stack with the root section
        stack = [root]

        while stack:
            current_root = stack.pop()

            ob = self.get_object()

            # Find the spline that corresponds to the section
            spline_i = self.name2spline_index[current_root.name]

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

            current_root.coords = coords.tolist()

            # Get radii
            radii = np.zeros(num_coords)
            point_source.foreach_get("radius", radii)
            current_root.radii = (radii[1:-1] if self.closed_ends else radii).tolist()
            del radii

            # Cleanup before processing next section
            del point_source, num_coords, coords

            if recursive:
                # Add child sections to the stack to process them iteratively
                stack.extend(reversed(current_root.children))

    def add_section(self, root, recursive=True, in_top_level=True, origin_type="center"):
        """
        Iteratively adds sections to the cell object starting from the root section.

        :param root: The root section to start adding from.
        :param recursive: Whether to process child sections recursively.
        :param in_top_level: Indicates if the root is the top-level section.
        :param origin_type: The origin type to use when setting the origin.
        :return: None
        """

        # Initialize the stack with the root node and its in_top_level status
        stack = [(root, in_top_level)]

        while stack:
            current_node, current_in_top_level = stack.pop()

            # Reshape the coords to be n X 3 array (for xyz)
            coords = np.array(current_node.coords)
            coords.shape = (-1, 3)

            if current_in_top_level:
                self.set_origin(coords, origin_type)

            if self.recording_granularity in ('Cell', 'Section'):
                # Add section spline to the cell object
                spline = self.add_spline(coords, current_node.radii, self.smooth_sections)

                if self.assigned_container_material is None:
                    material = CurveContainer.create_material(
                        current_node.name,
                        self.default_color,
                        self.default_brightness
                    )

                # If material is provided, assign it to the spline
                else:
                    material = self.assigned_container_material

                mat_idx = self.add_material_to_object(material)

                # Assign the material to the new spline
                spline.material_index = mat_idx

            else: # '3D Segment'-level recording granularity
                # A "3D segment" is the interval between two consecutive 3D NEURON points
                # Note this is different from section.nseg. Num 3D segments == section.n3d()-1
                # To animate each segment's color, will make each segment into a spline in the curve
                # since splines can be assigned materials, each spline will get its own material
                segment_count = len(coords) - 1

                for s in range(segment_count):
                    # This will be a two consecutive point spline
                    segment_coords = coords[s:s+2]
                    segment_radii = current_node.radii[s:s+2]

                    spline = self.add_spline(segment_coords, segment_radii, smooth=False)

                    # Each segment will get its own material with [seg_idx]'based name
                    material = CurveContainer.create_material(
                        f"{current_node.name}[{s}]",
                        self.default_color,
                        self.default_brightness
                    )

                    mat_idx = self.add_material_to_object(material)

                    # Assign the material to the new spline
                    spline.material_index = mat_idx

            # Save spline index for later lookup
            # Note: In Blender, using edit-mode on a curve object, results in creation of
            # new spline instances when returning to object-mode. If references to the
            # old splines are kept, Blender usually crashes. Here we retain the spline index,
            # which is preserved (if splines are not deleted in edit-mode).
            spline_index = len(self.curve.splines) - 1
            self.name2spline_index[current_node.name] = spline_index
            self.spline_index2section[spline_index] = current_node

            # Cleanup before starting recursion
            del spline, material, mat_idx

            # Do same with the children
            if recursive:
                # Add child sections to the stack to process them iteratively
                # Reverse the children to maintain traversal order
                for child in reversed(current_node.children):
                    stack.append((child, False))

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
        bpy.context.collection.objects.link(self.get_object()) # already-iterative

        self.linked = True

    def unlink(self):
        try:
            bpy.context.collection.objects.unlink(self.get_object()) # already-iterative

        except RuntimeError:
            pass  # ignore if already unlinked

        self.linked = False


