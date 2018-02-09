import xmlrpclib, threading, time
from math import sqrt

class BlenderNEURON(object):
    def __init__(self, h, ip = '192.168.0.34', port = '8000', collect_activity = True, roots_to_collect = []):
        self.h = h
        self.client = xmlrpclib.ServerProxy('http://'+ip+':'+port)
        self.progress_client = xmlrpclib.ServerProxy('http://' + ip + ':' + port)
        self.activity_simplification_tolerance = 0.32 # mV

        if collect_activity or len(roots_to_collect) > 0:
            self.collector_stim = self.h.NetStim(0.5)
            self.collector_stim.start = 0
            self.collector_stim.interval = 1
            self.collector_stim.number = 1e9
            self.collector_stim.noise = 0

            self.collector_con = self.h.NetCon(self.collector_stim, None)
            self.collector_con.record(self.collect)

            # Collect from all segments by default
            if len(roots_to_collect) == 0:
                self.roots_to_collect = self.h.SectionList()
                self.roots_to_collect.allroots()
            else:
                self.roots_to_collect = roots_to_collect

        self.clear_activity()

        # Clear previously recorded activity on h.run()
        self.fih = self.h.FInitializeHandler(self.clear_activity)

        self.progressNEURON = self.h.ref('0.0')
        self.progressBlender = self.h.ref('0.0')
        self.progressPercent = self.h.ref('0.0')
        self.include_cells = True
        self.include_connections = True
        self.include_activity = True
        self.show_panel()

    def show_panel(self):
        self.h.xpanel('BlenderNEURON')

        self.h.xcheckbox('Include Cells', (self, 'include_cells'))
        self.h.xcheckbox('Include Connections', (self, 'include_connections'))
        self.h.xcheckbox('Include Activity', (self, 'include_activity'))
        self.h.xbutton('Send To Blender', self.send_model_threaded)

        self.h.xlabel('Progress:')
        self.h.xvarlabel(self.progressNEURON)
        self.h.xvarlabel(self.progressBlender)
        self.h.xvarlabel(self.progressPercent)

        self.h.xpanel(500, 10)

    def clear_activity(self):
        self.segment_activity = {}
        self.collection_times = []

    def send_model_threaded(self):
        self.send_thread = threading.Thread(target=self.send_model)
        self.send_thread.daemon = True

        self.blender_progress_thread = threading.Thread(target=self.get_blender_progress)
        self.blender_progress_thread.daemon = True

        self.progress_client.progress_start()
        self.send_thread.start()
        self.blender_progress_thread.start()

        # self.send_thread.join()
        # self.blender_progress_thread.join()

    def get_blender_progress(self):
        def update():
            sent = self.progress_client.progress_get_total()
            done = self.progress_client.progress_get_done()

            self.progressNEURON[0] = 'Sent: ' + str(sent)
            self.progressBlender[0] = 'Completed: ' + str(done)

            if sent > 0:
                self.progressPercent[0] = ("%.2f" % ((done*1.0)/sent*100))+'%'

            return (sent, done)

        sent, done = update()

        while sent == 0 or sent != done:
            time.sleep(0.5)
            sent, done = update()

        sent, done = update()

        return 0

    def send_model(self):
        # Remove any previous model objects
        self.client.clear()

        if self.include_cells:
            self.send_cells()

        if self.include_connections:
            self.send_cons()

        if self.include_activity:
            self.send_activity()

    def send_cons(self):

        cons = []

        for i, con in enumerate(self.h.NetCon):
            pre = con.pre()
            post = con.syn()

            # If source is PointProcess
            if pre is not None:
                # A PointProcess with a segment
                if hasattr(pre, "get_segment"):
                    pre_seg = pre.get_segment()

                # Skip if the PP doesn't have a segment
                else:
                    continue

            else:
                pre_loc = con.preloc()

                # If source is a segment
                if pre_loc != -1.0:
                    pre_seg = self.h.cas()(pre_loc) # TEST THIS
                    self.h.pop_section()

                # Skip if it's neither a PP nor a segment
                else:
                    continue

            # Check if post is a PointProcess on a Section
            if post is None or hasattr(post, "get_segment") == False:
                continue

            pre_pos = self.get_coords_along_sec(pre_seg.sec, pre_seg.x)

            post_seg = post.get_segment()
            post_pos = self.get_coords_along_sec(post_seg.sec, post_seg.x)

            cons.append({
                "name":"NetCon["+str(i)+"]",
                "from":pre_pos,
                "to": post_pos
            })

        self.client.create_cons(cons)


    def get_coords_along_sec(self, section, along):
        coord_count = self.h.n3d(sec=section)
        along_coords = (coord_count-1) * along
        start_coord_i = int(along_coords)
        along_start_coord = along_coords - start_coord_i

        if along_start_coord > 0:
            along_x = self.get_along_coord_dim("x", section, start_coord_i, along_start_coord)
            along_y = self.get_along_coord_dim("y", section, start_coord_i, along_start_coord)
            along_z = self.get_along_coord_dim("z", section, start_coord_i, along_start_coord)

        else:
            along_x = self.h.x3d(start_coord_i, sec=section)
            along_y = self.h.y3d(start_coord_i, sec=section)
            along_z = self.h.z3d(start_coord_i, sec=section)

        return (along_x,along_y,along_z)


    def get_along_coord_dim(self, dim, section, coord_i, along_start_coord):
        dim = getattr(self.h,dim+"3d")
        start = dim(coord_i, sec=section)
        end = dim(coord_i + 1, sec=section)
        length = end - start
        along = start + along_start_coord * length
        return along

    def send_cells(self, roots_to_send = None):
        if roots_to_send is None:
            self.roots = self.h.SectionList()
            self.roots.allroots()
        else:
            self.roots = roots_to_send

        root_paths = []
        for root in self.roots:
            self.gather_section_paths(root, root_paths)

            if len(root_paths) > 10:
                self.client.make_paths(root_paths)
                root_paths = []

        if len(root_paths) > 0:
            self.client.make_paths(root_paths)

    def send_root(self, root):
        root_paths = []
        self.gather_section_paths(root, root_paths)
        self.client.make_paths(root_paths)

    def gather_section_paths(self, rootSection, paths, current_path = None):
        # Determine how many 3d points the section has
        coordCount = int(self.h.n3d(sec=rootSection))

        # Let NEURON create them if missing
        if coordCount == 0:
            self.h.define_shape(sec=rootSection)
            coordCount = int(self.h.n3d(sec=rootSection))

        # Collect the coordinates
        section_coords = []
        for i in range(coordCount):
            section_coords.append(self.get_coord(rootSection, i))

        # Associate the coords with the section name
        if current_path is None:
            current_path = []

        current_path.append({
            "name":rootSection.name(),
            "coords": section_coords
        })

        children = rootSection.children()
        num_children = len(children)


        continued = False
        for c in range(num_children):
            child = children[c]

            if int(self.h.n3d(sec=child)) <= 0:
                self.h.define_shape(sec=child)

            # Continuations are child segments whose first coord pos is identical to the parent's last coord pos
            isContinuation = self.get_coord(child, 0)[:3] == section_coords[-1][:3]

            # If child is the first continuation, pass along the coords so far
            if isContinuation and not continued:
                self.gather_section_paths(child, paths, current_path=current_path)
                continued = True

            # Otherwise start a new path
            else:
                self.gather_section_paths(child, paths)

        # If this sec has no more continuations, terminate it
        if not continued:
            #print("r.create_path("+ str(path_coords) +")")
            #self.client.create_path(path)
            paths.append(current_path)

    def get_coord(self, section, i):
        return (
            self.h.x3d(i, sec=section),
            self.h.y3d(i, sec=section),
            self.h.z3d(i, sec=section),
            self.h.diam3d(i, sec=section)
        )



    def collect(self, variable="v"):
        self.collection_times.append(self.h.t)

        for root in self.roots_to_collect:
            self.collect_recursive(root, variable)

    def collect_recursive(self, rootSection, variable="v"):
        coordCount = int(self.h.n3d(sec=rootSection))

        for i in range(1, coordCount):
            startL = self.h.arc3d(i - 1, sec=rootSection)
            endL = self.h.arc3d(i, sec=rootSection)
            vectorPos = (endL + startL) / 2.0 / rootSection.L

            segment_name = rootSection.name() + "[" +  str(i-1) + "]"

            if segment_name in self.segment_activity:
                values = self.segment_activity[segment_name]
            else:
                values = self.segment_activity[segment_name] = []

            value = getattr(rootSection(vectorPos), variable)
            values.append(value)

        for child in rootSection.children():
            self.collect_recursive(child, variable)

    def send_activity(self):
        if self.segment_activity is None:
            return

        segments = []

        for seg in self.segment_activity:
            reduced_times, reduced_values = self.simplify_activity(self.segment_activity[seg])

            segments.append({'name':seg, 'times':reduced_times, 'activity':reduced_values})

            # Buffered send
            if len(segments) > 100:
                self.client.set_segment_activities(segments)
                segments = []

        self.client.set_segment_activities(segments)

    def simplify_activity(self, activity):
        reduced = BlenderNEURON.rdp(zip(self.collection_times, activity), self.activity_simplification_tolerance)
        return zip(*reduced)

    @staticmethod
    def distance(a, b):
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @staticmethod
    def point_line_distance(point, start, end):
        if (start == end):
            return BlenderNEURON.distance(point, start)
        else:
            n = abs(
                (end[0] - start[0]) * (start[1] - point[1]) - (start[0] - point[0]) * (end[1] - start[1])
            )
            d = sqrt(
                (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2
            )
            return n / d

    # Reduces a series of points to a simplified version that loses detail, but maintains the general shape of the series
    # Ramer-Douglas-Peucker algorithm
    # Adapted from: https://github.com/sebleier/RDP
    @staticmethod
    def rdp(points, epsilon):
        dmax = 0.0
        index = 0
        for i in range(1, len(points) - 1):
            d = BlenderNEURON.point_line_distance(points[i], points[0], points[-1])
            if d > dmax:
                index = i
                dmax = d
        if dmax >= epsilon:
            results = BlenderNEURON.rdp(points[:index + 1], epsilon)[:-1] + BlenderNEURON.rdp(points[index:], epsilon)
        else:
            results = [points[0], points[-1]]
        return results