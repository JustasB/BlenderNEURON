# distutils: define_macros=CYTHON_TRACE=1
# cython: profile=True

import numpy as np

import bmesh, operator, bpy, threading, queue, marshal, zlib, traceback, time, re, inspect, colors
from math import sqrt, radians, atan, tan, degrees
from statistics import mean

class NeuroServer:

    def __init__(self, global_name = "BN"):

        if global_name:
            globals()[global_name] = self

        self.IP = "127.0.0.1" #"192.168.0.34"
        self.Port = 8000

        self.resting_color = np.array((30/255.0, 138/255.0, 112/255.0))   # Tinted bluish green
        self.active_color = np.array((0.992, 0.455, 0))                   # Tinted redish yellow
        self.color_dist = self.active_color - self.resting_color

        self.background_zenith_color = (0,0.040,0.070)           # Shaded greenish blue
        self.background_horizon_color = (0,0.008, 0.010)        # Darker zenith

        self.ui_background_zenith_color = (0,0.22,0.294)           # Shaded greenish blue
        self.ui_background_horizon_color = (0,0.086, 0.098)        # Darker zenith

        self.ttc_name = "CameraTrackToConstraint"
        self.fpc_name = "CameraFollowPathConstraint"

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

        self.camera = bpy.data.objects["Camera"]

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

        self.task_lock = threading.Lock()
        self.tasks = {}
        self.task_next_id = 0

        self.queue = queue.Queue()
        self.progress_start()

    def run_command(self, command_string):
        exec_lambda = self.get_command_lambda()
        return self.run_lambda(exec_lambda)

    def enqueue_command(self, command_string):
        exec_lambda = self.get_command_lambda()
        return self.enqueue_lambda(exec_lambda)

    def run_method(self, method, args, kwargs):
        task_lambda = lambda: getattr(self, method)(*args, **kwargs)

        return self.run_lambda(task_lambda)

    def enqueue_method(self, method, args, kwargs):
        task_lambda = lambda: getattr(self, method)(*args, **kwargs)

        return self.enqueue_lambda(task_lambda)

    def get_command_lambda(self, command_string):
        def exec_lambda():
            return_value = None
            exec("return_value = " + command_string)
            return return_value

        return exec_lambda

    def get_method_lambda(self, method, *args, **kwargs):

        # Retrieve the default values from method definition and pass them along if they're not set
        method_arg_spec = inspect.getargspec(getattr(self, method))
        default_args = dict(zip(method_arg_spec.args[-len(method_arg_spec.defaults):], method_arg_spec.defaults))
        for arg in default_args:
            if arg not in kwargs:
                kwargs[arg] = default_args[arg]

        task_lambda = lambda: getattr(self, method)(*args, **kwargs)
        return task_lambda

    def run_lambda(self, task_lambda):
        id = self.enqueue_lambda(task_lambda)

        while self.get_task_status(id) == 'QUEUED':
            time.sleep(0.1)

        status = self.get_task_status(id)

        if status == "SUCCESS":
            return self.tasks[id]["result"]

        else:
            raise Exception(self.tasks[id]["error"])

    def enqueue_lambda(self, task_lambda):
        task_id = self.get_new_task_id()

        task = {"id": task_id, "status": "QUEUED", "lambda": task_lambda, "result": None, "error": None}

        self.tasks[task_id] = task
        self.queue.put(task)

        return task_id

    def get_new_task_id(self):
        with self.task_lock:
            task_id = self.task_next_id
            self.task_next_id += 1

        return task_id

    def get_task_status(self, task_id):
        if task_id in self.tasks:
            return self.tasks[task_id]["status"]

        return "DOES_NOT_EXIST"

    def get_task_error(self, task_id):
        return self.tasks[task_id]["error"]

    def get_task_result(self, task_id):
        return self.tasks[task_id]["result"]

    def work_on_queue_tasks(self):
        q = self.queue
        
        while not q.empty():
            print_safe("Tasks in queue. Getting next task...")
            task = q.get()

            try:
                if not self.queue_error:
                    print_safe("Running task...")
                    result = task["lambda"]()
                    task["result"] = result
                    task["status"] = "SUCCESS"
                else:
                    print_safe("Previous task had an error. SKIPPING.")
                    task["status"] = "ERROR"

            except:
                self.queue_error = True
                tb = traceback.format_exc()

                task["status"] = "ERROR"
                task["error"] = tb

                print_safe(tb)

            print_safe("Marking task as done")
            q.task_done()
            print_safe("MARKED DONE")

    def service_queue(self):
        q = self.queue

        if not q.empty():
            print_safe("TASKS FOUND")

            self.queue_error = False
            self.queue_servicer = threading.Thread(target=self.work_on_queue_tasks)
            self.queue_servicer.daemon = True

            self.queue_servicer.start()

            q.join()
            print_safe("Task queue DONE")

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
        seg_mat = bpy.data.materials[name]

        intensity = list(map(self.activity_to_intensity, activity))

        for t in range(len(times)):
            seg_mat.emit = intensity[t]
            seg_mat.keyframe_insert(data_path="emit", frame=int(times[t]))

        self.progress_complete()

    def activity_to_intensity(self, activity, min_range = -50.0, max_range =   0.0):

        # Normalize to 0-1
        return max(min((activity - min_range) / (max_range - min_range), 1.0), 0.0)

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
                spherical = section["spherical"] if "spherical" in section else False

                if color_level == 'Section':
                    material = self.create_material(section_name, group)

                if interaction_level == 'Section':
                    parent_curve_obj, object_part_mat_idxs = self.create_curve_obj(section_name, group)

                    if self.level_is_greater_or_same(color_level, interaction_level):
                        self.assign_material(parent_curve_obj, material)

                self.add_spline(parent_curve_obj, coords, radii, smooth)

                if color_level == 'Segment':
                    mat_count = get_num_materials(coords)

                    if spherical:
                        seg_count = mat_count
                        mat_count = 1

                    for m in range(mat_count):
                        material = self.create_material(section_name+"["+str(m)+"]", group)
                        mat_idx = self.assign_material(parent_curve_obj, material)

                        if spherical:
                            poly_count = get_spherical_poly_count(seg_count, res_u, res_bev)
                        else:
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

        # Clear selection
        self.all_select(select=False)


    def set_clip_distance(self, distance = 100000):
        # For viewport
        for a in bpy.data.screens["Default"].areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_end = distance

        # For active camera, if any
        if "Camera" in bpy.data.cameras:
            bpy.data.cameras["Camera"].clip_end = distance

    def get_operator_context_override(self, selected_object = None):
        # override = bpy.context.copy()
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

    def set_camera_lock(self, lock):
        for area in bpy.data.screens["Default"].areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.lock_camera = lock

    def all_select(self, select):
        for ob in bpy.data.objects:
            ob.select = select

    def get_current_view_perspective(self):
        for area in bpy.data.screens["Default"].areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.region_3d.view_perspective

    def show_full_scene(self):
        # Clear selection
        self.all_select(select=False)

        # Select only the model objects
        for ob in self.objects.values():
            ob["object"].select = True

        # Change to camera view (if not already)
        if self.get_current_view_perspective() == 'PERSP':
            bpy.ops.view3d.viewnumpad(self.get_operator_context_override(), type='CAMERA')

        # Start with a camera that faces the front of the object
        self.camera.location = (7,7,7)
        self.camera.rotation_euler = (radians(53),0,radians(134))

        #Lock camera to view
        self.set_camera_lock(lock=True)

        #Fill screen with camera view
        bpy.ops.view3d.view_center_camera(self.get_operator_context_override())

        # Show all model objects
        bpy.ops.view3d.view_selected(self.get_operator_context_override(), use_all_regions=False)

        # Change back to perspective view
        if self.get_current_view_perspective() == 'CAMERA':
            bpy.ops.view3d.viewnumpad(self.get_operator_context_override(), type='CAMERA')

        # Unlock camera
        self.set_camera_lock(lock=False)

        # Clear selection
        self.all_select(select=False)

    def set_render_params(self, frame_range = (0, 200), width = 500, height = 500, file_format = 'JPEG', format_param = 93):
        scene = bpy.data.scenes["Scene"]

        scene.frame_start = frame_range[0]
        scene.frame_end = frame_range[1]

        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100

        scene.render.image_settings.file_format = file_format

        if file_format.startswith('JPEG'):
            scene.render.image_settings.quality = format_param

        if file_format.startswith('PNG'):
            scene.render.image_settings.compression = format_param

    def render_animation(self, destination_path):
        scene = bpy.data.scenes["Scene"]

        # Set render params
        if not destination_path.endswith("/"):
            destination_path += "/"

        scene.render.filepath = destination_path

        # Run render
        bpy.ops.render.render(self.get_operator_context_override(), animation=True)


    def orbit_camera_around_model(self, orbit_incline_angle = 15.0, animation_length = 200):
        # Run with: bpy.types.Object.neuron_server.orbit_camera_around_model()

        # Create a circular camera trajectory  - if haven't already
        if not hasattr(self, "camera_trajectory") or not self.camera_trajectory:
            bpy.ops.curve.primitive_nurbs_circle_add(location=(0.0, 0.0, 0.0))
            self.camera_trajectory  = bpy.data.objects['NurbsCircle']
            self.camera_trajectory.name = "CameraTrajectory"            
            bpy.context.scene.objects.active = self.camera_trajectory

            # For some reason the curve is in edit mode after creation and needs to be flipped
            bpy.ops.object.mode_set(self.get_operator_context_override(self.camera_trajectory), mode = 'EDIT')

        radius = self.get_whole_view_camera_distance()

        # Make it large enough to fit whole scene and angle it a bit
        self.camera_trajectory.scale = (radius, radius, 1)
        self.camera_trajectory.rotation_euler = (0.0, radians(orbit_incline_angle), 0.0)

        # Set the number of frames to use for the animation     
        self.camera_trajectory.data.path_duration = animation_length

        # Create a camera target at the object center
        if not hasattr(self, "camera_target") or not self.camera_target:
            bounds = self.get_model_bounds()

            center = (
                mean([bounds["mins"][0], bounds["maxes"][0]]),
                mean([bounds["mins"][1], bounds["maxes"][1]]),
                mean([bounds["mins"][2], bounds["maxes"][2]]),
            )

            bpy.ops.object.empty_add(type='SPHERE',
                                 radius=0.001,
                                 location=center)

            self.camera_target  = bpy.data.objects["Empty"]
            bpy.context.scene.objects.active = self.camera_target
            self.camera_target.name = "CameraTarget"


        # Assign camera to move along the trajectory (must be before track_to)
        bpy.context.scene.objects.active = self.camera
        self.camera.location = (0,0,0)
        self.camera.rotation_euler = (radians(90),0,0)



        if self.fpc_name not in self.camera.constraints:
            fpc = self.camera.constraints.new(type="FOLLOW_PATH")
            fpc.target = self.camera_trajectory
            fpc.use_curve_follow = True
            fpc.forward_axis = 'FORWARD_Y'
            fpc.up_axis = 'UP_Z'
            fpc.name = self.fpc_name

            # Animate the camera path
            bpy.ops.constraint.followpath_path_animate({"constraint":fpc, "object":self.camera},constraint=fpc.name)

            self.camera_trajectory.data.path_duration = animation_length

        # Assign camera to point at the model  (must be after follow_path)

        if self.ttc_name not in self.camera.constraints:
            ttc = self.camera.constraints.new(type="TRACK_TO")
            ttc.target = self.camera_target
            ttc.track_axis = 'TRACK_NEGATIVE_Z'
            ttc.up_axis = 'UP_Y'
            ttc.name = self.ttc_name

    def get_model_bounds(self):
        from mathutils import Vector
        corners = []

        for bn_object in self.objects.values():
            b_object = bn_object["object"]

            # Convert bound_box object-space coords to world-space coords
            for corner in b_object.bound_box:
                corners.append(b_object.matrix_world * Vector(corner))

        mins = []
        maxes = []
        ranges = []

        for d in range(3):
            maxes.append(max(c[d] for c in corners))
            mins.append(min(c[d] for c in corners))
            ranges.append(maxes[-1] - mins[-1])

        return { "mins": mins, "maxes": maxes, "ranges": ranges }

    def get_camera_hv_angles(self):
        camera_angle_rad = bpy.data.cameras[self.camera.name].angle

        cam_width = bpy.data.scenes["Scene"].render.resolution_x
        cam_height = bpy.data.scenes["Scene"].render.resolution_y

        max_dim = max(cam_height, cam_width)
        min_dim = min(cam_height, cam_width)

        aspect_ratio = min_dim / max_dim

        smaller_angle = 2*atan(aspect_ratio*tan(camera_angle_rad/2.0))

        if cam_width == max_dim:
            return { "h": camera_angle_rad, "v": smaller_angle }

        else:
            return { "h": smaller_angle, "v": camera_angle_rad }

    def get_whole_view_camera_distance(self):

        # Use camera angle, resolution w/h, and model bounding box dims
        # To find such cam dist that whole model would be visible
        model_bounds = self.get_model_bounds()
        camera_angles = self.get_camera_hv_angles()

        # x and y must fit within width
        h_range = max(model_bounds["ranges"][0], model_bounds["ranges"][1])

        # z must fit within cam height
        v_range = model_bounds["ranges"][2]

        # depth range is the narrower of x and y ranges
        depth_range = min(model_bounds["ranges"][0], model_bounds["ranges"][1])

        from math import tan
        dist_to_fit_h_range = (h_range / 2.0) / tan(camera_angles["h"] / 2.0) + (depth_range / 2.0)
        dist_to_fit_v_range = (v_range / 2.0) / tan(camera_angles["v"] / 2.0) + (depth_range / 2.0)

        # max of width dist and height dist is the cam dist
        cam_dist = max(dist_to_fit_h_range, dist_to_fit_v_range)

        return cam_dist


    def clear(self):

        for object in self.objects.values():
            self.clear_model_object(object, removeFromSelf=False) # Will remove below

        self.objects = {}

        if self.ttc_name in self.camera.constraints:
            self.camera.constraints.remove(self.camera.constraints[self.ttc_name])

        if self.fpc_name in self.camera.constraints:
            self.camera.constraints.remove(self.camera.constraints[self.fpc_name])

        # Clear any camera orbits
        if hasattr(self, "camera_target") and self.camera_target:
            self.clear_model_object(self.camera_target, removeFromSelf = False)
            self.camera_target = None

        if hasattr(self, "camera_trajectory") and self.camera_trajectory:
            self.clear_model_object(self.camera_trajectory, removeFromSelf = False)
            self.camera_trajectory = None

    def color_by_unique_materials(self):
        mat_names = set()
        regex = re.compile(r"(\d|_|]|\[|\.)")

        for mat in bpy.data.materials:
            clean_name = regex.sub("", mat.name)
            mat_names.add(clean_name)

        color_palette = colors.get_distinct(len(mat_names))

        # Assign each clean name to a color
        mat_colors = dict(zip(mat_names,color_palette))

        # Assign sections to a color
        for mat in bpy.data.materials:
            clean_name = regex.sub("", mat.name)
            if clean_name in mat_colors:
                mat.diffuse_color = mat_colors[clean_name]

    def clear_model_object(self, object, removeFromSelf = True):
        if object.__class__.__name__ == 'dict':
            ob = object["object"]
        else:
            ob = object

        obType = ob.type

        try:
            bpy.context.scene.objects.unlink(ob)
        except:
            pass

        if hasattr(ob.data, "materials"):
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
        return 0

    def ping(self):
        return "I'm alive"

    def listenForExternal(self):
        from xmlrpc.server import SimpleXMLRPCServer
        from xmlrpc.server import SimpleXMLRPCRequestHandler
        from socketserver import ThreadingMixIn

        class BlenderServer(ThreadingMixIn, SimpleXMLRPCServer):
            def __init__(self, param):
                self.daemon_threads = True
                super(BlenderServer, self).__init__(param, allow_none=True)

        self.server = BlenderServer((self.IP, self.Port))
        self.server.register_introspection_functions()

        # Basic server functions
        self.server.register_function(self.stop, 'stop')
        self.server.register_function(self.ping, 'ping')

        # Synchronous execution
        self.server.register_function(self.run_command, 'run_command')
        self.server.register_function(self.run_method,  'run_method')

        # Asynchronous task execution queueing
        self.server.register_function(self.enqueue_method,  'enqueue_method')
        self.server.register_function(self.enqueue_command, 'enqueue_command')
        self.server.register_function(self.get_task_status, 'get_task_status')
        self.server.register_function(self.get_task_error,  'get_task_error')
        self.server.register_function(self.get_task_result, 'get_task_result')

        self.server.serve_forever()


cimport cython

cdef inline hex_to_rgb(value):
    gamma = 2.2
    value = value.lstrip('#')
    lv = len(value)
    fin = list(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    r = pow(fin[0] / 255, gamma)
    g = pow(fin[1] / 255, gamma)
    b = pow(fin[2] / 255, gamma)
    fin.clear()
    fin.append(r)
    fin.append(g)
    fin.append(b)
    return tuple(fin)

cdef inline print_safe(value):
    try:
        print(value)
    except:
        tb = traceback.format_exc()
        print(tb)

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

        # Simple extension
        # extended = start + lengths * 1.001  # Extend by a small amount

        # Versor extension
        length = sqrt(np.power(lengths,2).sum())
        versor = lengths / length
        extended = end + versor * 0.01 # Extend in the same direction by a small amount

        result = extended.tolist()
        return result

@cython.profile(False)
cdef inline create_default_material(color, name = "SolidColor"):
    result = bpy.data.materials.new(name)
    result.diffuse_color = color

    # Ambient and back lighting
    result.ambient = 0.85
    result.translucency = 0.85

    # Raytraced reflections
    result.raytrace_mirror.use = True
    result.raytrace_mirror.reflect_factor = 0.1
    result.raytrace_mirror.fresnel = 2.0

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

cdef inline int get_spherical_poly_count(int seg_count, int res_u, int res_bev):
    # Get spherical bevelled bezier polygons by:
    iseg = seg_count-1 # Get the polygons of the last sphere segment
    isLast = True # Include the final end-cap
    isFirst = True # Include the start end-cap (and everything up to the last segment)

    result = get_poly_count(iseg, res_u, res_bev, isFirst=isFirst, isLast=isLast)

    return result



