import os, re

skip_download = os.path.exists('./blender')

if not skip_download:
    latest_url = 'https://mirror.clarkson.edu/blender/release/Blender3.5/blender-3.5.1-linux-x64.tar.xz'

    print('Downloading Blender', latest_url)
    import os
    os.system('curl -L -o blender.tar.xz ' + latest_url)
    os.system('tar xJf blender.tar.xz')

    # rename dir to just blender
    d = '.'
    new_dir = os.path.join(d, 'blender')
    print('Renaming dir to', new_dir)

    blender_dir = next(os.path.join(d, o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o)) and o.startswith('blender-'))
    os.renames(blender_dir,new_dir)

    print('Blender installed in: ', os.path.abspath(new_dir))
else:
    print('Blender folder found, skipped download')


