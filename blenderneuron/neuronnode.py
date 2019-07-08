from neuron import h
from blenderneuron.commnode import CommNode
import zlib

try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib

class NeuronNode(CommNode):
    roots = []

    def __init__(self, *args, **kwargs):
        def init():
            self.h = h
            h.load_file('stdrun.hoc')

            self.groups = {}

            # Clear previously recorded activity on h.run()
            self.fih = h.FInitializeHandler(self.clear_activity)

            self.server.register_function(self.get_root_section_names)

            self.server.register_function(self.set_sim_params)
            self.server.register_function(self.get_sim_params)

            self.server.register_function(self.set_groups)

        super(NeuronNode, self).__init__("NEURON", on_server_setup=init, *args, **kwargs)

    def get_root_section_names(self):
        self.roots = h.SectionList()
        self.roots.allroots()
        self.roots = list(self.roots)

        return [(i, sec.name()) for i, sec in enumerate(self.roots)]

    def set_sim_params(self, params):
        h.tstop = params["tstop"]
        h.dt = params["dt"]
        h.cvode.atol(params["atol"])
        h.celsius = params["celsius"]
        h.cvode_active(int(params["cvode"]))

    def get_sim_params(self):
        params = {}

        params["tstop"] = h.tstop
        params["dt"] = h.dt
        params["atol"] = h.cvode.atol()
        params["celsius"] = h.celsius
        params["cvode"] = str(h.cvode_active())

        return params

    def set_groups(self, groups):

        self.groups = groups

        for group in groups.values():
            group["cells"] = [self.roots[i] for i in group["cells"]]
            self.create_collector(group)

        h.run()

        for group in self.groups.values():
            self.gather_group_coords(group)

        result = {}

        for group_name in self.groups.keys():
            group = self.groups[group_name]

            # Send back a subset of the group structure
            result[group_name] = {
                "3d_data": group["3d_data"],
                "collected_activity": group["collected_activity"],
                "collection_times": group["collection_times"],
            }

        result = str(result)
        try:
            result = xmlrpclib.Binary(zlib.compress(result, 2))
        except:
            result = xmlrpclib.Binary(zlib.compress(result.encode('utf8'), 2))
        return result


    def create_collector(self, group):
        """
        Greates a pair of NetStim and NetCon which trigger an event to recursively collect the activity of the group
        segments. This method does nothing if group['collect_activity'] is False

        :param group: The group dictionary for which to create the collector
        """

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

    def send_model(self):
        """
        A convenience method to send the model morphology, connections, and activity data to Blender. After this method
        executes, BlenderNEURON addon method 'link_objects' needs to be called for the cells to become visible in
        Blender. See: :any:`to_blender` for details.

        Raises:
             Exception if communication with BlenderNEURON addon cannot be established

        """

        if self.include_morphology:
            self.send_morphology()

        if self.include_connections:
            self.send_cons()

        if self.include_activity:
            self.send_activity()


    def gather_group_coords(self, group):
        """
        Recursively obtains the coordinates of all 3D points of the group sections

        :param group: the dictionary of the group
        :return: None
        """

        cell_data = group['3d_data']['cells'] = {}

        for root in group["cells"]:
            cell_name = root.cell().hname() if root.cell() is not None else root.name()
            cell_coords = self.get_cell_coords(root)

            # Account for a cell having multiple roots
            if cell_name in cell_data:
                cell_data[cell_name].extend(cell_coords)
            else:
                cell_data[cell_name] = cell_coords

    def get_coord_count(self, section):
        """
        Obtains the number of 3D points defined for a section. If no points have been added, uses NEURON's define_shape
        method to automatically create them (will be equal to nseg).

        :param section: a reference to a NEURON section e.g. soma = h.Section()
        :return: The number of 3D points the section has
        """

        coord_count = int(self.h.n3d(sec=section))

        # Let NEURON create them if missing
        if coord_count == 0:
            self.h.define_shape(sec=section)
            coord_count = int(self.h.n3d(sec=section))

        return coord_count

    def get_cell_coords(self, section, result=None):
        """
        Recursively gathers the list of coordinates of a cell (root section)

        :param section: A reference to NEURON root section
        :param result: None, used internally
        :return: A list of dictionaries with section names, coordinates, and coordinate radii. Coords has the form
         of [x1,y1,z1,x2,y2,z2...], and radii [r1,r2,...]
        """

        # Determine how many 3d points the section has
        coord_count = self.get_coord_count(section)

        # Collect the coordinates
        coords = [None] * coord_count * 3
        radii = [None] * coord_count

        for c in range(coord_count):
            ci = c * 3
            coords[ci] = self.h.x3d(c, sec=section)
            coords[ci + 1] = self.h.y3d(c, sec=section)
            coords[ci + 2] = self.h.z3d(c, sec=section)

            radii[c] = self.h.diam3d(c, sec=section) / 2.0

        if result is None:
            result = []

        sec_coords = {
            "name": section.name(),
            "coords": coords,
            "radii": radii,
        }

        result.append(sec_coords)

        children = section.children()

        for child in children:
            self.get_cell_coords(child, result)

        return result


    def collect_group(self, group_name):
        """
        Based on the group's color level, gathers the values of the group's collect_variable. This method is called
        at regular times during the simulation. See :any:`create_cell_group()` for details.

        :param group_name: The name of the group whose section values to measure and store

        :return: None
        """

        group = self.groups[group_name]
        group["collection_times"].append(self.h.t)
        level = group['3d_data']["color_level"]

        # Recursively record from every segment of each section of each cell
        if level == 'Segment':
            for root in group["cells"]:
                self.collect_segments_recursive(root, group)

        # Recursively record from the middle of each section of each cell
        elif level == 'Section':
            for root in group["cells"]:
                self.collect_section(root, group, recursive=True)

        # Record from the middle of somas of each cell
        elif level == 'Cell':
            for root in group["cells"]:
                self.collect_section(root, group, recursive=False)

        # Record from the somas of each cell and compute their mean
        else:
            variable = group["collect_variable"]

            # Compute the mean of group cell somas
            value = 0.0
            for soma in group["cells"]:
                value += getattr(soma(0.5), variable)
            value = value / len(group["cells"])

            activity = group["collected_activity"]
            name = group_name + "Group"

            if name not in activity:
                activity[name] = []

            activity[name].append(value)

    def collect_segments_recursive(self, section, group):
        """
        Recursively collects the values of segments of a group cell (root section). Segments are given sequential 0-based
        names similar to NEURON cells and sections. For example, TestCell[0].dend[3][4] refers to first TestCell, 4th
        dendrite, 5th segment. Segment order is determined by the order in which they appear in NEURON's xyz3d() function.

        :param section: A reference to a group root section
        :param group: reference to a group dictionary
        :return: None
        """

        coordCount = self.get_coord_count(section)

        activity = group["collected_activity"]
        variable = group["collect_variable"]

        for i in range(1, coordCount):
            name = section.name() + "[" + str(i - 1) + "]"

            startL = self.h.arc3d(i - 1, sec=section)
            endL = self.h.arc3d(i, sec=section)
            vectorPos = (endL + startL) / 2.0 / section.L

            value = getattr(section(vectorPos), variable)

            if name not in activity:
                activity[name] = []

            activity[name].append(value)

        for child in section.children():
            self.collect_segments_recursive(child, group)

    def collect_section(self, section, group, recursive=True):
        """
        Recursively collects the section midpoint values of a group's collect_variable (e.g. 'v')

        :param section: A root section of a group
        :param group: The group's dictionary
        :param recursive: Whether to collect child section values (otherwise stop at root/soma)
        :return: None
        """

        activity = group["collected_activity"]
        variable = group["collect_variable"]

        if recursive:
            name = section.name()
        else:
            name = str(section.cell())

        value = getattr(section(0.5), variable)

        if name not in activity:
            activity[name] = []

        activity[name].append(value)

        if recursive:
            for child in section.children():
                self.collect_section(child, group, recursive)

    def send_activity(self):
        """
        Sends the collected group section/segment activity to Blender. The recorded activity values are compressed
        to remove co-linear points and are sent in batches to maximize performance.

        :return:
        """

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
                reduced_times = [t * frames_per_ms for t in reduced_times]

                payload.append({'name': part, 'times': reduced_times, 'activity': reduced_values})

                # Buffered send
                if len(payload) > 1000:
                    self.enqueue_method("set_segment_activities", payload)
                    payload = []

            self.enqueue_method("set_segment_activities", payload)

    # TODO: this could benefit from cython
    def simplify_activity(self, times, activity):
        """
        Removes co-linear points from a time series of collected activity. Used to compress activity before
        sending to Blender.

        :param times: an array of times
        :param activity: an array of corresponding activity values
        :return: times and activity arrays with the co-linear points removed
        """
        reduced = BlenderNEURON.rdp(list(zip(times, activity)), self.activity_simplification_tolerance)
        return zip(*reduced)

    def clear_activity(self):
        """
        Removes collected activity values from all groups. Called at the start of simulation, using NEURON's FInitialize()
        method.

        :return: None
        """
        for group in self.groups.values():
            group['collection_times'] = []
            group['collected_activity'] = {}

    def send_cons(self):
        """
        Gathers the start and end coordinates (if available) of all NetConn objects and sends them to Blender.

        :return: None
        """

        cons = {}

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
                    pre_seg = self.h.cas()(pre_loc)
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

            cons["NetCon[" + str(i) + "]"] = [{
                "name": "NetCon[" + str(i) + "]",
                "coords": pre_pos + post_pos,
                "radii": [1, 1]
            }]

        self.connection_data["Synapses"]["cells"] = cons

        self.enqueue_method("create_cons", self.connection_data["Synapses"])

    def get_coords_along_sec(self, section, along):
        """
        Gets the section 3d coordinate that is 0-1 fraction along from the begining of the section.

        :param section: reference to a NEURON section
        :param along: float, 0-1, refering to the fraction along the section
        :return: a tuple of (x,y,z) coordinate
        """

        coord_count = self.h.n3d(sec=section)
        along_coords = (coord_count - 1) * along
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

        return (along_x, along_y, along_z)

    def get_along_coord_dim(self, dim, section, coord_i, along_start_coord):
        dim = getattr(self.h, dim + "3d")
        start = dim(coord_i, sec=section)
        end = dim(coord_i + 1, sec=section)
        length = end - start
        along = start + along_start_coord * length
        return along

    @staticmethod
    def distance(a, b):
        """
        Returns the distance between two points defined as 2-lists/tuples
        """
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @staticmethod
    def point_line_distance(point, start, end):
        if (start == end):
            return BlenderNEURON.distance(point, start)
        else:
            n = abs((end[0] - start[0]) * (start[1] - point[1]) - (start[0] - point[0]) * (end[1] - start[1]))
            d = sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
            return n / d

    @staticmethod
    def rdp(points, epsilon):
        """
        Reduces a series of points to a simplified version that loses detail, but maintains the general shape of the series.

        Ramer-Douglas-Peucker algorithm adapted from: https://github.com/sebleier/RDP

        :param points: An array of (x,y) tuples to simplify
        :param epsilon: The maximum distance that points can deviate from a line and be removed
        :return: A simplified array of (x,y) tuples
        """

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