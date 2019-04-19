neuron_v=7.5
iv_v=19
export CPU=x86_64

start_dir=$(pwd)

sudo apt-get update

sudo apt-get install libx11-dev libxt-dev gnome-devel

sudo apt-get install mpich

sudo apt-get install libncurses-dev xfonts-100dpi

pip install --upgrade pip

pip install scipy numpy matplotlib cython mpi4py neuronpy

curl -o nrn.tar.gz https://neuron.yale.edu/ftp/neuron/versions/v$neuron_v/nrn-$neuron_v.tar.gz

curl -o iv.tar.gz https://neuron.yale.edu/ftp/neuron/versions/v$neuron_v/iv-$iv_v.tar.gz

tar -xvzf nrn.tar.gz

tar -xvzf iv.tar.gz

rm *.tar.gz

mkdir ~/neuron

mv nrn-$neuron_v ~/neuron/nrn

mv iv-$iv_v ~/neuron/iv

cd ~/neuron/iv

./configure --prefix=`pwd`

make

make install

cd ~/neuron/nrn

python_loc=$(which python)

./configure --prefix=`pwd` --with-iv=$HOME/neuron/iv --with-paranrn --with-nrnpython=$python_loc

make

make install

export IV=$HOME/neuron/iv

export N=$HOME/neuron/nrn

export PATH="$IV/$CPU/bin:$N/$CPU/bin:$PATH"

cd ~/neuron/nrn/srcs
