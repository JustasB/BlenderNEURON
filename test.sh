scripts/install_neuron.sh

python scripts/install_blender_and_addon.py
./blender/blender --python scripts/install_enable_addon.py --background

py.test --cov=ForNEURON/blenderneuron tests/test_client.py
