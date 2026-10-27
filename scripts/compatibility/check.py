"""Native NEURON smoke check for the Python 2 assessment."""
from __future__ import print_function

import sys

from neuron import h

print("Python:", sys.version)
print("NEURON:", h.nrnversion())
h.load_file('stdrun.hoc')
section = h.Section(name='compatibility_soma')
section.insert('pas')
times = h.Vector()
values = h.Vector()
times.record(h._ref_t, 0.1)
values.record(section(0.5).pas._ref_i, 0.1)
h.finitialize(-65)
h.continuerun(1.05)  # Step past the final 1.0-ms recording event.
assert len(times) == len(values) == 11, (len(times), len(values))
assert all(abs(times[index] - index * 0.1) < 1e-9 for index in range(11))
print("NEURON native vector recording: PASS")
