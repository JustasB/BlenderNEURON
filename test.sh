scripts/install_neuron.sh

python scripts/install_blender_and_addon.py
python scripts/install_enable_addon.py

py.test --cov=ForNEURON/blenderneuron tests/test_client.py
