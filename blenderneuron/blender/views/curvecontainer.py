from math import sqrt, pi
import bpy
import numpy as np
from blenderneuron.datablocknames import get_registry, entity_key, METADATA, key_json

class CurveContainer:

    def __init__(self, root, curve_template, smooth_sections, color, brightness,
                 recording_granularity, recursive=True, origin_type="center", closed_ends=True,
                 container_material=None, material_template=None, registry=None, identity_scope="",
                 roots=None, container_name=None, root_materials=None):

        roots = list(roots) if roots is not None else [root]
        self.root_materials = root_materials or {}
        self.name = self.canonical_name = container_name or root.name
        self.registry = registry or get_registry()
        self.identity_scope = identity_scope
        self.object_key = entity_key('objects', 'section-container', self.canonical_name, identity_scope)
        self.materials = {}
        self.smooth_sections = smooth_sections
        self.closed_ends = closed_ends
        self.assigned_container_material = container_material
        self.material_template = material_template
        self.default_color = color
        self.default_brightness = brightness
        self.recording_granularity = recording_granularity

        # copy the curve template and make a new blender object out of it
        curve_key = entity_key('curves', 'section-geometry', self.canonical_name, identity_scope)
        self.registry.reserve(self.object_key)
        self.registry.reserve(curve_key)
        existing = self.registry.resolve(self.object_key)
        self._object = self.registry.create(
            self.object_key, lambda name: bpy.data.objects.new(
                name, self.registry.copy(curve_key, curve_template)))
        self.blender_name = self._object.name

        self.linked = False
        self.material_indices = []

        # Quickly find the spline of a given section
        self.name2spline_index = {}
        self.spline_index2section = {}

        # Recursively add section splines and corresponding materials to the container
        if existing is None:
            for index, cell_root in enumerate(roots):
                self.assigned_container_material = self.root_materials.get(cell_root.name, container_material)
                self.add_section(cell_root, recursive, in_top_level=index == 0, origin_type=origin_type)
            # Persist spline identity separately: spline RNA references cannot survive edit mode.
            import json
            self._object['blenderneuron_splines'] = json.dumps(list(self.name2spline_index))
        else:
            self.restore_sections(roots, recursive)

    def get_object(self):
        ob = self.registry.resolve(self.object_key)
        if ob is None:
            raise self.registry.error(self.object_key, 'Container object is missing')
        self._object = ob
        self.blender_name = ob.name
        return ob

    @property
    def object(self):
        return self.get_object()

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

    def restore_sections(self, roots, recursive):
        import json
        try:
            geometry_key = entity_key('curves', 'section-geometry', self.canonical_name, self.identity_scope)
            if self.registry.resolve(geometry_key) != self.curve:
                raise ValueError('object geometry does not match its canonical identity')
            names = json.loads(self._object['blenderneuron_splines'])
            if not isinstance(names, list) or len(names) != len(self.curve.splines) or len(set(names)) != len(names):
                raise ValueError('invalid spline identities')
            self.name2spline_index = {name: i for i, name in enumerate(names)}
            stack = [(root, self.root_materials.get(root.name, self.assigned_container_material))
                     for root in roots]
            while stack:
                section, assigned_material = stack.pop()
                section_names = ([section.name] if self.recording_granularity in ('Cell', 'Section') else
                                 ['%s[%s]' % (section.name, i) for i in range(len(section.radii)-1)])
                for name in section_names:
                    index = self.name2spline_index[name]
                    self.spline_index2section[index] = section
                    material = self.curve.materials[self.curve.splines[index].material_index]
                    expected = assigned_material
                    key = entity_key('materials', 'section-material', name, self.identity_scope)
                    if expected is None:
                        expected = self.registry.resolve(key)
                    if material is None or material != expected:
                        raise ValueError('spline material does not have the expected identity')
                    self.materials[name] = material
                if recursive:
                    stack.extend((child, assigned_material) for child in section.children)
            if len(self.spline_index2section) != len(names):
                raise ValueError('morphology differs from saved splines')
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            raise self.registry.error(self.object_key, 'Cannot recover splines on %r: %s' % (self.blender_name, exc)) from exc

    def remove(self):
        ob = self.registry.resolve(self.object_key)
        if ob is None:
            return
        curve = ob.data
        materials = list({mat.as_pointer(): mat for mat in curve.materials if mat is not None}.values())
        self.registry.remove(ob)
        self.registry.remove(curve)
        for mat in materials:
            # Cell materials can be shared by several section containers.
            if mat.users:
                continue
            actions = []
            for owner in (mat, mat.node_tree):
                if owner is not None and owner.animation_data is not None and owner.animation_data.action is not None:
                    actions.append(owner.animation_data.action)
            self.registry.remove(mat)
            for action in actions:
                if action.users == 0:
                    self.registry.remove(action)
        self.linked = False

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
    def create_material(name, color, brightness, registry=None, identity_scope='', role='section-material'):
        registry = registry or get_registry()
        key = entity_key('materials', role, name, identity_scope)
        existing = registry.resolve(key)
        if existing is not None:
            return existing
        mat = registry.create(key, bpy.data.materials.new)

        mat.diffuse_color = color

        # Add Cycles nodes
        mat.use_nodes = True
        CurveContainer.identify_node_tree(mat, registry)

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

    @staticmethod
    def identify_node_tree(material, registry):
        key = registry.identity(material)
        tree_key = entity_key('node_trees', key[2] + '-nodes', key[3], key[4])
        # Embedded node-tree names are read-only; their owner carries the mapping.
        material.node_tree[METADATA] = key_json(tree_key)

    def create_section_material(self, name):
        if self.material_template is None:
            material = CurveContainer.create_material(
                name, self.default_color, self.default_brightness,
                self.registry, self.identity_scope)
        else:
            key = entity_key('materials', 'section-material', name, self.identity_scope)
            material = self.registry.copy(key, self.material_template)
            self.identify_node_tree(material, self.registry)
        self.materials[name] = material
        return material

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

    def update_group_section_with_view_data(self, root, recursive=True):
        """
        Updates internal BlenderSection instances with 3D data from Blender curve objects
        For example after the curves/points were moved/rotated in Blender
        After this step, the modified morphology can be exported back to NEURON to update the sections in NEURON

        :param root: The top-level BlenderSection instance of a cell
        :param recursive: Whether to update BlenderRoot's child sections as well.

        After this completes, Curve points+radii should match BlenderRoot points+radii
        """

        # Initialize a stack with the root section
        stack = [root]

        while stack:
            current_root = stack.pop()

            if self.recording_granularity in ('Cell', 'Section'):
                # Get 3d data from single section spline
                section_coords, section_radii = self.get_spline_3d_data(current_root.name)

            else: # '3D Segment'
                # In segment granularity, each 3D segment has its own spline+material
                # Need to extract and merge the coords+radii from the splines into a single list
                section_coords = []
                section_radii = []
                for iseg in range(len(current_root.radii)-1):
                    seg_coords, seg_radii = self.get_spline_3d_data(f"{current_root.name}[{iseg}]")

                    # Each segment spline is a 2-consecutive-NRN-point spline
                    # want to add each point only once when re-building merged coords
                    section_coords.append(seg_coords[0:3])
                    section_radii.append(seg_radii[0])

                    # if last segment spline, add the last segment point
                    if iseg == len(current_root.radii)-2:
                        section_coords.append(seg_coords[3:6])
                        section_radii.append(seg_radii[1])

            current_root.coords = section_coords
            current_root.radii = section_radii

            if recursive:
                # Add child sections to the stack to process them iteratively
                stack.extend(reversed(current_root.children))

    def get_spline_3d_data(self, spline_name):

        # Find the spline that corresponds to the section
        spline_i = self.name2spline_index[spline_name]

        try:
            spline = self.curve.splines[spline_i]

        except IndexError:
            print("Could not find spline with index " + str(spline_i) + " in " + self.name +
                  ". This can happen if a spline is deleted in Edit Mode.")
            raise

        # Get the 3d points
        num_coords = len(spline.bezier_points)

        coords = np.zeros(num_coords * 3)
        spline.bezier_points.foreach_get("co", coords)

        # Adjust coords for container origin and rotation
        coords = self.to_global(coords)

        if self.closed_ends:
            # Discard the 0-radius end caps that were added to the spline
            coords = coords[3:-3]

        # Get radii
        radii = np.zeros(num_coords)
        spline.bezier_points.foreach_get("radius", radii)
        radii = (radii[1:-1] if self.closed_ends else radii).tolist()

        return coords.tolist(), radii

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
                    material = self.create_section_material(current_node.name)

                # If material is provided, assign it to the spline
                else:
                    material = self.assigned_container_material
                    self.materials[current_node.name] = material

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
                    material = self.create_section_material(f"{current_node.name}[{s}]")

                    mat_idx = self.add_material_to_object(material)

                    # Assign the material to the new spline
                    spline.material_index = mat_idx

                    # Save splines for later fast lookup
                    spline_index = len(self.curve.splines) - 1
                    self.name2spline_index[f"{current_node.name}[{s}]"] = spline_index
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
        ob = self.get_object()
        if bpy.context.collection.objects.get(ob.name) != ob:
            bpy.context.collection.objects.link(ob)

        self.linked = True

    def unlink(self):
        try:
            bpy.context.collection.objects.unlink(self.get_object()) # already-iterative

        except RuntimeError:
            pass  # ignore if already unlinked

        self.linked = False


