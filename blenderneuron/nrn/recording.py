"""Native activity recording and user-facing variable lookup."""
from blenderneuron.compat import Sequence, finalize
import math
import weakref

from neuron import h

from blenderneuron.activity import Activity


# NEURON 8.2 deletes a record event without cancelling its queued delivery when
# play_remove() is called mid-run. CVode also retains native recording lists.
# Quiesce retired schedules and detach only at the next initialization, after
# NEURON clears its event queue. This also covers deletion between runs.
_retired = {}


def _release_vectors(vectors):
    for vector in vectors:
        vector.play_remove()
    del vectors[:]


def _release_retired():
    for data in _retired.values():
        _release_vectors(data[0])
    _retired.clear()


_retirement_fih = h.FInitializeHandler(0, _release_retired)


def _retire_vectors(vectors, schedule, local_times):
    if not vectors:
        return
    count = max(len(vector) for vector in vectors)
    # Leave exactly the time needed by each pending native event. Its delivery
    # then cannot enqueue another sample. Retain both vectors and time storage.
    size = min(count + 1, len(schedule))
    schedule.resize(size)
    for vector, times in zip(vectors, local_times):
        times.resize(min(len(vector) + 1, len(times)))
    token = object()
    _retired[token] = (vectors, schedule, local_times)


def get_recording_value(segment, variable):
    """Read a segment attribute or a dotted mechanism path such as ``pas.i``."""
    value = segment
    for attribute in variable.split('.'):
        value = getattr(value, attribute)
    return value


def get_recording_reference(segment, variable):
    """Translate ordinary names to NEURON references internally."""
    path = variable.split('.')
    owner = segment
    for attribute in path[:-1]:
        owner = getattr(owner, attribute)
    return getattr(owner, '_ref_' + path[-1])


class RecordedValues(Sequence):
    """Read live native storage without making a second full set of Python floats."""
    def __init__(self, vector):
        self.vector = vector

    def __len__(self):
        return len(self.vector)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self.vector[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return self.vector[index]

    def __iter__(self):
        return iter(self.vector)

    def __eq__(self, other):
        return list(self) == list(other)

class RecordedTimes(Sequence):
    """Label samples with requested times, independent of solver clock staggering."""
    def __init__(self, vector, schedule):
        self.vector, self.schedule = vector, schedule

    def __len__(self):
        return len(self.vector)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return self.schedule[index]

    def __eq__(self, other):
        return list(self) == list(other)

class VectorRecorder(object):
    """One native trace per compartment; grow the schedule ahead of the solver.

    The schedule is extended halfway through each block, before its final event
    can be consumed. This needs no tstop, preserves start + n*period, and adds
    one lightweight scheduling callback per block rather than per sample.
    """
    BLOCK_SIZE = 4096

    def __init__(self, group):
        self.active = True
        self.vectors = []
        self.local_times = []
        self.schedule = h.Vector()
        self.start, self.period = group.recording_time_start, group.recording_period
        self._finalizer = finalize(self, _retire_vectors, self.vectors,
                                          self.schedule, self.local_times)
        self._finalizer.atexit = False
        end = group.recording_time_end
        self.limit = None if end == 0 else max(0, int(math.floor((end - self.start) / self.period + 1e-9)) + 1)
        self._extend()
        unique = {}
        cvode = h.CVode()
        local_dt = bool(cvode.active() and cvode.use_local_dt())
        stack = list(reversed(list(group.roots.values())))
        while stack:
            node = stack.pop()
            sec = node.nrn_section
            if group.recording_granularity == '3D Segment':
                targets = enumerate(node._segment_midpoints)
            else:
                targets = [(None, .5)]
            for index, x in targets:
                compartment = ('endpoint', x) if x in (0, 1) else int(x * sec.nseg)
                key = (sec, compartment)
                if key not in unique:
                    vector = h.Vector()
                    pointer = get_recording_reference(sec(x), group.record_variable)
                    if local_dt:
                        times = self.schedule.c()
                        cvode.record(pointer, vector, times, 1, sec=sec)
                        self.local_times.append(times)
                    else:
                        vector.record(pointer, self.schedule)
                    unique[key] = vector
                    self.vectors.append(vector)
                activity = node.activity if index is None else node.segment_activity.setdefault(index, Activity())
                activity.values = RecordedValues(unique[key])
            if group.recording_granularity != 'Cell':
                stack.extend(reversed(node.children))
        if self.vectors:
            group.activity.times = RecordedTimes(self.vectors[0], self.schedule)
        recorder_ref = weakref.ref(self)

        def extend_schedule():
            recorder = recorder_ref()
            if recorder is not None and recorder.active:
                recorder._extend()
                recorder.schedule_extension()

        self._extend_callback = extend_schedule

    def _extend(self):
        first = len(self.schedule)
        stop = first + self.BLOCK_SIZE
        if self.limit is not None:
            stop = min(stop, self.limit)
        addition = h.Vector([self.start + i * self.period for i in range(first, stop)])
        self.schedule.append(addition)
        for times in self.local_times:
            times.append(addition)

    def schedule_extension(self):
        if self.active and self.vectors and (self.limit is None or len(self.schedule) < self.limit):
            index = max(0, len(self.schedule) - self.BLOCK_SIZE // 2)
            h.CVode().event(self.schedule[index], self._extend_callback)

    def close(self, queue_cleared=False):
        self.active = False
        if queue_cleared:
            self._finalizer.detach()
            _release_vectors(self.vectors)
            del self.local_times[:]
        else:
            self._finalizer()
