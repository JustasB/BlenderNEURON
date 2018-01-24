import xmlrpclib

class BlenderNEURON(object):
    def __init__(self, h, ip = '192.168.0.34', port = '8000', collect_activity = True, roots_to_collect = []):
        self.h = h
        self.client = xmlrpclib.ServerProxy('http://'+ip+':'+port)

        if collect_activity or len(roots_to_collect) > 0:
            self.collector_stim = self.h.NetStim(0.5)
            self.collector_stim.start = 0
            self.collector_stim.interval = 1
            self.collector_stim.number = 1e9
            self.collector_stim.noise = 0

            self.collector_con = self.h.NetCon(self.collector_stim, None)
            self.collector_con.record(self.collect)

            # Collect from all segments
            if len(roots_to_collect) == 0:
                self.roots_to_collect = self.h.SectionList()
                self.roots_to_collect.allroots()
            else:
                self.roots_to_collect = roots_to_collect


        self.is_collecting = collect_activity
        self.segment_activity = {}
        self.collection_times = []

    def send_model(self, include_cells = True, include_cons = True, include_activity = True):
        # Remove any previous model objects
        self.client.clear()

        if include_cells:
            self.send_cells()

        if include_cons:
            self.send_cons()

        if include_activity:
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
                    self.pop_section()

                # Skip if it's neither a PP nor a segment
                else:
                    continue

            # Check if post is a Section
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

    def send_cells(self):
        self.roots = self.h.SectionList()
        self.roots.allroots()
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
            h.define_shape(sec=rootSection)
            coordCount = int(h.n3d(sec=rootSection))

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
        activities = []

        for seg in self.segment_activity:
            activities.append({'name':seg, 'activity':self.segment_activity[seg]})

            # Buffered send
            if len(activities) > 100:
                self.client.set_segment_activities(self.collection_times, activities)
                activities = []

        self.client.set_segment_activities(self.collection_times, activities)


