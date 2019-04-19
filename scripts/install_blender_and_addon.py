import os, re

skip_download = os.path.exists('./blender')

if not skip_download:
    from latest_blender_url import get_latest
    latest_url = get_latest()

    print('Downloading Blender', latest_url)
    import os
    os.system('curl -L -o blender.tar.bz2 ' + latest_url)
    os.system('tar xvjf blender.tar.bz2')

    # rename dir to just blender
    d = '.'
    new_dir = os.path.join(d,'blender')
    print('Renaming dir to', new_dir)

    blender_dir = next(os.path.join(d, o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o)) and o.startswith('blender-'))
    os.renames(blender_dir,new_dir)
else:
    print('Blender folder found, skipped download')

# Find addon sub-dir
d='blender'
ver_dir = next(os.path.join(d, o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o)) and re.search('\d',o) is not None)
addons_dir = os.path.join(ver_dir,'scripts','addons')
print('Addons found in', addons_dir)

# Cythonize the latest addon version
os.chdir('ForBlender/blender_neuron')
os.system('pip install cython')
os.system('python setup.py build_ext --inplace')
os.chdir('..')
os.system('./buildzip.sh')
os.chdir('..')

# Unzip the addon to Blender addons dir
os.system('unzip -o ForBlender/blender_neuron_addon_v.zip -d ' + addons_dir)
