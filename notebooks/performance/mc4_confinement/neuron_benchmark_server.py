from pathlib import Path
import sys,time,re,inspect
from neuron import h
# The benchmark launches this with exec(compile(...)), which need not set __file__.
ROOT=Path(inspect.currentframe().f_code.co_filename).resolve().parent
sys.path.insert(0,str(ROOT))
h.load_file('stdrun.hoc')
# Geometry-only instantiation: retain topology and pt3d, omit custom channels.
source=(ROOT/'MC4.hoc').read_text().replace('  biophys()','  // biophysics omitted for geometry inspection')
source=re.sub(r'(?m)^\s*insert \w+\s*$', '', source)
path=ROOT/'MC4_geometry.hoc';path.write_text(source)
h.load_file(str(path))
cell=h.MC4()
from MCTransforms import TransformMC4
TransformMC4.apply_on(cell.hname())
from blenderneuron.nrn.neuronnode import NeuronNode
node=NeuronNode()
while True:time.sleep(1)
