# distutils: define_macros=CYTHON_TRACE=1
# cython: profile=True

import bpy as blenderpy
import numpy as np
import bmesh, operator, bpy, threading, queue, marshal, zlib

class NeuroServer:

    def __init__(self):
        self.IP = "192.168.0.34"
        self.Port = 8000

        self.resting_color = np.array((30/255.0, 138/255.0, 112/255.0))   # Tinted bluish green
        self.active_color = np.array((0.992, 0.455, 0))                   # Tinted redish yellow
        self.color_dist = self.active_color - self.resting_color

        self.background_zenith_color = (0,0.040,0.070)           # Shaded greenish blue
        self.background_horizon_color = (0,0.008, 0.010)        # Darker zenith

        self.ui_background_zenith_color = (0,0.22,0.294)           # Shaded greenish blue
        self.ui_background_horizon_color = (0,0.086, 0.098)        # Darker zenith

        self.bpy = blenderpy

        # Level to rank map
        self.level_rank = {
            'Group': 4,
            'Cell': 3,
            'Section': 2,
            'Segment': 1
        }

        # Clear scene
        try:
            bpy.data.objects.remove(bpy.data.objects["Cube"])
        except:
            pass

        try:
            bpy.data.objects.remove(bpy.data.objects["Lamp"])
        except:
            pass

        # Default curve to use
        self.blank_curve = bpy.data.curves.new("bezier", type='CURVE')
        self.blank_curve.dimensions = '3D'
        self.blank_curve.resolution_u = 1  # Segment subdivisions
        self.blank_curve.fill_mode = 'FULL'
        self.blank_curve.bevel_depth = 1.0
        self.blank_curve.bevel_resolution = 1  # this*2+4 = Circular subdivisions

        # Expand the clip area
        self.set_clip_distance()

        # Resting color
        self.solidColor = create_default_material(self.resting_color.tolist(), "SolidColor")

        # Background color
        bpy.data.worlds["World"].use_sky_blend = True
        bpy.data.worlds["World"].zenith_color = self.background_zenith_color
        bpy.data.worlds["World"].horizon_color = self.background_horizon_color
        bpy.data.worlds["World"].light_settings.use_environment_light = True

        # UI background
        bpy.context.user_preferences.themes[0].view_3d.space.gradients.show_grad = True
        bpy.context.user_preferences.themes[0].view_3d.space.gradients.high_gradient = self.ui_background_zenith_color
        bpy.context.user_preferences.themes[0].view_3d.space.gradients.gradient = self.ui_background_horizon_color

        # Dendrite path resolution - higher values make the sections smoother, but use more memory
        self.segment_subdivisions = 2
        self.circular_subdivisions = 8

        self.objects = {}
        self.has_linked = False
        self.link_lock = threading.Lock()

        self.queue = queue.Queue()
        self.progress_start()

    def progress_start(self):
        self.tasks_total = 0
        self.tasks_done = 0
        return 0

    def progress_add(self, task, count = 1):
        self.tasks_total += count
        self.queue.put(task)
        return 0

    def progress_complete(self):
        self.tasks_done += 1
        return 0

    def progress_get_done(self):
        return self.tasks_done

    def progress_get_total(self):
        return self.tasks_total

    # Executed on first export from simulator
    def on_first_link(self):
        # Add a sun lamp
        bpy.ops.object.lamp_add(type="SUN", location=(10000, 10000, 10000))

        # Set reasonable units
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 0.001

    def set_segment_activities(self, segments):
        for seg in segments:
            self.set_segment_activity(seg["name"], seg["times"], seg["activity"])

    def set_segment_activity(self, name, times, activity):
        seg_mat = self.bpy.data.materials[name]

        colors = list(map(self.activity_to_color, activity))

        for t in range(len(times)):
            seg_mat.diffuse_color = colors[t]
            seg_mat.keyframe_insert(data_path="diffuse_color", frame=int(times[t]))

        self.progress_complete()

    def activity_to_color(self, activity):
        scale = (activity + 80.0) / 120.0

        if activity < 0:
            scale = 0.0
        elif activity > 1:
            scale = 1.0

        return (self.resting_color + self.color_dist * scale).tolist()

    def create_cons(self, cons):
        for con in cons:
            self.create_con(con)

    def create_con(self, con):
        start = np.array(con["from"])
        end = np.array(con["to"])
        lengths = end - start
        arrow_head = end - lengths * 0.05  # Position the arrow head a few percent from end
        arrow_base = arrow_head - lengths * 0.01

        start = start.tolist()
        arrow_base = arrow_base.tolist()
        arrow_head = arrow_head.tolist()
        end = end.tolist()

        # Set diameters of the arrow
        start.append(1)
        arrow_base.append(1)
        arrow_head.append(3)
        end.append(0)

        con_path = [{
            "name": con["name"],
            "coords": [start, arrow_base,arrow_head, end]
        }]

        self.create_path(con_path, res_bev = 1, res_u = 1, addCaps = False)

    def make_paths(self, paths, selectable_sections = False):
        for path in paths:
            self.create_path(path, selectable_sections)

    def visualize_group(self, group):
        group_name = group["name"] + "Group"
        interaction_level = group["interaction_level"]
        color_level = group["color_level"]
        smooth = group['smooth_sections']

        res_bev = get_res_bev(group["circular_subdivisions"])
        res_u = get_res_u(group["segment_subdivisions"])

        if color_level == 'Group':
            material = self.create_material(group_name, group)

        if interaction_level == 'Group':
            parent_curve_obj, object_part_mat_idxs = self.create_curve_obj(group_name, group)

            if self.level_is_greater_or_same(color_level, interaction_level):
                self.assign_material(parent_curve_obj, material)

        for cell_name in group["cells"].keys():

            if color_level == 'Cell':
                material = self.create_material(cell_name, group)

            if interaction_level == 'Cell':
                parent_curve_obj, object_part_mat_idxs = self.create_curve_obj(cell_name, group)

                if self.level_is_greater_or_same(color_level, interaction_level):
                    self.assign_material(parent_curve_obj, material)

            cell = group["cells"][cell_name]

            for section in cell:
                section_name = section["name"]
                coords = section["coords"]
                radii = section["radii"]

                if color_level == 'Section':
                    material = self.create_material(section_name, group)

                if interaction_level == 'Section':
                    parent_curve_obj, object_part_mat_idxs = self.create_curve_obj(section_name, group)

                    if self.level_is_greater_or_same(color_level, interaction_level):
                        self.assign_material(parent_curve_obj, material)

                self.add_spline(parent_curve_obj, coords, radii, smooth)

                if color_level == 'Segment':
                    mat_count = get_num_materials(coords)

                    for m in range(mat_count):
                        material = self.create_material(section_name+"["+str(m)+"]", group)
                        mat_idx = self.assign_material(parent_curve_obj, material)
                        poly_count = get_poly_count(m, res_u, res_bev, m == 0, m == (mat_count - 1))
                        object_part_mat_idxs.extend([mat_idx]*poly_count)

                    if interaction_level == 'Section':
                        self.assign_mats_to_polys(parent_curve_obj, object_part_mat_idxs)

                if color_level == 'Section' and interaction_level in ['Group', 'Cell']:
                    mat_idx = self.assign_material(parent_curve_obj, material)
                    object_part_mat_idxs.append(mat_idx)

            if color_level == 'Cell' and interaction_level == 'Group':
                mat_idx = self.assign_material(parent_curve_obj, material)
                object_part_mat_idxs.extend([mat_idx]*len(cell))

            if interaction_level == 'Cell':
                if color_level == 'Section':
                    self.assign_mats_to_splines(parent_curve_obj, object_part_mat_idxs)

                if color_level == 'Segment':
                    self.assign_mats_to_polys(parent_curve_obj, object_part_mat_idxs)

            self.progress_complete()

        if interaction_level == 'Group':
            if color_level in ['Cell', 'Section']:
                self.assign_mats_to_splines(parent_curve_obj, object_part_mat_idxs)

            if color_level == 'Segment':
                self.assign_mats_to_polys(parent_curve_obj, object_part_mat_idxs)

    def assign_mats_to_splines(self, parent_curve_obj, object_part_mat_idxs):
        parent_curve_obj.data.splines.foreach_set('material_index',object_part_mat_idxs)

    def assign_mats_to_polys(self, parent_curve_obj, object_poly_mat_idxs):
        mesh_obj = self.curve_to_mesh(parent_curve_obj)
        print(mesh_obj.data.polygons)
        print(object_poly_mat_idxs)
        mesh_obj.data.polygons.foreach_set("material_index", object_poly_mat_idxs)
        self.objects[mesh_obj.name] = {'object': mesh_obj, 'linked': False}

    def level_is_greater_or_same(self, color_level, interaction_level):
        return self.level_rank[color_level] >= self.level_rank[interaction_level]

    def assign_material(self, parent_curve_obj, material):
        mats = parent_curve_obj.data.materials
        mats.append(material)
        return len(mats)-1 # Return material index

    def create_material(self, mat_name, group):
        return create_default_material(group["color"], mat_name)

    def create_curve_obj(self, name, group_params):

        curve = self.blank_curve.copy()

        if group_params["as_lines"]:
            curve.bevel_depth = 0
        else:
            res_bev = get_res_bev(group_params["circular_subdivisions"])
            res_u = get_res_u(group_params["segment_subdivisions"])

            if res_bev != curve.bevel_resolution:
                curve.bevel_resolution = res_bev

            if res_u != curve.resolution_u:
                curve.resolution_u = res_u

        curve_obj = bpy.data.objects.new(name, curve)

        self.objects[name] = {'object': curve_obj, 'linked': False}

        object_poly_mat_idxs = []

        return (curve_obj, object_poly_mat_idxs)

    def add_coord_segment_materials(self, coords, sec_mesh_obj, res_u, res_bev):
        seg_count = get_num_materials(coords) # Extra caps don't count
        seg_cursor = 0

        # print(sec_mesh_obj.name + "coord seg count: " + str(seg_count))

        mesh_name = sec_mesh_obj.name
        color = self.solidColor
        mats = sec_mesh_obj.data.materials
        mat_indices = []
        resting_color = self.resting_color.tolist()

        for seg in range(seg_count):
            # Create a new material for the selected polygons
            name = mesh_name + "[" + str(seg) + "]"
            seg_mat = create_default_material(resting_color, name)
            mats.append(seg_mat)
            mat_index = len(mats) - 1

            poly_count = get_poly_count(seg_cursor, res_u, res_bev, seg == 0, seg == (seg_count - 1))
            mat_indices.extend([mat_index] * poly_count)
            seg_cursor += 1

        #assert(len(mats)==len(mat_names))
        #mats.foreach_set("name", mat_names)
        sec_mesh_obj.data.polygons.foreach_set("material_index", mat_indices)

    def assign_mat_index(self, mat_index, polys):
        for poly in polys:
            poly.material_index = mat_index

    def curve_to_mesh(self, sec_curve_obj):
        name = sec_curve_obj.name

        sec_mesh = sec_curve_obj.to_mesh(bpy.context.scene, apply_modifiers=False, settings='RENDER')

        # Remove old curve and it's object
        bpy.data.curves.remove(sec_curve_obj.data, do_unlink = True)
        # bpy.data.objects.remove(sec_curve_obj)

        sec_obj = bpy.data.objects.new(name, sec_mesh)


        return sec_obj

    def add_spline(self, curve_obj, coords, radii, smooth = False):
        sec_curve = curve_obj.data
        sec_spline = sec_curve.splines.new('BEZIER')

        # This line is necessary due to a bug in Blender see: https://developer.blender.org/T54112
        curve_obj.data.resolution_u = curve_obj.data.resolution_u

        bezier_points = sec_spline.bezier_points

        # Add closed caps
        first_coords = coords[:6]
        coords[0:0] = diam0version(first_coords[3:6], first_coords[0:3])
        radii.insert(0, 0)

        last_coords = coords[-6:]
        coords.extend(diam0version(last_coords[0:3], last_coords[3:6]))
        radii.append(0)

        # Spline comes with 1 pt, coords have len/3 pts
        bezier_points.add(len(coords)/3 - 1)

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

    def create_bezier_curve(self, cell, name, coords, radii, selectable_sections, res_bev, res_u, addCaps):

        # Create object for each section to make it selectable
        if selectable_sections:
            sec_curve = self.blank_curve.copy()
            sec_curve_obj = bpy.data.objects.new(name, sec_curve)

        # Otherwise only allow cell selection - reuse a cell object - create splines for each section
        else:
            # Create cell if it doesn't exist
            if cell not in bpy.data.objects:
                sec_curve = self.blank_curve.copy()
                sec_curve_obj = bpy.data.objects.new(cell, sec_curve)

            # Otherwise, reuse existing cell
            else:
                sec_curve_obj = bpy.data.objects[cell]
                sec_curve = sec_curve_obj.data

        sec_spline = sec_curve.splines.new('BEZIER')
        bezier_points = sec_spline.bezier_points

        # Add closed caps
        if addCaps:
            first_coords = coords[:6]
            coords[0:0] = diam0version(first_coords[3:6], first_coords[0:3])
            radii.insert(0, 0)

            last_coords = coords[-6:]
            coords.extend(diam0version(last_coords[0:3], last_coords[3:6]))
            radii.append(0)

        # Spline comes with 1 pt, coords have len/3 pts
        bezier_points.add(len(coords)/3 - 1)

        bezier_points.foreach_set('radius', radii)
        bezier_points.foreach_set('co', coords)
        bezier_points.foreach_set('handle_right', coords)
        bezier_points.foreach_set('handle_left', coords)

        return sec_curve_obj

    def get_res_u(self):
        return self.segment_subdivisions

    def get_res_bev(self):
        return (self.circular_subdivisions - 4) / 2.0

    def get_segment_polys(self, meshOB, seg_cursor, isFirstMeshSeg, isLastMeshSeg, res_bev, res_u):
        poly_ids = self.segmentFaces(seg_cursor, res_u, res_bev, isLast=isLastMeshSeg, isFirst=isFirstMeshSeg)
        polys = operator.itemgetter(*poly_ids)(meshOB.data.polygons)
        return polys

    def segmentFaces(self, iseg, res_u=2, res_bev=1, isFirst=False, isLast=False):
        face_count = res_u * (res_bev * 2 + 4)
        start_index = (iseg + 1) * face_count
        end_index_excl = start_index + face_count
        if isFirst:
            start_index = 0
        if isLast:
            end_index_excl = end_index_excl + face_count
        return range(int(start_index), int(end_index_excl))

    def link_objects(self):

        new_links = False

        # Ensure thread safety
        with self.link_lock:

            # Add any unlinked objects to the scene
            for obj in self.objects.values():
                if not obj["linked"]:
                    # On first export
                    if not self.has_linked:
                        self.on_first_link()
                        self.has_linked = True

                    # print('linking: ' + obj['object'].name)
                    bpy.context.scene.objects.link(obj['object'])
                    obj["linked"] = True

                    new_links = True


            if new_links:
                # Select all meshes and curves
                for ob in bpy.data.objects:
                    if ob.type in ['MESH','CURVE']:
                        ob.select = True

                # Reset their origins to center
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')

                self.show_full_scene()

    def set_clip_distance(self, distance = 100000):
        # For viewport
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_end = distance

        # For active camera, if any
        if "Camera" in bpy.data.cameras:
            bpy.data.cameras["Camera"].clip_end = distance

    def show_full_scene(self):
        # Unselect everything
        for ob in bpy.data.objects:
            ob.select = False

        # Select only the model objects
        for ob in self.objects.values():
            ob["object"].select = True

        # Show all model objects
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = {'area': area, 'region': region, 'edit_object': bpy.context.edit_object}
                        bpy.ops.view3d.view_selected(override, use_all_regions=False)
                        bpy.ops.view3d.camera_to_view(override)
                        break

        bpy.ops.object.select_all(action='TOGGLE')

    def clear(self):

        for object in self.objects.values():
            self.clear_model_object(object, removeFromSelf=False)

        self.objects = {}

    def clear_model_object(self, object, removeFromSelf = True):
        ob = object["object"]
        obType = ob.type

        try:
            bpy.context.scene.objects.unlink(ob)
        except:
            pass

        for mat in ob.data.materials:
            if mat is None:
                continue

            action_name = mat.name+'Action'

            if action_name in bpy.data.actions:
                bpy.data.actions.remove(bpy.data.actions[action_name])

            mat.animation_data_clear()
            bpy.data.materials.remove(mat)

        if obType == "CURVE":
            bpy.data.curves.remove(ob.data)

        elif obType == "MESH":
            bpy.data.meshes.remove(ob.data)

        bpy.data.objects.remove(ob, True)

        if removeFromSelf:
            self.objects.pop(ob.name)


    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def listenForExternal(self):
        from xmlrpc.server import SimpleXMLRPCServer
        from xmlrpc.server import SimpleXMLRPCRequestHandler
        from socketserver import ThreadingMixIn

        class BlenderServer(ThreadingMixIn, SimpleXMLRPCServer):
            def __init__(self, param):
                self.daemon_threads = True
                super(BlenderServer, self).__init__(param)

        self.server = BlenderServer((self.IP, self.Port))
        self.server.register_introspection_functions()

        def stop():
            self.stop()
            return 0

        self.server.register_function(stop, 'stop')

        def ping():
            return "I'm alive"

        self.server.register_function(ping, 'ping')

        def visualize_group(group):
            group = zlib.decompress(group)
            group = marshal.loads(group)
            self.progress_add(lambda: self.visualize_group(group), count=len(group["cells"]))
            return 0

        self.server.register_function(visualize_group, 'visualize_group')

        def create_cons(cons):
            self.progress_add(lambda: self.create_cons(cons), count=len(cons))
            return 0

        self.server.register_function(create_cons, 'create_cons')

        def link_objects():
            self.progress_add(lambda: self.link_objects())
            return 0

        self.server.register_function(link_objects, 'link_objects')

        def show_full_scene():
            self.progress_add(lambda: self.show_full_scene())
            return 0

        self.server.register_function(show_full_scene, 'show_full_scene')

        def set_segment_activities(segments):
            self.progress_add(lambda: self.set_segment_activities(segments),count=len(segments))
            return 0

        self.server.register_function(set_segment_activities, 'set_segment_activities')

        def set_segment_activity(name, times, activity):
            self.progress_add(lambda: self.set_segment_activity(name, times, activity))
            return 0

        self.server.register_function(set_segment_activity, 'set_segment_activity')

        def clear():
            self.queue.put(lambda: self.clear())
            return 0

        self.server.register_function(clear, 'clear')

        self.server.register_function(self.progress_start, 'progress_start')
        self.server.register_function(self.progress_get_done, 'progress_get_done')
        self.server.register_function(self.progress_get_total, 'progress_get_total')

        self.server.serve_forever()


cimport cython

cdef inline int get_num_materials(coords):
    # Div by 3: Each coord has x,y,z locations
    # -1: Number of segments is points - 1
    # -2: Two extra points are added to create 0-radius end-caps
    return len(coords) / 3 - 1 - 2

cdef inline int get_res_u(int segment_subdivisions):
    return segment_subdivisions

cdef inline int get_res_bev(int circular_subdivisions):
    return int((circular_subdivisions - 4) / 2.0)

@cython.profile(False)
cdef inline diam0version(start, end):
        start = np.array(start)
        end = np.array(end)
        lengths = end - start
        extended = start + lengths * 1.001  # Extend by a small amount
        result = extended.tolist()
        return result

@cython.profile(False)
cdef inline create_default_material(color, name = "SolidColor"):
    result = blenderpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_transparency = True
    result.alpha = 0.8
    result.emit = 1.0
    return result

@cython.profile(False)
cdef inline int get_poly_count(int iseg, int res_u=2, int res_bev=1, bint isFirst=False, bint isLast=False):
    cdef int face_count, start_index, end_index_excl

    face_count = res_u * (res_bev * 2 + 4)
    start_index = (iseg + 1) * face_count
    end_index_excl = start_index + face_count
    if isFirst:
        start_index = 0
    if isLast:
        end_index_excl = end_index_excl + face_count

    return int(end_index_excl-start_index)