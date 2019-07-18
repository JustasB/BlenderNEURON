import numpy as np
import bmesh, operator, bpy, threading, queue, marshal, zlib, traceback, time, re, inspect
from math import sqrt, radians, atan, tan, degrees
from statistics import mean
from collections import OrderedDict

class CellObjectView:
    link_lock = threading.Lock()
    has_linked = False

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

    # Executed on first export from simulator
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

    def select_containers(self, select):
        for container in self.containers.values():
            container.object.select = select

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

    def show(self):
        if self.group.interaction_granularity != "Cell":
            raise NotImplementedError()

        if self.group.recording_granularity != "Section":
            raise NotImplementedError()

        for root in self.group.roots.values():
            # Create container object
            container = CurveContainer(
                root,
                self.curve_template,
                self.group.smooth_sections
            )

            self.containers[container.root_hash] = container

        self.link_containers()

    def update_group(self):
        for root in self.group.roots.values():
            self.containers[root.hash].update_group_section(root, recursive=True)

class CurveContainer:

    def remove(self):
        self.unlink()

        # materials
        for mat in self.curve.materials:
            bpy.data.materials.remove(mat)

        # curve
        bpy.data.curves.remove(self.curve)

        # object
        bpy.data.objects.remove(self.object)


    def __init__(self, root, curve_template, smooth_sections):

        self.root_hash = root.hash
        self.name = root.name
        self.smooth_sections = smooth_sections
        self.default_color = [1,1,1]

        # copy the curve template and make a new blender object out of it
        self.curve = curve_template.copy()
        self.object = bpy.data.objects.new(self.name, self.curve)

        self.linked = False
        self.material_indices = []

        # Quickly find the spline of a given section
        self.hash2spline = {}

        # Recursively add section splines and corresponding materials to the container
        self.add_section(root, recursive=True)

    @property
    def origin(self):
        return self.object.location

    @origin.setter
    def origin(self, value):
        self.object.location = value

    def diam0version(self, start, end):
        lengths = end - start

        # Versor extension
        length = sqrt(np.power(lengths,2).sum())
        versor = lengths / length
        extended = end + versor * 0.01 # Extend in the same direction by a small amount

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

        # Add closed, 0-diam caps (to avoid open-ended cylinders)
        cap1 = self.diam0version(coords[1], coords[0])
        cap2 = self.diam0version(coords[-2], coords[-1])

        coords = np.concatenate(([cap1], coords, [cap2]))
        radii = np.concatenate(([0],radii,[0]))

        # Flatten the coords back (needed by the foreach_set() functions below)
        coords.shape = (-1)

        bezier_points = sec_spline.bezier_points

        # Spline comes with 1 initial pt, len(radii)=num pts
        bezier_points.add(len(radii) - 1)

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


    def create_material(self, name):
        result = bpy.data.materials.new(name)

        result.diffuse_color = self.default_color

        # Ambient and back lighting
        result.ambient = 0.85
        result.translucency = 0.85

        # Raytraced reflections
        result.raytrace_mirror.use = True
        result.raytrace_mirror.reflect_factor = 0.1
        result.raytrace_mirror.fresnel = 2.0

        return result

    def add_material_to_object(self, material):
        mats = self.curve.materials
        mats.append(material)
        mat_idx = len(mats)-1
        return mat_idx

    def to_global(self, local_coords):
        """
        This function performs the fancy fast vectorized multiplication of the container object's
        world matrix (trans, rot, scale) by the local bezier curve points to obtain the global
        version of the coordinates.

        :param local_coords: Local coords as returned by bezier_points.foreach_get("co")
        :return: Global version of the local_coords
        """

        # Get the world matrix
        matrix = self.object.matrix_world

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
        # Find the spline that corresponds to the section
        spline = self.hash2spline[root.hash]

        # Get the 3d points
        bezier_points = spline.bezier_points
        num_coords = len(bezier_points)

        coords = np.zeros(num_coords * 3)
        bezier_points.foreach_get("co", coords)

        # Adjust coords for container origin and rotation
        coords = self.to_global(coords)

        # Discard the 0-radius end caps
        coords = coords[3:-3]

        root.coords = coords.tolist()

        # Get radii
        radii = np.zeros(num_coords)
        bezier_points.foreach_get("radius", radii)
        root.radii  = radii[1:-1].tolist()

        # Cleanup before recursion
        del spline, bezier_points, num_coords, coords, radii

        if recursive:
            for child in root.children:
                self.update_group_section(child, recursive=True)

    def add_section(self, root, recursive=True, in_top_level=True):
        # Reshape the coords to be n X 3 array (for xyz)
        coords = np.array(root.coords)
        coords.shape = (-1, 3)

        if in_top_level:
            self.set_origin(coords)

        # Add section spline and material to the cell object
        spline = self.add_spline(coords, root.radii, self.smooth_sections)

        # Each section gets a material, whose emit property will be animated
        material = self.create_material(root.name)
        mat_idx = self.add_material_to_object(material)

        # Assign the material to the new spline
        spline.material_index = mat_idx

        # Save spline reference for later quick lookup
        self.hash2spline[root.hash] = spline

        # Cleanup before starting recursion
        del spline, material, mat_idx

        # Do same with the children
        if recursive:
            for child in root.children:
                self.add_section(child, recursive=True, in_top_level=False)

    def set_origin(self, coords):
        point_count = coords.shape[0]

        center_i = int(point_count / 2)

        # If even number of 3D points, use the mean of the
        # two points closest to the section middle
        if point_count % 2 == 0:
            center_i2 = center_i - 1
            center = (coords[center_i] + coords[center_i2]) / 2.0
        else:
            center = coords[center_i]

        self.object.location = center

    def link(self):
        bpy.context.scene.objects.link(self.object)

        self.linked = True

    def unlink(self):
        bpy.context.scene.objects.unlink(self.object)

        self.linked = False



