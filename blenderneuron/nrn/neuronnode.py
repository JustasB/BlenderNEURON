from neuron import h
from blenderneuron.commnode import CommNode
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from collections import OrderedDict

try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib


class NeuronNode(CommNode):

    def __init__(self, *args, **kwargs):
        def init():
            h.load_file('stdrun.hoc')

            self.server.register_function(self.get_roots)

            self.server.register_function(self.set_sim_params)
            self.server.register_function(self.get_sim_params)

            self.server.register_function(self.initialize_groups)
            self.server.register_function(self.update_groups)

        super(NeuronNode, self).__init__("NEURON", on_server_setup=init, *args, **kwargs)

    def get_roots(self):
        self.roots = h.SectionList()
        self.roots.allroots()
        self.roots = list(self.roots)

        self.update_section_index()

        return [
            {
                "index": i,
                "hash": str(hash(sec)),
                "name": sec.name()
            }
            for i, sec in enumerate(self.roots)
        ]

    def update_section_index(self):
        all_sec = h.allsec()
        self.section_index = {str(hash(sec)): sec for sec in all_sec}

    def initialize_groups(self, blender_groups):

        self.groups = OrderedDict()

        for blender_group in blender_groups:
            name = blender_group["name"]

            nrn_group = NeuronRootGroup()
            nrn_group.from_skeletal_blender_group(blender_group, node=self)

            self.groups[name] = nrn_group

        h.run()

        result = [group.to_dict(include_activity=True,
                  include_root_children=True,
                  include_coords_and_radii=True)
                  for group in self.groups.values()]

        return self.compress(result)

    def update_groups(self, blender_groups):

        for blender_group in blender_groups:
            name = blender_group["name"]
            nrn_group = self.groups[name]
            nrn_group.from_updated_blender_group(blender_group)

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
    def send_activity(self):
        """
        Sends the collected group section/segment activity to Blender. The recorded activity values are compressed
        to remove co-linear points and are sent in batches to maximize performance.

        :return:
        """

        for group in self.groups.values():
            if "collected_activity" not in group:
                return

            frames_per_ms = self.frames_per_ms
            part_activities = self.collected_activity
            parts = part_activities.keys()
            times = self.collection_times

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
                    pre_seg = h.cas()(pre_loc)
                    h.pop_section()

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

        coord_count = h.n3d(sec=section)
        along_coords = (coord_count - 1) * along
        start_coord_i = int(along_coords)
        along_start_coord = along_coords - start_coord_i

        if along_start_coord > 0:
            along_x = self.get_along_coord_dim("x", section, start_coord_i, along_start_coord)
            along_y = self.get_along_coord_dim("y", section, start_coord_i, along_start_coord)
            along_z = self.get_along_coord_dim("z", section, start_coord_i, along_start_coord)

        else:
            along_x = h.x3d(start_coord_i, sec=section)
            along_y = h.y3d(start_coord_i, sec=section)
            along_z = h.z3d(start_coord_i, sec=section)

        return (along_x, along_y, along_z)

    def get_along_coord_dim(self, dim, section, coord_i, along_start_coord):
        dim = getattr(h, dim + "3d")
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