"""Script-owned recording and offline export, without a communication node."""
from collections import OrderedDict

from neuron import h

from blenderneuron.nrn.neuronrootgroup import NeuronRootGroup
from blenderneuron.nrn.neuronsection import NeuronSection
from blenderneuron.results import (RECORDING_KEYS,
                                  validate_display, validate_recording, write_snapshot)
from blenderneuron.utils import serialize, deserialize


class SimulationExport:
    """Configure groups, prepare collectively, run your model, then save collectively.

    ``roots`` passed to add_group are local NEURON root sections (e.g. cell.soma).
    Saving before any samples are collected exports morphology only.
    Set record_activity=False to disable collection for a group explicitly.
    No call in this class initializes, advances, or reruns the simulation.
    """
    def __init__(self, parallel_context=None):
        self.pc = parallel_context
        self.rank = int(parallel_context.id()) if parallel_context is not None else 0
        self.nhost = int(parallel_context.nhost()) if parallel_context is not None else 1
        self.groups = OrderedDict()
        self.specs = OrderedDict()
        self.prepared = False

    def add_group(self, name, roots, recording_granularity='Cell', record_variable='v',
                  recording_period=1.0, recording_time_start=0.0,
                  recording_time_end=0.0, variable_units=None, display=None, record_activity=True):
        """Declare a rank-local group. Empty membership on a rank is allowed."""
        if self.prepared:
            raise RuntimeError('Configure all groups before prepare()')
        if not isinstance(name, str) or not name or name in self.specs:
            raise ValueError('Group names must be nonempty and unique on each rank')
        if not isinstance(record_activity, bool):
            raise ValueError('record_activity must be a boolean')
        self.specs[name] = dict(
            roots=list(roots), record_activity=record_activity, recording_granularity=recording_granularity,
            record_variable=record_variable, recording_period=recording_period,
            recording_time_start=recording_time_start, recording_time_end=recording_time_end,
            variable_units=('mV' if record_variable == 'v' else '') if variable_units is None else variable_units,
            display={} if display is None else dict(display))
        return self

    def _gather(self, value):
        if self.nhost == 1:
            return [value]
        parts = self.pc.py_alltoall([serialize(value)] + [None] * (self.nhost - 1))
        return [deserialize(p) for p in parts] if self.rank == 0 else None

    def _finish(self, error):
        if self.nhost > 1:
            error = self.pc.py_broadcast(error, 0)
        if error:
            raise ValueError(error)

    def prepare(self):
        """Install NetStim/NetCon collectors before finitialize; call on every rank."""
        if self.prepared:
            raise RuntimeError('Export already prepared')
        error = None
        try:
            self._prepare_local()
        except Exception as exc:
            error = 'Rank %d: %s' % (self.rank, exc)
        parts = self._gather({'error': error, 'settings': {
            name: {key: value for key, value in spec.items() if key != 'roots'}
            for name, spec in self.specs.items()}})
        if self.rank == 0:
            settings = {}
            for part in parts:
                error = error or part['error']
                for name, spec in part['settings'].items():
                    if name in settings and settings[name] != spec:
                        error = error or 'Inconsistent settings across ranks for group %r' % name
                    settings[name] = spec
            if not settings:
                error = error or 'Configure at least one group'
        self._finish(error)
        self.prepared = True
        return self

    def _prepare_local(self):
        seen = set()
        for name, spec in self.specs.items():
            validate_display(spec['display'])
            level = spec['recording_granularity']
            validate_recording(spec)
            group = NeuronRootGroup()
            group.name, group.record_activity = name, spec['record_activity']
            for key in RECORDING_KEYS:
                setattr(group, key, spec[key])
            self.groups[name] = group
            for sec in spec['roots']:
                if sec.parentseg() is not None:
                    raise ValueError('Group %r requires root sections: %s' % (name, sec.name()))
                if sec.name() in seen:
                    raise ValueError('Cell appears in multiple groups: ' + sec.name())
                seen.add(sec.name())
                root = NeuronSection()
                root.from_nrn_section(sec, group)
                group.roots[root.name] = root
                stack = [(root, True)]
                while stack:
                    node, is_root = stack.pop()
                    if node.point_count < 2:
                        raise ValueError('Section has fewer than two morphology points: ' + node.name)
                    targets = []
                    if group.record_activity and level == '3D Segment':
                        node._build_segment_midpoints()
                        targets.extend(node._segment_midpoints)
                    elif group.record_activity and (level == 'Section' or is_root):
                        targets.append(0.5)
                    for x in targets:
                        try:
                            getattr(node.nrn_section(x), spec['record_variable'])
                        except AttributeError as exc:
                            raise ValueError('Group %r, cell %s, section %s: missing variable %s' %
                                             (name, root.name, node.name, spec['record_variable'])) from exc
                    stack.extend((child, False) for child in node.children)

            # Reuse the live path's initialization reset and event collector.
            # Keep both handlers alive with the export-owned group.
            if group.record_activity and group.roots:
                group.fih = h.FInitializeHandler(group.prepare_activity)
                group.create_collector()

    def _local_results(self):
        result = []
        for name, group in self.groups.items():
            # An unrun model (or a recording window with no samples) still has
            # useful morphology. Decide per save so a later run can add activity.
            include_activity = group.record_activity and bool(group.activity.times)
            data = group.to_dict(include_activity, True, True)
            data['record_activity'] = include_activity
            data['variable_units'] = group.variable_units
            data['display'] = self.specs[name]['display']
            if self.nhost > 1:
                stack = list(data['roots'])
                while stack:
                    node = stack.pop()
                    node['name'] = 'rank%d::%s' % (self.rank, node['name'])
                    stack.extend(node['children'])
            result.append(data)
        return result

    @staticmethod
    def _merge(parts):
        merged = OrderedDict()
        for part in parts:
            for group in part:
                name = group['name']
                # Empty ranks do not contribute a time axis.
                if not group['roots']:
                    continue
                if name not in merged:
                    merged[name] = group
                    continue
                dest = merged[name]
                if (dest['record_activity'] != group['record_activity'] or
                        (group['record_activity'] and
                         dest['activity']['times'] != group['activity']['times'])):
                    raise ValueError('Inconsistent sample times for group ' + name)
                dest['roots'].extend(group['roots'])
        return list(merged.values())

    def save(self, path):
        """Gather into rank 0 and atomically write one .bnresults file.

        Call on all ranks after prepare(), with or without running a simulation.
        Groups with no collected samples save morphology only. File/validation
        failures propagate to every rank, including ranks without local groups.
        """
        if not self.prepared:
            raise RuntimeError('Call prepare() before running the simulation')
        error, groups = None, None
        try:
            groups = self._local_results()
        except Exception as exc:
            error = 'Rank %d: %s' % (self.rank, exc)
        parts = self._gather({'error': error, 'groups': groups})
        if self.rank == 0:
            try:
                for part in parts:
                    if part['error']:
                        raise ValueError(part['error'])
                write_snapshot(path, self._merge([p['groups'] for p in parts]))
            except Exception as exc:
                error = 'Could not save simulation results: %s' % exc
        self._finish(error)
