from blenderneuron.compat import string_types
from neuron import h
from blenderneuron.commnode import CommNode
from blenderneuron.utils import deserialize, serialize
from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from collections import OrderedDict
import re, math, traceback
import logging

logger = logging.getLogger(__name__)
from hashlib import sha1

try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib


class NeuronNode(CommNode):
    # Match Cell[n].section[y] pattern e.g. MC1[0].soma
    section_rx = re.compile(r'(.+?])\.?(.*)')

    def __init__(self, server_end=None, *args, **kwargs):
        self.roots = None
        self.section_index = None
        self.synapse_sets = {}  # 'set_name': [(netcon, syn, head, neck)]

        self.parallel_ctx = None
        self.mpimap = None
        self.mpirank = None
        self.mpi_coordinator_active = False

        def init():
            h.load_file('stdrun.hoc')

            self.server.register_function(self.get_roots)

            self.server.register_function(self.set_sim_params)
            self.server.register_function(self.run_simulation)
            self.server.register_function(self.get_sim_params)

            self.server.register_function(self.initialize_groups)
            self.server.register_function(self.update_groups)

            self.server.register_function(self.create_synapses)

        if server_end is None:
            server_end = "NEURON"

        # MPI workers have no XML-RPC server, but still need stdrun commands
        # when rank zero later dispatches a simulation operation to them.
        if server_end == "Package":
            h.load_file('stdrun.hoc')

        super(NeuronNode, self).__init__(server_end, on_server_setup=init, *args, **kwargs)

    def init_mpi(self, parallel_ctx, mpimap=None):
        self.parallel_ctx = parallel_ctx
        self.mpimap = mpimap
        self.mpirank = parallel_ctx.id()
        self.current_gid = 0

    def start_mpi_coordinator(self):
        """Start rank-zero Blender coordination after MPI model setup.

        Call this on every rank after ``init_mpi``.  It returns immediately on
        rank zero, which remains available to Blender; worker ranks enter the
        request loop and return only after ``stop_mpi_coordinator`` is called
        on rank zero.
        """
        if self.parallel_ctx is None or int(self.parallel_ctx.nhost()) == 1:
            return
        if int(self.parallel_ctx.id()) == 0:
            self.mpi_coordinator_active = True
            if self.mpimap is None:
                fragments = self._mpi_request("discover_mpimap", None)
                self.mpimap = self._build_automatic_mpimap(fragments)
                self._mpi_request("set_mpimap", self.mpimap)
            return
        self._serve_mpi_requests()

    def stop_mpi_coordinator(self):
        """Stop worker request loops.  This must be called from rank zero."""
        if not self._uses_mpi_coordinator():
            return
        self._mpi_request("__stop__", None)
        self.mpi_coordinator_active = False

    def _uses_mpi_coordinator(self):
        return (self.mpi_coordinator_active and self.parallel_ctx is not None and
                int(self.parallel_ctx.nhost()) > 1 and int(self.parallel_ctx.id()) == 0)

    def _serve_mpi_requests(self):
        rank_count = int(self.parallel_ctx.nhost())
        while True:
            command = self.parallel_ctx.py_alltoall([None] * rank_count)[0]
            operation, payload = command
            if operation == "__stop__":
                self.parallel_ctx.py_alltoall([None] * rank_count)
                return
            response = self._mpi_operation_response(operation, payload)
            self.parallel_ctx.py_alltoall([response] + [None] * (rank_count - 1))

    def _mpi_request(self, operation, payload):
        """Broadcast an operation and gather one response from every rank."""
        if not self._uses_mpi_coordinator():
            raise RuntimeError("MPI coordinator requests must originate on rank zero")
        return self._mpi_request_targeted(
            operation, [payload] * int(self.parallel_ctx.nhost()))

    def _mpi_request_targeted(self, operation, payloads):
        """Deliver one payload per destination, then drain every response."""
        if not self._uses_mpi_coordinator():
            raise RuntimeError("MPI coordinator requests must originate on rank zero")
        rank_count = int(self.parallel_ctx.nhost())
        if len(payloads) != rank_count:
            raise ValueError("Expected one MPI payload per rank")
        self.parallel_ctx.py_alltoall([(operation, payload) for payload in payloads])
        payload = payloads[0]
        local_response = ({"ok": True, "result": None}
                          if operation == "__stop__" else
                          self._mpi_operation_response(operation, payload))
        responses = self.parallel_ctx.py_alltoall(
            [local_response] + [None] * (rank_count - 1))
        for rank, response in enumerate(responses):
            if response is not None and not response["ok"]:
                logger.debug("MPI rank %d failed %s", rank, operation)
                raise RuntimeError("MPI rank %d failed %s:\n%s" %
                                   (rank, operation, response["error"]))
        results = [response["result"] for response in responses if response is not None]
        if operation in ("initialize_groups", "get_group_dicts"):
            return [deserialize(result) for result in results]
        return results

    def _mpi_operation_response(self, operation, payload):
        try:
            return {"ok": True, "result": self._execute_mpi_operation(operation, payload)}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}

    def _execute_mpi_operation(self, operation, payload):
        if operation == "discover_mpimap":
            return self._discover_local_cells()
        if operation == "set_mpimap":
            self.mpimap = payload
            return None
        if operation == "run_simulation":
            self._run_simulation_local()
            return None
        if operation == "get_roots":
            return self._get_roots_local()
        if operation == "initialize_groups":
            self._initialize_groups_local(payload)
            return serialize(self._get_group_dicts_local(run_simulation=True))
        if operation == "get_group_dicts":
            return serialize(self._get_group_dicts_local(run_simulation=True))
        if operation == "set_sim_params":
            return self._set_sim_params_local(payload)
        if operation == "update_groups":
            return self._update_groups_local(deserialize(payload))
        if operation == "validate_synapse_sections":
            return self._validate_synapse_sections_local(payload)
        if operation == "create_synapses":
            return self._create_synapses_local(payload)
        raise ValueError("Unsupported MPI operation: " + operation)

    def _discover_local_cells(self):
        roots = h.SectionList()
        roots.allroots()
        cells = []
        for section in roots:
            match = self.section_rx.match(section.name())
            if match is None:
                raise ValueError("Cannot derive an MPI cell name from root section '%s'; "
                                 "pass mpimap explicitly" % section.name())
            cells.append(match.group(1))
        return cells

    @staticmethod
    def _build_automatic_mpimap(fragments):
        mpimap = {}
        counts = {}
        for cells in fragments:
            for cell_name in cells:
                counts[cell_name] = counts.get(cell_name, 0) + 1

        for rank, cells in enumerate(fragments):
            for cell_name in cells:
                blender_name = cell_name
                if counts[cell_name] > 1:
                    stem, index = cell_name.rsplit("[", 1)
                    blender_name = "%s_rank%d[%s" % (stem, rank, index)
                    # Preserve deterministic identities even if a model already
                    # has a cell whose name happens to match this convention.
                    while blender_name in mpimap:
                        blender_name = "%s_mpi%d[%s" % (stem, rank, index)
                mpimap[blender_name] = {"name": cell_name, "rank": rank}
        return mpimap


    def get_roots(self):
        if self._uses_mpi_coordinator():
            roots = []
            for rank, fragment in enumerate(self._mpi_request("get_roots", None)):
                roots.extend(fragment)
                for root in fragment:
                    self._restore_blender_section_names(root, rank)
            return sorted(roots, key=lambda root: root["name"])
        return self._get_roots_local()

    def _get_roots_local(self):
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
        if self._uses_mpi_coordinator():
            fragments = self._mpi_request("initialize_groups", blender_groups)
            result = self.merge_mpi_group_fragments(fragments)
            return self.compress(result) if send_back else None
        self._initialize_groups_local(blender_groups)
        if send_back:
            return self.get_group_dicts()

    def _initialize_groups_local(self, blender_groups):

        for group in getattr(self, "groups", {}).values():
            group.close()
        self.groups = OrderedDict()

        if self.section_index is None:
            self.update_section_index()

        for blender_group in blender_groups:
            name = blender_group["name"]

            nrn_group = NeuronRootGroup()
            nrn_group.from_skeletal_blender_group(blender_group, node=self)

            self.groups[name] = nrn_group

    def get_group_dicts(self, compressed=True):
        """Return the selected groups, gathering rank-local roots under MPI.

        When MPI is enabled this is a collective operation: every rank must call
        it in the same order.  Only rank zero receives the complete result;
        non-root ranks return ``None``.  Keeping the collective boundary here
        means a caller can send precisely one complete payload to Blender.
        """

        if self._uses_mpi_coordinator():
            result = self.merge_mpi_group_fragments(
                self._mpi_request("get_group_dicts", None))
        else:
            result = self._get_group_dicts_local(run_simulation=True)
            result = self.gather_group_dicts(result)

        if result is None:
            return None

        if compressed:
            return self.compress(result)
        else:
            return result

    def run_simulation(self):
        """Initialize and run, dispatching to every rank under the coordinator.

        Without the coordinator, MPI callers must call this on every rank.
        """
        if self._uses_mpi_coordinator():
            self._mpi_request("run_simulation", None)
        else:
            self._run_simulation_local()
        return True

    def _run_simulation_local(self):
        if self.parallel_ctx is not None and int(self.parallel_ctx.nhost()) > 1:
            self.parallel_ctx.set_maxstep(1.0)
            h.stdinit()
            self.parallel_ctx.psolve(h.tstop)
        else:
            h.run()

    def _get_group_dicts_local(self, run_simulation):
        if run_simulation:
            record_activity = any(g.record_activity for g in self.groups.values())
            if self.parallel_ctx is not None and int(self.parallel_ctx.nhost()) > 1:
                # Even ranks with no recorded groups must enter the solver.
                record_activity = self.parallel_ctx.allreduce(int(record_activity), 2)
            if record_activity:
                self._run_simulation_local()
        return self._get_local_group_dicts()

    def _get_local_group_dicts(self):
        """Serialize just the roots owned by this MPI rank."""
        return [group.to_dict(include_activity=group.record_activity,
                              include_root_children=True,
                              include_coords_and_radii=True)
                for group in self.groups.values()]

    def gather_group_dicts(self, local_groups):
        """Gather local group dictionaries on rank zero and merge their roots.

        ``ParallelContext.py_alltoall`` is used rather than an external MPI
        dependency.  Each rank sends its local fragment only to rank zero, so
        large activity traces are not replicated on every worker.
        """
        if self.parallel_ctx is None or int(self.parallel_ctx.nhost()) == 1:
            return local_groups

        rank_count = int(self.parallel_ctx.nhost())
        fragments = self.parallel_ctx.py_alltoall(
            [serialize(local_groups)] + [None] * (rank_count - 1))

        if int(self.parallel_ctx.id()) != 0:
            return None

        return self.merge_mpi_group_fragments(
            [deserialize(fragment) if fragment is not None else None
             for fragment in fragments])

    def merge_mpi_group_fragments(self, fragments):
        """Merge rank fragments deterministically, restoring Blender names."""
        groups_by_name = OrderedDict()
        for rank, fragment in enumerate(fragments):
            if fragment is None:
                continue
            for group in fragment:
                name = group["name"]
                if name not in groups_by_name:
                    merged = group.copy()
                    merged["roots"] = []
                    groups_by_name[name] = merged
                else:
                    merged = groups_by_name[name]
                    self._check_mpi_group_activity(merged, group)

                for root in group["roots"]:
                    self._restore_blender_section_names(root, rank)
                    root_name = root["name"]
                    if any(existing["name"] == root_name for existing in merged["roots"]):
                        raise ValueError("MPI group '%s' contains duplicate root '%s'" %
                                         (name, root_name))
                    merged["roots"].append(root)

        for group in groups_by_name.values():
            group["roots"].sort(key=lambda root: root["name"])

        return list(groups_by_name.values())

    @staticmethod
    def _check_mpi_group_activity(merged, fragment):
        """Reject divergent sampling schedules before Blender sees bad data."""
        if "activity" not in merged or "activity" not in fragment:
            return
        if merged["activity"]["times"] != fragment["activity"]["times"]:
            raise ValueError("MPI group '%s' has inconsistent activity sample times" %
                             merged["name"])

    def _restore_blender_section_names(self, root, rank=None):
        """Translate MPI-local cell-name prefixes back to Blender's names."""
        if self.mpimap is None:
            return

        mpi_to_blender = {
            entry["name"]: original_name
            for original_name, entry in self.mpimap.items()
            if rank is None or entry["rank"] == rank
        }
        stack = [root]
        while stack:
            section = stack.pop()
            mpi_cell_name, suffix = self.section_rx.match(section["name"]).groups()
            if mpi_cell_name in mpi_to_blender:
                section["name"] = mpi_to_blender[mpi_cell_name] + (
                    "." + suffix if suffix else "")
            stack.extend(section.get("children", []))

    def update_groups(self, blender_groups):
        """Apply group dictionaries, serialized groups, or flat group-file tables.

        A file loaded with json.load() can be passed as one item in the list.
        Call deserialize() first if application code needs to inspect its roots.
        """
        if isinstance(blender_groups, xmlrpclib.Binary):
            blender_groups = self.decompress(blender_groups)
        elif isinstance(blender_groups, string_types + (dict,)):
            blender_groups = deserialize(blender_groups)
            if isinstance(blender_groups, dict):
                blender_groups = [blender_groups]
        if any(isinstance(group, string_types) or "__blenderneuron_flat__" in group
               for group in blender_groups):
            blender_groups = [deserialize(group)
                              if isinstance(group, string_types) or
                              "__blenderneuron_flat__" in group else group
                              for group in blender_groups]
        if self._uses_mpi_coordinator():
            partitions = self._partition_morphology_updates(blender_groups)
            self._mpi_request_targeted("update_groups", [serialize(part) for part in partitions])
            return
        self._update_groups_local(blender_groups)

    def _partition_morphology_updates(self, blender_groups):
        """Validate the entire export before constructing destination envelopes.

        Keep metadata on all ranks: recording settings also govern existing
        groups whose roots were not selected for this export. Root trees are
        shared read-only here; each destination receives a flat JSON payload.
        A mapping has one entry per visible cell, so conflicting duplicate keys
        cannot be represented by the supported mpimap dictionary format.
        """
        rank_count = int(self.parallel_ctx.nhost())
        partitions = [[] for _ in range(rank_count)]
        seen = set()
        for group in blender_groups:
            envelopes = [dict(group, roots=[]) for _ in range(rank_count)]
            for root in group["roots"]:
                name = root["name"]
                context = "group %r root %r" % (group["name"], name)
                if name in seen:
                    raise ValueError("Duplicate Blender root in " + context)
                seen.add(name)
                match = self.section_rx.match(name)
                cell = match.group(1) if match else name
                if self.mpimap is None or cell not in self.mpimap:
                    raise ValueError("Missing ownership for " + context)
                rank = self.mpimap[cell]["rank"]
                # ParallelContext.id() historically supplies integral floats.
                if (isinstance(rank, bool) or not isinstance(rank, (int, float))
                        or not 0 <= rank < rank_count or int(rank) != rank):
                    raise ValueError("Invalid ownership rank %r for %s" % (rank, context))
                envelopes[int(rank)]["roots"].append(root)
            for rank, envelope in enumerate(envelopes):
                partitions[rank].append(envelope)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("update_groups: %d groups, %d roots, %d serialized bytes",
                         len(blender_groups), len(seen), len(serialize(blender_groups).encode("utf-8")))
            for rank, partition in enumerate(partitions):
                logger.debug("update_groups rank %d: %d roots, %d serialized bytes",
                             rank, sum(len(g["roots"]) for g in partition),
                             len(serialize(partition).encode("utf-8")))
        return partitions

    def _update_groups_local(self, blender_groups):

        for blender_group in blender_groups:
            name = blender_group["name"]

            if name not in self.groups:
                self._initialize_groups_local(blender_groups)

            nrn_group = self.groups[name]
            nrn_group.from_updated_blender_group(blender_group)

    def set_sim_params(self, params):
        if self._uses_mpi_coordinator():
            self._mpi_request("set_sim_params", params)
            return
        self._set_sim_params_local(params)

    def _set_sim_params_local(self, params):
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
        Only one gid can be associated with a segment. If more than one gid is assigned to a seg,
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
        if self._uses_mpi_coordinator():
            partitions, checks = self._partition_synapse_set(syn_set)
            # A read-only collective checks rank-local sections before any rank
            # creates point processes, spines, GIDs, or replaces retained sets.
            self._mpi_request_targeted("validate_synapse_sections", checks)
            self._mpi_request_targeted("create_synapses", partitions)
            return
        self._create_synapses_local(syn_set)

    def _partition_synapse_set(self, syn_set):
        """Route each entry to the union of endpoint owners, in input order."""
        count = int(self.parallel_ctx.nhost())
        parts = [dict(syn_set, entries=[], _entry_indices=[]) for _ in range(count)]
        checks = [dict(name=syn_set['name'], sections=[]) for _ in range(count)]
        for index, entry in enumerate(syn_set['entries']):
            context = "synapse set %r entry %d" % (syn_set['name'], index)
            required = ['source_section', 'dest_section', 'source_x', 'dest_x',
                        'source_seg_i', 'dest_syn', 'dest_syn_params', 'threshold',
                        'delay', 'weight', 'create_spine', 'is_reciprocal']
            if entry.get('is_reciprocal'):
                required += ['dest_seg_i', 'source_syn', 'source_syn_params']
            if entry.get('create_spine'):
                required += ['prefix', 'head_start', 'head_end', 'head_diameter',
                             'neck_start']
                if entry.get('neck_start') is not None:
                    required += ['neck_end', 'neck_diameter']
            for field in required:
                if field not in entry:
                    raise ValueError("Missing %s in %s" % (field, context))
            owners = set()
            for field in ('source_section', 'dest_section'):
                section = entry.get(field)
                if not isinstance(section, string_types) or not section:
                    raise ValueError("Missing %s in %s" % (field, context))
                match = self.section_rx.match(section)
                cell = match.group(1) if match else section
                if self.mpimap is None or cell not in self.mpimap:
                    raise ValueError("Missing ownership for %s %r in %s" %
                                     (field, section, context))
                rank = self.mpimap[cell].get('rank')
                if (isinstance(rank, bool) or not isinstance(rank, (int, float))
                        or not 0 <= rank < count or int(rank) != rank):
                    raise ValueError("Invalid ownership rank %r in %s (%s)" %
                                     (rank, context, field))
                rank = int(rank)
                owners.add(rank)
                checks[rank]['sections'].append((index, field, section))
            for rank in sorted(owners):
                parts[rank]['entries'].append(entry)
                parts[rank]['_entry_indices'].append(index)
        return parts, checks

    def _validate_synapse_sections_local(self, payload):
        # Refresh names without altering model geometry or retained synapses.
        self.update_section_index()
        for index, field, section in payload['sections']:
            local = self.rank_section_name(section)
            if local is None or local not in self.section_index:
                raise ValueError("Missing %s %r in synapse set %r entry %d" %
                                 (field, section, payload['name'], index))

    def _create_synapses_local(self, syn_set):

        set_name = syn_set['name']
        syn_entries = syn_set['entries']

        synapses = self.synapse_sets[set_name] = []

        for entry_index, entry in enumerate(syn_entries):

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
                # Preserve broadcast-era spine names when unrelated entries
                # have been omitted from this rank's payload.
                original_index = syn_set.get('_entry_indices', range(len(syn_entries)))[entry_index]
                prefix = set_name+"_"+entry['prefix']+"["+str(original_index)+"]"

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
