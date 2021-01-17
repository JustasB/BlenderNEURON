import sys

def patch_original(version, addon, controller):
    if version[0] == 2 and version[1] == 79:
        from . import addon27

        # Replace the addon module with the old Blender 2.7 module
        sys.module[addon.__name__] = addon27
