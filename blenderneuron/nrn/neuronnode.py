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
        self.roots = None
        self.section_index = None
        self.synapse_sets = {}  # 'set_name': [(netcon, syn, head, neck)]

        def init():
            h.load_file('stdrun.hoc')

            self.server.register_function(self.get_roots)

            self.server.register_function(self.set_sim_params)
            self.server.register_function(self.get_sim_params)

            self.server.register_function(self.initialize_groups)
            self.server.register_function(self.update_groups)

            self.server.register_function(self.create_synapses)

        super(NeuronNode, self).__init__("NEURON", on_server_setup=init, *args, **kwargs)

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

    def create_synapses(self, syn_set):

        set_name = syn_set['name']
        syn_entries = syn_set['entries']

        synapses = self.synapse_sets[set_name] = []

        for entry in syn_entries:
            dest_sec = self.section_index[entry['dest_section']]
            dest_x = h.arc3d(entry['dest_pt_idx'], sec=dest_sec) / dest_sec.L

            source_sec = self.section_index[entry['source_section']]
            source_x = h.arc3d(entry['source_pt_idx'], sec=source_sec) / source_sec.L

            # Assume no spines
            neck = None
            head = None

            # Unless indicated otherwise
            if entry['create_spine']:
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

                # Delay is now 0 - propagation is taken care of by the spine
                entry['delay'] = 0

            netcon, syn = self.create_netcon_syn(
                entry['dest_syn'],
                dest_sec,
                dest_x,
                entry['dest_syn_params'],
                source_sec,
                source_x,
                entry['threshold'],
                entry['delay'],
                entry['weight']
            )

            if entry['is_reciprocal']:
                netcon_recip, syn_recip = self.create_netcon_syn(
                    entry['source_syn'],
                    source_sec,
                    source_x,
                    entry['source_syn_params'],
                    dest_sec,
                    dest_x,
                    entry['threshold'],
                    entry['delay'],
                    entry['weight']
                )
            else:
                netcon_recip, syn_recip = None, None

            # Keep references to the synapse parts
            synapses.append((netcon, syn, neck, head, netcon_recip, syn_recip))

    def create_netcon_syn(self,
                          syn_class_name, syn_sec, syn_sec_x, syn_params,
                          source_sec, source_x, threshold, delay, weight):

        # Create synapse point process
        # e.g. syn = h.ExpSyn(dend(0.5))
        syn_class = getattr(h, syn_class_name)
        syn = syn_class(syn_sec(syn_sec_x))

        if syn_params != '':
            syn_params = eval(syn_params)
            for key in syn_params.keys():
                setattr(syn, key, syn_params[key])

        netcon = h.NetCon(
            source_sec(source_x)._ref_v,
            syn,
            threshold,
            delay,
            weight,
            sec=source_sec
        )

        return netcon, syn

    @staticmethod
    def add_spine_pt3d(sec, xyz, diam):
        h.pt3dadd(xyz[0], xyz[1], xyz[2], diam, sec=sec)