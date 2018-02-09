import bpy as blenderpy
import numpy as np
import bmesh, operator, bpy, threading, queue

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

        # Clear scene
        try:
            bpy.data.objects.remove(bpy.data.objects["Cube"])
        except:
            pass

        try:
            bpy.data.objects.remove(bpy.data.objects["Lamp"])
        except:
            pass



        # Expand the clip area
        self.set_clip_distance()

        # Resting color
        self.solidColor = self.bpy.data.materials.new("SolidColor")
        self.solidColor.diffuse_color = self.resting_color.tolist()
        self.solidColor.use_transparency = True
        self.solidColor.alpha = 0.8
        self.solidColor.emit = 1.0


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

        self.objects = []
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

    def make_paths(self, paths):
        for path in paths:
            self.create_path(path)

    def create_path(self,sections, res_bev = None, res_u = None, addCaps = True):
        if res_bev is None:
            res_bev = self.get_res_bev()

        if res_u is None:
            res_u = self.get_res_u()

        for section in sections:
            coords = section["coords"]
            name = section["name"]

            # Create bezier curve from coordinates
            sec_curve_obj = self.create_bezier_curve(name, coords, res_bev, res_u, addCaps)

            # Convert bezier to mesh
            sec_mesh_obj = self.curve_to_mesh(sec_curve_obj, name)

            # Manage the mesh object as part of the model
            self.objects.append({'object': sec_mesh_obj, 'linked': False})

            # Add materials to each coord segment
            self.add_coord_segment_materials(coords, sec_mesh_obj, res_u, res_bev)

        self.progress_complete()

    def add_coord_segment_materials(self, coords, sec_mesh_obj, res_u, res_bev):
        seg_count = len(coords) - 1 - 2 # Extra caps don't count
        seg_cursor = 0

        print(sec_mesh_obj.name + "coord seg count: " + str(seg_count))

        for seg in range(seg_count):
            name = sec_mesh_obj.name + "[" + str(seg) + "]"

            # collect the segment polygons
            polys = self.get_segment_polys(sec_mesh_obj, seg_cursor, seg == 0, seg == (seg_count - 1), res_bev, res_u)

            # Create a new material for the selected polygons
            seg_mat = self.solidColor.copy()
            seg_mat.name = name
            sec_mesh_obj.data.materials.append(seg_mat)
            mat_index = len(sec_mesh_obj.data.materials)-1

            # Assign that material to the polygons
            for poly in polys:
                poly.material_index = mat_index

            seg_cursor += 1

    def curve_to_mesh(self, sec_curve_obj, name):
        sec_mesh = sec_curve_obj.to_mesh(bpy.context.scene, apply_modifiers=False, settings='RENDER')
        sec_obj = bpy.data.objects.new(name, sec_mesh)
        # Remove old curve and it's object
        bpy.data.curves.remove(sec_curve_obj.data)
        bpy.data.objects.remove(sec_curve_obj)
        return sec_obj

    def create_bezier_curve(self, name, coords, res_bev, res_u, addCaps):
        sec_curve = bpy.data.curves.new(name, type='CURVE')
        sec_spline = sec_curve.splines.new('BEZIER')
        sec_curve_obj = bpy.data.objects.new(name+"_curve", sec_curve)

        # Add closed caps
        if addCaps:
            first_coords = coords[:2]
            coords.insert(0, self.diam0version(first_coords[1], first_coords[0]))
            last_coords = coords[-2:]
            coords.append(self.diam0version(last_coords[0], last_coords[1]))

        sec_spline.bezier_points.add(len(coords) - 1)
        for s, coord in enumerate(coords):
            bpoint = sec_spline.bezier_points[s]
            bpoint.co = coord[:3]
            bpoint.radius = coord[3] / 2.0
            bpoint.handle_left_type = bpoint.handle_right_type = 'AUTO'

        sec_curve.dimensions = '3D'
        sec_curve.resolution_u = res_u  # Segment subdivisions
        sec_curve.fill_mode = 'FULL'
        sec_curve.bevel_depth = 1.0
        sec_curve.bevel_resolution = res_bev  # Circular subdivisions

        return sec_curve_obj

    def get_res_u(self):
        return self.segment_subdivisions

    def get_res_bev(self):
        return (self.circular_subdivisions - 4) / 2.0

    def diam0version(self, start, end):
        start = np.array(start[0:3])
        end = np.array(end[0:3])
        lengths = end - start
        extended = start + lengths * 1.001  # Extend by a small amount
        result = extended.tolist()
        result.append(0)
        return result

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
            for obj in self.objects:
                if not obj["linked"]:
                    # On first export
                    if not self.has_linked:
                        self.on_first_link()
                        self.has_linked = True

                    print('linking: ' + obj['object'].name)
                    bpy.context.scene.objects.link(obj['object'])
                    obj["linked"] = True

                    new_links = True


            if new_links:
                # Select all meshes
                bpy.ops.object.select_by_type(type='MESH')

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
        for ob in self.objects:
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

        for object in self.objects:
            self.clear_model_object(object, removeFromSelf=False)

        self.objects = []

    def clear_model_object(self, object, removeFromSelf = True):
        ob = object["object"]
        obType = type(ob.data).__name__

        try:
            bpy.context.scene.objects.unlink(ob)
        except:
            pass

        for mat in ob.data.materials:
            action_name = mat.name+'Action'

            if action_name in bpy.data.actions:
                bpy.data.actions.remove(bpy.data.actions[action_name])

            mat.animation_data_clear()
            bpy.data.materials.remove(mat)

        if obType == "Curve":
            bpy.data.curves.remove(ob.data)

        elif obType == "Mesh":
            bpy.data.meshes.remove(ob.data)

        bpy.data.objects.remove(ob, True)

        if removeFromSelf:
            self.objects.remove(ob)


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

        def create_path(sections):
            print("Adding path... queue size: " + str(self.queue.qsize()))
            self.progress_add(lambda: self.create_path(sections))
            print("Added. queue size: " + str(self.queue.qsize()))
            return 0

        self.server.register_function(create_path, 'create_path')

        def make_paths(paths):
            self.progress_add(lambda: self.make_paths(paths), count=len(paths))
            return 0

        self.server.register_function(make_paths, 'make_paths')

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
            print("Clearing... queue size: " + str(self.queue.qsize()))
            self.queue.put(lambda: self.clear())
            self.queue.put(lambda: self.progress_start())

            print("Cleared. queue size: " + str(self.queue.qsize()))
            return 0

        self.server.register_function(clear, 'clear')

        self.server.register_function(self.progress_start, 'progress_start')
        self.server.register_function(self.progress_get_done, 'progress_get_done')
        self.server.register_function(self.progress_get_total, 'progress_get_total')

        self.server.serve_forever()
