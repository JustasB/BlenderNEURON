from neuron import h
from blenderneuron.client import BlenderNEURON
bn = BlenderNEURON(h)

h.load_file("SnakeCell.hoc")

sc = h.SnakeCell()

syn = h.Exp2Syn(0.5, sec=sc.soma)
syn.g = 10

nc = h.NetCon(sc.dend[25](0.5)._ref_v, syn, sec=sc.dend[25])
nc.weight[0] = 1
nc.delay = 20

ic = h.IClamp(0.5, sec=sc.soma)
ic.delay = 1
ic.dur = 1
ic.amp = 0.5

#
s1 = h.Section(name="Soma1")
s2 = h.Section(name="Soma2")
s1.L = s1.diam = s2.L = s2.diam = 10

syn = h.Exp2Syn(0.5, sec=s2)
syn.g = 10

nc = h.NetCon(s1(0.5)._ref_v, syn, sec=s1)
nc.weight[0] = 1

