python scripts/install_blender_and_addon.py
./blender/blender --python scripts/install_enable_addon.py --background

scripts/install_neuron.sh

py.test --cov=ForNEURON/blenderneuron tests/test_client.py
