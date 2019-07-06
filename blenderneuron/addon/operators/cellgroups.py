import bpy, random

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)

class CUSTOM_OT_cellgroup_operator(object):
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """
        Checks if a connection to NEURON has been established
        """
        return hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None

    def get_group(self, context):
        groups = context.scene.BlenderNEURON_neuron_cellgroups
        group_i = context.scene.BlenderNEURON_neuron_cellgroups_index
        group = groups[group_i]
        return group


class CUSTOM_OT_cell_group_add(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.cell_group_add"
    bl_label = "Add new cell display group"
    bl_description = "Add new cell display group. Each group allows cells within it to have their own granularity " \
                     "and variable recording settings. E.g. to allow customization of cell display detail"


    def execute(self, context):
        scene = context.scene
        i = len(context.scene.BlenderNEURON_neuron_cellgroups)

        # Find a unique name for the new group
        i_name = i
        existing_groups = scene.BlenderNEURON_neuron_cellgroups.keys()

        while True:
            name = "CellGroup." + str(i_name).zfill(3)

            if name in existing_groups:
                i_name += 1
            else:
                break

        group = scene.BlenderNEURON_neuron_cellgroups.add()
        group.name = name
        group.index = i
        group.selected = True

        scene.BlenderNEURON_neuron_cellgroups_index = i

        bpy.ops.custom.get_cell_list_from_neuron()

        return{'FINISHED'}


class CUSTOM_OT_cell_group_remove(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.cell_group_remove"
    bl_label = "Remove a cell display group"
    bl_description = "Remove a cell display group"

    def execute(self, context):

        remove_i = context.scene.BlenderNEURON_neuron_cellgroups_index
        group = self.get_group(context)

        # when deleting group, reset the selected cell's group in the root index
        for cell in group.cells:
            if cell.selected:
                cell.selected = False

        del group

        context.scene.BlenderNEURON_neuron_cellgroups.remove(remove_i)

        return{'FINISHED'}

class CUSTOM_OT_get_cell_list_from_neuron(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.get_cell_list_from_neuron"
    bl_label = "List NEURON Cells"
    bl_description = "Get all cells (root sections) currently instantiated in NEURON"

    @classmethod
    def poll(cls, context):
        """
        Checks if there are any cell groups
        """
        return len(context.scene.BlenderNEURON_neuron_cellgroups) > 0

    def execute(self, context):
        self.update_roots(context)
        self.update_group_cell_list(context, self.get_group(context))

        return{'FINISHED'}

    def update_roots(self, context):

        roots = context.scene.BlenderNEURON_neuron_roots

        old_groups = dict(zip(
            [root.name for root in roots],
            [root.group_index for root in roots]
        ))

        roots.clear()

        client = bpy.types.Object.BlenderNEURON_node.client
        root_data = client.get_root_section_names()

        for i, root_info in enumerate(root_data):
            root = roots.add()
            root.index = root_info[0]
            root.name = root_info[1]

            if root.name in old_groups:
                root.group_index = old_groups[root.name]


    def update_group_cell_list(self, context, group):

        roots = context.scene.BlenderNEURON_neuron_roots

        group.cells.clear()

        for i, root in enumerate(roots):
            group_root = group.cells.add()
            group_root.index = root.index
            group_root.name = root.name

            # When creating new group, include cells that have not been included in other groups
            if root.group_index == -1 or root.group_index == group.index:
                group_root.selected = True


class CUSTOM_OT_select_all_neuron_cells(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.select_all_neuron_cells"
    bl_label = "Select All"
    bl_description = "Select all cells to be shown in Blender"

    def execute(self, context):
        cells = self.get_group(context).cells

        for item in cells:
            item.selected = True

        return{'FINISHED'}


class CUSTOM_OT_select_none_neuron_cells(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.select_none_neuron_cells"
    bl_label = "None"
    bl_description = "Unselect all cells for showing in Blender"

    def execute(self, context):
        cells = self.get_group(context).cells

        for item in cells:
            item.selected = False

        return{'FINISHED'}


class CUSTOM_OT_select_invert_neuron_cells(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.select_invert_neuron_cells"
    bl_label = "Invert"
    bl_description = "Invert the selection of cells for showing in Blender"

    def execute(self, context):
        cells = self.get_group(context).cells

        for item in cells:
            item.selected = not item.selected

        return{'FINISHED'}


class CUSTOM_OT_import_selected_groups(Operator, CUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.import_selected_groups"
    bl_label = "Import Selected Cells"
    bl_description = "Show the selected NEURON cells in Blender 3D View"

    def execute(self, context):
        cells = self.get_group(context).cells

        pass

        return{'FINISHED'}


