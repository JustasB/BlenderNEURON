try:
    import bpy
except:
    raise ImportError("`blenderneuron._blender` can only be imported inside Blender.")

def get_blender_version():
    try:
        return bpy.app.version_string.split(".")
    except:
        raise RuntimeError("Blender version could not be determined.")

def make_blender_addon(root_module):
    from . import patches, addon, controller

    version = get_blender_version()
    for name, patch in patches.__dict__.items():
        if name.startswith("patch_"):
            patch(version, addon, controller)

    # Reload the addon module to allow for all kinds of importloader shennanigans
    from . import addon

    # Inject the information that Blender requires to recognize the root_module as a
    # Blender addon, according to the magic __blender__ attr.
    for k, v in addon.__blender__.items():
        root_module[k] = v
