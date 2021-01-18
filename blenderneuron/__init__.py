try:
    import bpy
except:
    inside_blender = False
else:
    inside_blender = True

if inside_blender:
    # `bl_info` is read without evaluating the module. The BlenderNEURON installer will
    # replace the `blender` and `location` key with what is appropriate for the detected
    # Blender version so that our addon is compatible across Blender versions.
    bl_info = {
        "name": "BlenderNEURON",
        "description": "A Blender GUI for NEURON simulator",
        "author": "Justas Birgiolas",
        "version": (3, 0),
        "blender": (2, 91, 0),
        "location": "View3D > Properties > BlenderNEURON",
        "wiki_url": "BlenderNEURON.org",
        "tracker_url": "https://github.com/JustasB/BlenderNEURON/issues",
        "support": "COMMUNITY",
        "category": "Import-Export",
    }

    from ._blender import make_blender_addon

    addon = make_blender_addon()

    def register():
        addon.register()

    def unregister():
        addon.unregister()
