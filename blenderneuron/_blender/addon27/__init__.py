from bpy.app.handlers import persistent

from ...commnode import CommNode

from blenderneuron.blender.operators.connection import *
from blenderneuron.blender.panels.connection import *
from blenderneuron.blender.properties.connection import *

from blenderneuron.blender.operators.rootgroup import *
from blenderneuron.blender.panels.rootgroup import *
from blenderneuron.blender.properties.rootgroup import *

from blenderneuron.blender.utils import register_module_classes

import sys

@persistent
def auto_start(scene):
    # Remove auto-execute command after starting
    bpy.app.handlers.scene_update_post.remove(auto_start)

    bpy.ops.blenderneuron.node_start()

@persistent
def on_blend_load(scene):
    bpy.ops.blenderneuron.node_start()

def register():
    try:
        bpy.utils.register_module(__name__)
    except:
        pass

    sys.setrecursionlimit(1500)

    register_module_classes(blenderneuron.blender.operators.rootgroup)
    register_module_classes(blenderneuron.blender.panels.rootgroup)
    register_module_classes(blenderneuron.blender.properties.rootgroup)

    blenderneuron.blender.properties.rootgroup.register()

    register_module_classes(blenderneuron.blender.operators.connection)
    register_module_classes(blenderneuron.blender.panels.connection)
    register_module_classes(blenderneuron.blender.properties.connection)

    blenderneuron.blender.properties.connection.register()

    # This ensures the server starts on Blender load (self-removing)
    bpy.app.handlers.scene_update_post.append(auto_start)

    # Reload the addon on file open
    bpy.app.handlers.load_post.append(on_blend_load)

def unregister():
    bpy.ops.blenderneuron.node_stop()

    try:
        bpy.utils.unregister_module(__name__)
    except:
        pass

    register_module_classes(blenderneuron.blender.operators.connection, unreg=True)
    register_module_classes(blenderneuron.blender.panels.connection, unreg=True)
    register_module_classes(blenderneuron.blender.properties.connection, unreg=True)

    register_module_classes(blenderneuron.blender.operators.rootgroup, unreg=True)
    register_module_classes(blenderneuron.blender.panels.rootgroup, unreg=True)
    register_module_classes(blenderneuron.blender.properties.rootgroup, unreg=True)

    blenderneuron.blender.properties.rootgroup.unregister()

import bpy
from abc import ABCMeta

class BlenderNodeClass:
    __metaclass__ = ABCMeta

    @property
    def node(self):
        if hasattr(bpy.types.Object, "BlenderNEURON_node"):
            return bpy.types.Object.BlenderNEURON_node
        else:
            return None

    @node.setter
    def node(self, value):
        bpy.types.Object.BlenderNEURON_node = value

    @property
    def client(self):
        try:
            return self.node.client
        except:
            return None

    @staticmethod
    def groups_exist(context):
        """
        Checks if there are any cell groups
        """
        return any(context.scene.BlenderNEURON.groups)

    @staticmethod
    def group_count(context):
        """
        Checks if there are any cell groups
        """
        return len(context.scene.BlenderNEURON.groups.keys())

    @staticmethod
    def imported_groups_exist(context):
        """
        Checks if there are any imported cell groups
        """
        return any([g for g in context.scene.BlenderNEURON.groups if g.node_group.state == 'imported'])

    @staticmethod
    def visible_groups_exist(context):
        """
        Checks if there are any cell groups whose view is visible
        """
        return any([g for g in context.scene.BlenderNEURON.groups if g.node_group.view is not None])

    def get_group_list(self, context):
        return [(g.name, g.name, g.name) for g in context.scene.BlenderNEURON.groups.values()]


__blender__ = dict(bl_info=bl_info, register=register, unregister=unregister)
