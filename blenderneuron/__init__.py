try:
    import bpy
    inside_blender = True
except:
    inside_blender = False


import os
if 'COVERAGE_PROCESS_START' in os.environ:
    try:
        print('Importing COVERAGE: Inside ', "BLENDER" if inside_blender else "NEURON")
        import coverage
        COV = coverage.process_startup()
    except:
        print('Coverage error. Skipping coverage')

if inside_blender:
    from ._blender import make_blender_addon
    make_blender_addon(globals())
