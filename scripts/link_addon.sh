# Start container shell in /BlenderNEURON
echo 'cd /BlenderNEURON' >> /root/.bashrc
echo 'export BLENDER_SYSTEM_SCRIPTS=/BlenderNEURON/blender_scripts' >> /root/.bashrc

# Create a symbolic link from folder mapped to container to Blender addon folder
BLENDER_SYSTEM_SCRIPTS=${BLENDER_SYSTEM_SCRIPTS:-/BlenderNEURON/blender_scripts}
mkdir -p $BLENDER_SYSTEM_SCRIPTS/addons
ln -sfn /BlenderNEURON/blenderneuron $BLENDER_SYSTEM_SCRIPTS/addons/blenderneuron

# Enable the addon within blender ('check the box')
blender --python enable_addon.py --background -noaudio
