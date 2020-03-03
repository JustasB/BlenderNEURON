from neuron import h
from blenderneuron.commnode import CommNode
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from collections import OrderedDict
import re, math
from hashlib import sha1

try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib


class NeuronNode(CommNode):
    # Match Cell[n].section[y] pattern e.g. MC1[0].soma
    section_rx = re.compile('(.+?])\.?(.*)')

    def __init__(self, server_end=None, *args, **kwargs):
        self.roots = None
        self.section_index = None
        self.synapse_sets = {}  # 'set_name': [(netcon, syn, head, neck)]

        self.parallel_ctx = None
        self.mpimap = None
        self.mpirank = None

        def init():
            h.load_file('stdrun.hoc')

            self.server.register_function(self.get_roots)

            self.server.register_function(self.set_sim_params)
            self.server.register_function(self.get_sim_params)

            self.server.register_function(self.initialize_groups)
            self.server.register_function(self.update_groups)

            self.server.register_function(self.create_synapses)

        if server_end is None:
            server_end = "NEURON"

        super(NeuronNode, self).__init__(server_end, on_server_setup=init, *args, **kwargs)

    def init_mpi(self, parallel_ctx, mpimap):
        self.parallel_ctx = parallel_ctx
        self.mpimap = mpimap
        self.mpirank = parallel_ctx.id()
        self.current_gid = 0


    def get_roots(self):
        self.roots = h.SectionList()
        self.roots.allroots()
        self.roots = list(self.roots)

        self.update_section_index()

        return [
            {
                "index": i,
                "name": sec.name()
            }
            for i, sec in enumerate(self.roots)
        ]

    def update_section_index(self):
        all_sec = h.allsec()
        self.section_index = {sec.name(): sec for sec in all_sec}

    def initialize_groups(self, blender_groups, send_back=True):

        self.groups = OrderedDict()

        if self.section_index is None:
            self.update_section_index()

        for blender_group in blender_groups:
            name = blender_group["name"]

            nrn_group = NeuronRootGroup()
            nrn_group.from_skeletal_blender_group(blender_group, node=self)

            self.groups[name] = nrn_group

        if send_back:
            return self.get_group_dicts()

    def get_group_dicts(self, compressed=True):

        if any([g.record_activity for g in self.groups.values()]):
            h.run()

        result = [group.to_dict(include_activity=group.record_activity,
                  include_root_children=True,
                  include_coords_and_radii=True)
                  for group in self.groups.values()]

        if compressed:
            return self.compress(result)
        else:
            return result

    def update_groups(self, blender_groups):

        for blender_group in blender_groups:
            name = blender_group["name"]

            if name not in self.groups:
                self.initialize_groups(blender_groups, send_back=False)

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

        params["t"] = h.t
        params["tstop"] = h.tstop
        params["dt"] = h.dt
        params["atol"] = h.cvode.atol()
        params["celsius"] = h.celsius
        params["cvode"] = str(h.cvode_active())

        return params

    @staticmethod
    def clamp_section_x(x_in):
        """
        When placing synapses, avoid using 0 and 1 section locations, esp. if
        extracellular potentials will be computed. See the warning comment in:

        https://www.neuron.yale.edu/neuron/static/py_doc/modelspec/programmatic/
            mechanisms/mech.html?highlight=i_membrane#mech-extracellular

        :param x_in: 0-1 section location
        :return: section location constrained to 0.001-0.999
        """
        return min(max(x_in, 0.001), 0.999)

    def rank_section_name(self, single_rank_name):

        if self.mpimap is not None:
            cell_name, section_name = self.section_rx.match(single_rank_name).groups()

            entry = self.mpimap[cell_name]

            # If cell is not on this rank, return None
            if self.mpirank != entry['rank']:
                return None

            # Otherwise get its multi-rank section name
            mpi_cell_name = entry['name']
            mpi_name = mpi_cell_name

            if section_name != '':
                mpi_name += '.' + section_name

            return mpi_name

        else:
            return single_rank_name

    def segment_gid(self, sec_name, seg_id, has_spine):
        """
        One one gid can be associated with a segment. If more than one gid is assigned to a seg,
        only the last gid will send events to the post- synapse.

        However, if the segment index can be computed from section.x location, locations that
        refer to the same segment e.g. section(0.49) and section(0.51) when nseg=3, can be identified.

        This method generates a unique gid for each segment based on the section name and segment
        index. Where section(0) -> seg_id=0 and section(1) -> seg_id=nseg-1

        If a spine was added, its assumed that the pre-syn location is at the head of the spine.

        :param sec_name:
        :param seg_id:
        :param has_spine:
        :return:
        """

        # Generate a segment address e.g. MyCell[2].soma[1] from soma(0.5) with nseg=3
        seg_address = sec_name + ('[%s]' % seg_id)

        if has_spine:
            seg_address += '.spine_head'

        # Compute the SHA1 9-digit hash of the address
        # 9 digits is the largest safe number that is accepted by pc.set_gid2node
        # In practice, this will be unique for each segment
        # And same on each machine and version of python (unlike hash())
        gid = int(sha1(seg_address.encode('utf-8')).hexdigest(), 16) % (10 ** 9)

        return gid



    def create_synapses(self, syn_set):

        set_name = syn_set['name']
        syn_entries = syn_set['entries']

        synapses = self.synapse_sets[set_name] = []

        for entry in syn_entries:

            rank_source_section = self.rank_section_name(entry['source_section'])
            rank_dest_section = self.rank_section_name(entry['dest_section'])

            source_on_rank = rank_source_section is not None
            dest_on_rank = rank_dest_section is not None

            if dest_on_rank:
                dest_sec = self.section_index[rank_dest_section]
                dest_x = self.clamp_section_x(entry['dest_x'])
            else:
                dest_sec = None
                dest_x = 0

            if source_on_rank:
                source_sec = self.section_index[rank_source_section]
                source_x = self.clamp_section_x(entry['source_x'])
            else:
                source_sec = None
                source_x = 0

            # At first, assume no spines
            neck = None
            head = None

            # Unless indicated otherwise
            if source_on_rank and entry['create_spine']:
                prefix = set_name+"_"+entry['prefix']+"["+str(len(synapses))+"]"

                # Create the spine head
                head = h.Section(name=prefix + ".head")

                # basic passive params
                head.insert('pas')

                # Add the 3D coords
                self.add_spine_pt3d(head, entry['head_start'], entry['head_diameter'])
                self.add_spine_pt3d(head, entry['head_end'], entry['head_diameter'])

                # Create the head (if there is enough room)
                if entry['neck_start'] is not None:
                    neck = h.Section(name=prefix+".neck")
                    neck.insert('pas')

                    self.add_spine_pt3d(neck, entry['neck_start'], entry['neck_diameter'])
                    self.add_spine_pt3d(neck, entry['neck_end'], entry['neck_diameter'])

                    # Connect the spine together to the source section
                    neck.connect(source_sec(source_x), 0)
                    head.connect(neck)

                else:
                    # If there is no neck, connect the head to section directly
                    head.connect(source_sec(source_x), 0)

                # Point process should now be placed on the spine head
                source_sec = head
                source_x = 0.5

            source_gid = self.segment_gid(entry['source_section'], entry['source_seg_i'], entry['create_spine'])

            netcon, syn = self.create_netcon_syn(
                entry['dest_syn'],
                dest_sec,
                dest_x,
                entry['dest_syn_params'],
                source_sec,
                source_x,
                entry['threshold'],
                entry['delay'],
                entry['weight'],
                source_on_rank, dest_on_rank,
                source_gid
            )

            # If reciprocal, create a NetCon+Syn going in the opposite direction
            if entry['is_reciprocal']:

                dest_gid = self.segment_gid(entry['dest_section'], entry['dest_seg_i'], False)

                netcon_recip, syn_recip = self.create_netcon_syn(
                    entry['source_syn'],
                    source_sec,
                    source_x,
                    entry['source_syn_params'],
                    dest_sec,
                    dest_x,
                    entry['threshold'],
                    entry['delay'],
                    entry['weight'],
                    dest_on_rank, source_on_rank,
                    dest_gid
                )
            else:
                netcon_recip, syn_recip = None, None

            # Keep references to the synapse parts
            synapses.append((netcon, syn, neck, head, netcon_recip, syn_recip))


    def create_netcon_syn(self,
                          syn_class_name, syn_sec, syn_sec_x, syn_params,
                          source_sec, source_x, threshold, delay, weight,
                          source_on_rank, syn_on_rank, source_gid):

        netcon, syn = None, None

        if syn_on_rank:
            # Create synapse point process
            # e.g. syn = h.ExpSyn(dend(0.5))
            syn_class = getattr(h, syn_class_name)
            syn = syn_class(syn_sec(syn_sec_x))

            if syn_params != '':
                syn_params = eval(syn_params)
                for key in syn_params.keys():
                    setattr(syn, key, syn_params[key])

        # If both source and syn on rank, no rank span -> classic NetCon
        if syn_on_rank and source_on_rank:
            netcon = h.NetCon(
                source_sec(source_x)._ref_v,
                syn,
                threshold,
                delay,
                weight,
                sec=source_sec
            )

        # Connection spans ranks
        elif source_on_rank or syn_on_rank:
            if source_on_rank:

                # Assign a gid to a given segment only once
                if self.parallel_ctx.gid_exists(source_gid) == 0:
                    self.assign_gid_to_source_seg(
                        source_sec,
                        source_x,
                        threshold,
                        source_gid
                    )

            else: # syn_on_rank
                netcon = self.parallel_ctx.gid_connect(source_gid, syn)
                netcon.delay = delay
                netcon.weight[0] = weight

        return netcon, syn

    def assign_gid_to_source_seg(self, pre_sec, pre_sec_x, threshold, gid):
        # Assign the gid the current rank
        self.parallel_ctx.set_gid2node(gid, self.mpirank)

        # Create the dummy connection from source segment
        nc = h.NetCon(pre_sec(pre_sec_x)._ref_v, None, sec=pre_sec)
        nc.threshold = threshold

        # Assign the gid to the source segment (through the dummy netcon)
        self.parallel_ctx.cell(gid, nc)

    @staticmethod
    def add_spine_pt3d(sec, xyz, diam):
        h.pt3dadd(xyz[0], xyz[1], xyz[2], diam, sec=sec)