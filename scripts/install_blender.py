import os, re

skip_download = os.path.exists('./blender')

if not skip_download:
    latest_url = 'https://mirror.clarkson.edu/blender/release/Blender2.79/blender-2.79b-linux-glibc219-x86_64.tar.bz2'

    print('Downloading Blender', latest_url)
    import os
    os.system('curl -L -o blender.tar.bz2 ' + latest_url)
    os.system('tar xjf blender.tar.bz2')

    # rename dir to just blender
    d = '.'
    new_dir = os.path.join(d,'blender')
    print('Renaming dir to', new_dir)

    blender_dir = next(os.path.join(d, o) for o in os.listdir(d) if os.path.isdir(os.path.join(d,o)) and o.startswith('blender-'))
    os.renames(blender_dir,new_dir)

    print('Blender installed in: ', os.path.abspath(new_dir))
else:
    print('Blender folder found, skipped download')


