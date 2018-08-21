try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib

import threading, time, hashlib
from math import sqrt
import collections

"""NEURON-based client library for BlenderNEURON"""

class BlenderNEURON(object):
    """The BlenderNEURON client class, which sends commands to the server created by the BlenderNEURON Blender add-on"""

    def __init__(self, h=None, ip='127.0.0.1', port='8000', show_panel=True, show_tutorial=True):
        """
        Creates an XMLRCP client which will communicate with the server, shows the GUI panel, and the tutorial

        :math:`a^2+b^2=c^2`

        :param h: an optional NEURON "h" variable. If not passed in, the method will load NEURON automatically
        :param ip: the IP address of the machine where the Addon will listen to client commands. Localhost by default. If another machine is specified, make sure any firewalls allow communication.
        :param port: the port of the machine where the Addon will listen to
        :param show_panel: Shows the GUI window
        :param show_tutorial: Shows a short tutorial for how to use the client
        """

        if h is not None:
            self.h = h

        else:
            from neuron import h, gui
            self.h = h

        self.IP = ip
        self.Port = str(port)
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
        self.connection_data = {}

        self.clear_activity()

        # Clear previously recorded activity on h.run()
        self.fih = self.h.FInitializeHandler(self.clear_activity)

        # self.progressNEURON = self.h.ref('0.0')
        # self.progressBlender = self.h.ref('0.0')
        # self.progressPercent = self.h.ref('0.0')
        self.connectionStatus = self.h.ref('---')

        self.include_morphology = True
        self.include_connections = True
        self.include_activity = True

        if show_panel:
            self.show_panel()

        if show_tutorial:
            print("")
            print("-== NEURON python module of BlenderNEURON is ready ==-")
            print("  It will send commands to Blender at the following address:" + self.IP + ":" + self.Port)
            print("  If you haven't already, start Blender with BlenderNEURON addon installed")
            print("  The address on the addon's tab in Blender should match the above IP and Port.")
            print("")
            print("  In python console, type: bn.is_blender_ready() to check if connection to Blender can be established.")
            print("")
            print("  To visualize a model in Blender: ")
            print("  1) Load it in NEURON. Graph > Shape plot should show active cell morphology.")
            print("  2) Click 'Send to Blender' in the GUI panel or type 'bn.to_blender()' in python console.")
            print("  3) Switch to Blender window to see the model.")
            print("")
            print("  To visualize activity: ")
            print("  1) Load model in NEURON")
            print("  2) Click 'Prepare for Simulation'. During simulation, this will save compartment activity to be sent to Blender.")
            print("  3) Run simulation (e.g. 'h.run()')")
            print("  4) Click 'Send to Blender' ")
            print("  5) Switch to Blender window to see the model.")
            print("")
            print("  If you add cells or make changes to morphology, click 'Re-Gather Sections before 'Send'ing or 'Prepare'ing.")
            print("")
            print(" Blender basics:")
            print("   HOME key to zoom out and view the full scene")
            print("   Mouse wheel - zoom in/out")
            print("   Hold down and drag mouse middle button - rotate")
            print("   SHIFT + hold down and drag mouse middle button - pan view")
            print("   Right click on an object - select the object and see its name")
            print("   Numpad '.' key - to zoom in on a selected object")
            print("")
            print("   There are many great Blender tutorials online. ")
            print("   These are a good start: https://cloud.blender.org/p/blender-inside-out/560414b7044a2a00c4a6da98")

    def to_blender(self, color_unique_names=True):
        """
        A convenience method to send all groups of cells defined by self.groups property to Blender.
        The method first clears the Blender scene, sends the morphology, any activity, and NetConns, links them to the scene (shows),
        Zooms out the camera to include all cells/sections, colors the sections based on their names, and sets the animation length based on h.tstop

        If called without creating any groups, it will create a default "all" group which contains all sections instantiated in NEURON

        :param color_unique_names: Whether to color the cell sections based on their names, gray otherwise
        :return: None
        """
        self.enqueue_method("clear")
        self.send_model()
        self.enqueue_method('link_objects')
        self.enqueue_method('show_full_scene')

        if color_unique_names:
            self.enqueue_method('color_by_unique_materials')

        self.run_method('set_render_params', (0, self.get_num_frames()))

    def refresh(self):
        """
        A convenience menthod that will recreate the default "all" group. It should be called after NEURON model
        has changed (added/modified sections).

        :return: None
        """
        self.setup_default_group()

    def get_num_frames(self):
        r"""
        Computes the number of frames to be shown in Blender to represent the simulation.

        It's equal to the maximum number of frames per ms of simulation x NEURON h.tstop



        :return:
        """

        max_num_frames_per_ms = max(self.groups[g]["frames_per_ms"] for g in self.groups.keys())

        return max_num_frames_per_ms * self.h.tstop

    def show_panel(self):
        self.h.xpanel('BlenderNEURON')

        self.h.xcheckbox('Include Cells', (self, 'include_morphology'))
        self.h.xcheckbox('Include Connections', (self, 'include_connections'))
        self.h.xcheckbox('Include Activity', (self, 'include_activity'))
        self.h.xlabel(" ")
        self.h.xbutton('Prepare For Simulation', self.prepare_for_collection)
        self.h.xbutton('Send To Blender', self.to_blender)
        self.h.xlabel(" ")
        self.h.xbutton('Re-Gather Sections', self.refresh)
        self.h.xlabel(" ")
        self.h.xlabel("Connection status:")
        self.h.xvarlabel(self.connectionStatus)
        self.h.xbutton('Test Connection', self.is_blender_ready)

        # self.h.xlabel('Progress:')
        # self.h.xvarlabel(self.progressNEURON)
        # self.h.xvarlabel(self.progressBlender)
        # self.h.xvarlabel(self.progressPercent)

        self.h.xpanel(500, 10)

    def setup_defaults_if_needed(self):
        if len(self.groups.values()) == 0:
            self.setup_default_group()

        if len(self.connections) == 0:
            self.setup_default_connections()

    def setup_default_connections(self):
        # Include all NetCon connections by default
        self.connections = self.h.NetCon

        # Connections will be rendered as segments connecting cells
        group =  {
            'name': "Synapses",
            'color': [1, 1, 0],
            'interaction_level': "Group",
            'color_level': "Group",
            'as_lines': False,
            'circular_subdivisions': 4,
            'segment_subdivisions': 1,
            'smooth_sections': False,
            'cells': {}
        }

        self.connection_data["Synapses"] = group


    def setup_default_group(self):
        # By default, include all cells ('root sections') in the model
        all_cells = self.h.SectionList()
        all_cells.allroots()
        root_sections = [cell for cell in all_cells]

        if "all" in self.groups:
            group = self.groups["all"]

            # If group already exists, clear out previous section data
            group["cells"] = root_sections
            group["3d_data"]["cells"] = {}
            group['collection_times'] = []
            group['collected_activity'] = {}

        else:
            self.create_cell_group("all", root_sections)

    def create_cell_group(self, name, cells, options=None):

        # Adjust level of detail based on cell count
        level = self.get_detail_level(len(cells))

        # Create group based on default settings
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
            },
            'collection_times': [],
            'collected_activity': {},
        }

        # Set any custom options for the group
        BlenderNEURON.update_group(group, options)

        # TODO: Segment level interaction is not supported
        if group['3d_data']['interaction_level'] == 'Segment':
            group['3d_data']['interaction_level'] = 'Section'

        # Create collectors, if collecting activity for the group
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


    def prepare_for_collection(self):
        self.setup_defaults_if_needed()

    def run_method(self, name, *args, **kwargs):
        return self.client.run_method(name, args, kwargs)

    def enqueue_method(self, name, *args, **kwargs):
        self.client.enqueue_method(name, args, kwargs)

    def run_command(self, command_string):
        return self.client.run_command(command_string)

    def enqueue_command(self, command_string):
        self.client.enqueue_command(command_string)

    def send_model(self):
        if not self.is_blender_ready():
            raise Exception(
                "Is Blender running and BlenderNEURON addon active? "
                "Could not communicate with Blender on " + self.IP + ":" + self.Port
            )

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
            self.connectionStatus[0] = 'Ready'
            return True
        except:
            self.connectionStatus[0] = 'Not Connected'
            return False

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
        # If section name is too long, will truncate the string and replace it with an MD5 hash
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
        # Remove intermediate, co-linear points
        if len(sec_coords["radii"]) > 2:
            sec_coords["radii"] = [sec_coords["radii"][0], sec_coords["radii"][-1]]
            sec_coords["coords"] = sec_coords["coords"][0:3] + sec_coords["coords"][-3:]

        x1 = sec_coords["coords"][0]
        y1 = sec_coords["coords"][1]
        z1 = sec_coords["coords"][2]

        x2 = sec_coords["coords"][-3]
        y2 = sec_coords["coords"][-2]
        z2 = sec_coords["coords"][-1]

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

        sec_coords["spherical"] = True

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
            name = group_name + "Group"

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
            name = str(section.cell())

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
        for group in self.groups.values():
            group['collection_times'] = []
            group['collected_activity'] = {}

    def send_cons(self):

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

            cons["NetCon["+str(i)+"]"] = [{
                "name": "NetCon["+str(i)+"]",
                "coords": pre_pos + post_pos,
                "radii": [1,1]
            }]

        self.connection_data["Synapses"]["cells"] = cons

        self.enqueue_method("create_cons", self.connection_data["Synapses"])

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

    @staticmethod
    def update_group(group, options):
        if options is None:
            return group

        d = group
        u = options

        for k, v in u.iteritems():
            if isinstance(v, collections.Mapping):
                d[k] = update(d.get(k, {}), v)

            else:
                d[k] = v

        return d
