# Start container shell in /BlenderNEURON
echo 'cd /BlenderNEURON' >> /root/.bashrc

# Create a symbolic link from folder mapped to container to Blender addon folder
ln -s /BlenderNEURON/blenderneuron /blender/3.5/scripts/addons/blenderneuron

# Enable the addon within blender ('check the box')
blender/blender --python enable_addon.py --background -noaudio
