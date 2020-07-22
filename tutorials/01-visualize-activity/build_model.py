from neuron import h

h.load_file('TestCell.hoc')

cell1 = h.TestCell()
cell2 = h.TestCell()
cell3 = h.TestCell()

#Position cells side by side
cell1.position(0, -200, 0)
cell3.position(0, 200, 0)

# Insert electrodes
ic1 = h.IClamp(0.5, sec=cell1.soma)

# A distant dendrite
ic2 = h.IClamp(1, sec=cell2.dendrites[29])

# A dendrite on the opposite side of ic2
ic3 = h.IClamp(1, sec=cell3.dendrites[18])

stims = [ic1, ic2, ic3]

# A 1ms long input stimulus at 10ms
for ic in stims:
    ic.delay = 10
    ic.dur = 1
    ic.amp = 1

# Will run the simulation for 20 ms
h.tstop = 20
    


