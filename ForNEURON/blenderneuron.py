import xmlrpclib, threading, time, cPickle, zlib, hashlib
from math import sqrt

class BlenderNEURON(object):
    def __init__(self, h, ip='127.0.0.1', port='8000'):
        self.h = h

        self.IP = ip
        self.Port = port
        self.client = xmlrpclib.ServerProxy('http://'+ip+':'+port, allow_none=True)
        self.progress_client = xmlrpclib.ServerProxy('http://' + ip + ':' + port)

        self.activity_simplification_tolerance = 0.32 # mV

        # Example groups:
        # blender.groups = {
        # 	"earth": {     cells: [h.Cell[0].soma],    color_level = 'Segment', interaction_level = 'Segment', collection_period_ms = 0.1, res_u, res_v, as_lines, color, smooth_sections},
        # 	"pluto": {     cells: [root2,3,4],         color_level = 'Section', interaction_level = 'Section', collection_period_ms = 1},
        # 	"alphaC": {    cells: [root5,6,7,8,9,10],  color_level = 'Cell',    interaction_level = 'Cell',    collection_period_ms = 3},
        # 	"andromeda": { cells: [root11-1000],       color_level = 'Group',   interaction_level = 'Group',   collection_period_ms = 5}
        # }
        self.groups = {}

        # Example connections:
        # blender.conenctions = [h.NetCon[0], h.NetCon[1]]
        self.connections = []

        self.clear_activity()

        # Clear previously recorded activity on h.run()
        self.fih = self.h.FInitializeHandler(self.clear_activity)

        self.progressNEURON = self.h.ref('0.0')
        self.progressBlender = self.h.ref('0.0')
        self.progressPercent = self.h.ref('0.0')

        self.include_morphology = True
        self.include_connections = True
        self.include_activity = True

        self.show_panel()

    def show_panel(self):
        self.h.xpanel('BlenderNEURON')

        self.h.xcheckbox('Include Cells', (self, 'include_morphology'))
        self.h.xcheckbox('Include Connections', (self, 'include_connections'))
        self.h.xcheckbox('Include Activity', (self, 'include_activity'))
        self.h.xbutton('Send To Blender', self.send_model_threaded)

        self.h.xlabel('Progress:')
        self.h.xvarlabel(self.progressNEURON)
        self.h.xvarlabel(self.progressBlender)
        self.h.xvarlabel(self.progressPercent)

        self.h.xpanel(500, 10)
    def send_model_threaded(self):
        self.send_thread = threading.Thread(target=self.send_model)
        self.send_thread.daemon = True

        self.blender_progress_thread = threading.Thread(target=self.get_blender_progress)
        self.blender_progress_thread.daemon = True

        # self.progress_client.progress_start()
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

    def setup_defaults_if_needed(self):
        if len(self.groups.values()) == 0:
            self.setup_default_group()

        if len(self.connections) == 0:
            self.setup_default_connections()

    def setup_default_connections(self):
        # Include all connections by default
        self.connections = self.h.NetCon

    def setup_default_group(self):
        # By default, include all cells ('root sections') in the model
        all_cells = self.h.SectionList()
        all_cells.allroots()

        self.create_cell_group("all", [cell for cell in all_cells])

    def create_cell_group(self, name, cells):

        # Adjust level of detail based on cell count
        level = self.get_detail_level(len(cells))

        group = {
            'cells': cells,
            'collect_activity': True,
            'collect_variable': 'v',
            'collection_period_ms': 1,
            'frames_per_ms': 2.0,
            'spherize_soma_if_DeqL': True,
            '3d_data': {
                'name': name,
                'color': [1, 1, 1],
                'interaction_level': level,
                'color_level': level,
                'as_lines': False,
                'segment_subdivisions': 3,
                'circular_subdivisions': 12,
                'smooth_sections': True,
                'cells': {}
            }
        }

        # TODO: Segment level interaction is not supported
        if level == 'Segment':
            group['3d_data']['interaction_level'] = 'Section'

        self.create_collector(group)

        self.groups[name] = group

        return group

    def get_detail_level(self, cell_count):
        if cell_count <= 5:
            level = 'Segment'
        elif cell_count <= 25:
            level = 'Section'
        elif cell_count <= 100:
            level = 'Cell'
        else:
            level = 'Group'
        return level

    def create_collector(self, group):
        if group['collect_activity']:
            collector_stim = self.h.NetStim(0.5)
            collector_stim.start = 0
            collector_stim.interval = group['collection_period_ms']
            collector_stim.number = 1e9
            collector_stim.noise = 0
            collector_con = self.h.NetCon(collector_stim, None)
            collector_con.record((self.collect_group, group['3d_data']['name']))

            group["collector_stim"] = collector_stim
            group["collector_con"] = collector_con
            group["collection_times"] = []
            group["collected_activity"] = {}


    def prepare_for_collection(self):
        self.setup_defaults_if_needed()

    def run_method(self, name, *args, **kwargs):
        self.client.run_method(name, args, kwargs)

    def enqueue_method(self, name, *args, **kwargs):
        self.client.enqueue_method(name, args, kwargs)

    def run_command(self, command_string):
        self.client.run_command(command_string)

    def enqueue_command(self, command_string):
        self.client.enqueue_command(command_string)

    def send_model(self):
        self.is_blender_ready()

        self.setup_defaults_if_needed()

        # Remove any previous model objects
        self.enqueue_method("clear")

        if self.include_morphology:
            self.send_morphology()

        if self.include_connections:
            self.send_cons()

        if self.include_activity:
            self.send_activity()

    def is_blender_ready(self):
        try:
            self.client.ping()
        except:
            raise Exception(
                "Is Blender running and BlenderNEURON addon active? Could not communicate with Blender on " + self.IP + ":" + self.Port)

    def send_morphology(self):
        for group in self.groups.values():
            self.gather_group_coords(group)
            self.send_group(group)

    def gather_group_coords(self, group):
        cell_data = group['3d_data']['cells'] = {}
        spherize = group["spherize_soma_if_DeqL"]

        for root in group["cells"]:
            cell_name = root.cell().hname() if root.cell() is not None else root.name()
            cell_coords = self.get_cell_coords(root, spherize_if_DeqL=spherize)

            # Account for a cell having multiple roots
            if cell_name in cell_data:
                cell_data[cell_name].extend(cell_coords)
            else:
                cell_data[cell_name] = cell_coords


    def get_coord_count(self, section):
        coord_count = int(self.h.n3d(sec=section))

        # Let NEURON create them if missing
        if coord_count == 0:
            self.h.define_shape(sec=section)
            coord_count = int(self.h.n3d(sec=section))

        return coord_count

    def shorten_name_if_needed(self, name, max_length=56):
        result = name

        # Blender names must be <64 characters long
        # If section name is too long, will truncate the string and replace it with a MD5 hash
        # There must also be enough room for segment materials (here we allow for up to 99,999 segments/materials per section)
        # 63 max, with two for []s and 5 for segment id = 56
        if len(result) > max_length:
            return result[:max_length-17] + "#" + hashlib.md5(result.encode('utf-8')).hexdigest()[:16]

        return result

    def get_cell_coords(self, section, result=None, spherize_if_DeqL=True):
        # Determine how many 3d points the section has
        coord_count = self.get_coord_count(section)

        # Collect the coordinates
        coords = [None]*coord_count*3
        radii =  [None]*coord_count

        for c in range(coord_count):
            ci = c*3
            coords[ci] = self.h.x3d(c, sec=section)
            coords[ci+1] = self.h.y3d(c, sec=section)
            coords[ci+2] = self.h.z3d(c, sec=section)

            radii[c] = self.h.diam3d(c, sec=section) / 2.0


        if result is None:
            result = []

        sec_coords = {
            "name": self.shorten_name_if_needed(section.name()),
            "coords": coords,
            "radii": radii,
        }

        # Create spherical intermediate points if spherizing
        if spherize_if_DeqL and \
            "soma" in section.name().lower() and \
                 abs(section.diam - section.L) < 0.1:
                    self.spherize_coords(sec_coords, length=section.L)

        result.append(sec_coords)

        children = section.children()

        for child in children:
            self.get_cell_coords(child, result, spherize_if_DeqL)

        return result

    def spherize_coords(self, sec_coords, length, steps=7):
        sec_coords["spherical"] = True

        x1 = sec_coords["coords"][0]
        y1 = sec_coords["coords"][1]
        z1 = sec_coords["coords"][2]

        x2 = sec_coords["coords"][3]
        y2 = sec_coords["coords"][4]
        z2 = sec_coords["coords"][5]

        range_x = x2 - x1
        range_y = y2 - y1
        range_z = z2 - z1

        radius = sec_coords["radii"][0]

        # Length and diameter are same, so spherize the cylinder
        # by adding intermediate, spherical diameter points
        step_size = length / (steps + 1.0)

        for step in range(steps):
            dist_from_start = step_size + step*step_size
            dist_to_center = abs(radius-dist_from_start)
            step_radius = sqrt(radius**2-dist_to_center**2)

            fraction_along = dist_from_start / length
            step_x = x1 + range_x * fraction_along
            step_y = y1 + range_y * fraction_along
            step_z = z1 + range_z * fraction_along

            pt_idx = step+1
            sec_coords["coords"][pt_idx*3:pt_idx*3] = [step_x, step_y, step_z]
            sec_coords["radii"].insert(pt_idx, step_radius)

        # Set the first and last points to 0 diam
        sec_coords["radii"][0] = 0
        sec_coords["radii"][-1] = 0

    def send_group(self, group):
        data = group['3d_data']
        # data = cPickle.dumps(data)
        # data = zlib.compress(data)

        self.enqueue_method("visualize_group", data)


    def collect_group(self, group_name):
        group = self.groups[group_name]
        group["collection_times"].append(self.h.t)
        level = group['3d_data']["color_level"]

        #level = "Cell"

        # Recursively record from every segment of each section of each cell
        if level == 'Segment':
            for root in group["cells"]:
                self.collect_segments_recursive(root, group)

        # Recursively record from the middle of each section of each cell
        elif level == 'Section':
            for root in group["cells"]:
                self.collect_section(root, group, recursive = True)

        # Record from the middle of somas of each cell
        elif level == 'Cell':
            for root in group["cells"]:
                self.collect_section(root, group, recursive = False)

        # Record from the somas of each cell and compute their mean
        else:
            variable = group["collect_variable"]

            # Compute the mean of group cell somas
            value = 0.0
            for soma in group["cells"]:
                value += getattr(soma(0.5), variable)
            value = value / len(group["cells"])

            activity = group["collected_activity"]
            name = group["name"] + "Group"

            if name not in activity:
                activity[name] = []

            activity[name].append(value)

    def collect_segments_recursive(self, section, group):
        coordCount = self.get_coord_count(section)

        activity = group["collected_activity"]
        variable = group["collect_variable"]

        for i in range(1, coordCount):
            name = self.shorten_name_if_needed(section.name()) + "[" + str(i - 1) + "]"

            startL = self.h.arc3d(i - 1, sec=section)
            endL = self.h.arc3d(i, sec=section)
            vectorPos = (endL + startL) / 2.0 / section.L

            value = getattr(section(vectorPos), variable)

            if name not in activity:
                activity[name] = []

            activity[name].append(value)

        for child in section.children():
            self.collect_segments_recursive(child, group)

    def collect_section(self, section, group, recursive = True):
        activity = group["collected_activity"]
        variable = group["collect_variable"]

        if recursive:
            name = self.shorten_name_if_needed(section.name())
        else:
            name = section.cell().name()

        value = getattr(section(0.5), variable)

        if name not in activity:
            activity[name] = []

        activity[name].append(value)

        if recursive:
            for child in section.children():
                self.collect_section(child, group, recursive)

    def send_activity(self):
        for group in self.groups.values():
            if "collected_activity" not in group:
                return

            frames_per_ms = group["frames_per_ms"]
            part_activities = group["collected_activity"]
            parts = part_activities.keys()
            times = group["collection_times"]

            payload = []

            for part in parts:
                # Remove extra co-linear points
                reduced_times, reduced_values = self.simplify_activity(times, part_activities[part])

                # Scale the times
                reduced_times = [t*frames_per_ms for t in reduced_times]

                payload.append({'name':part, 'times':reduced_times, 'activity':reduced_values})

                # Buffered send
                if len(payload) > 1000:
                    self.enqueue_method("set_segment_activities", payload)
                    payload = []

            self.enqueue_method("set_segment_activities", payload)

    # TODO: this could benefit from cython
    def simplify_activity(self, times, activity):
        reduced = BlenderNEURON.rdp(zip(times, activity), self.activity_simplification_tolerance)
        return zip(*reduced)

    def clear_activity(self):
        self.activity = {}
        self.collection_times = []


    def send_cons(self):

        cons = []

        for i, con in enumerate(self.connections):
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

        self.enqueue_method("create_cons", cons)

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
