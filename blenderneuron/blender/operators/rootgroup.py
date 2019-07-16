import bpy, random, zlib
from blenderneuron.blender.group2cells import CellObjectView

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)

from blenderneuron.blender import BlenderNodeClass

class AbstractCUSTOM_OT_cellgroup_operator(BlenderNodeClass):
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """
        Checks if a connection to NEURON has been established
        """
        return hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None


class CUSTOM_OT_cell_group_add(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.cell_group_add"
    bl_label = "Add new cell display group"
    bl_description = "Add new cell display group. Each group allows cells within it to have their own granularity " \
                     "and variable recording settings. E.g. to allow customization of cell display detail"


    def execute(self, context):

        self.node.add_group()

        return{'FINISHED'}


class CUSTOM_OT_cell_group_remove(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.cell_group_remove"
    bl_label = "Remove a cell display group"
    bl_description = "Remove a cell display group"

    @classmethod
    def poll(cls, context):
        """
        Checks if there are any cell groups
        """
        return len(bpy.types.Object.BlenderNEURON_node.groups) > 0

    def execute(self, context):
        self.node.ui_properties.group.node_group.remove()

        return{'FINISHED'}

class CUSTOM_OT_get_cell_list_from_neuron(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.get_cell_list_from_neuron"
    bl_label = "List NEURON Cells"
    bl_description = "Get all cells (root sections) currently instantiated in NEURON. Automatically " \
                     "selects roots that are not included in any other groups."

    @classmethod
    def poll(cls, context):
        """
        Checks if there are any cell groups
        """
        return len(bpy.types.Object.BlenderNEURON_node.groups) > 0

    def execute(self, context):

        self.node.update_root_index()
        self.node.ui_properties.group.node_group.add_groupless_roots()

        return{'FINISHED'}


class CUSTOM_OT_select_all_neuron_cells(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.select_all_neuron_cells"
    bl_label = "Select All"
    bl_description = "Select all cells to be shown in Blender"

    def execute(self, context):
        roots = self.node.ui_properties.group.root_entries

        for item in roots:
            item.selected = True

        return{'FINISHED'}


class CUSTOM_OT_select_none_neuron_cells(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.select_none_neuron_cells"
    bl_label = "None"
    bl_description = "Unselect all cells for showing in Blender"

    def execute(self, context):
        roots = self.node.ui_properties.group.root_entries

        for item in roots:
            item.selected = False

        return{'FINISHED'}


class CUSTOM_OT_select_invert_neuron_cells(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.select_invert_neuron_cells"
    bl_label = "Invert"
    bl_description = "Invert the selection of cells for showing in Blender"

    def execute(self, context):
        roots = self.node.ui_properties.group.root_entries

        for item in roots:
            item.selected = not item.selected

        return{'FINISHED'}


class CUSTOM_OT_sim_settings_to_neuron(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.sim_settings_to_neuron"
    bl_label = "Send simulation parameters to NEURON"
    bl_description = "Sends simulation parameters set in Blender to NEURON"

    def execute(self, context):
        self.node.ui_properties.simulator_settings.to_neuron()
        return{'FINISHED'}


class CUSTOM_OT_sim_settings_from_neuron(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.sim_settings_from_neuron"
    bl_label = "Get simulation parameters from NEURON"
    bl_description = "Reads simulation parameters set in NEURON into Blender. Use this when one of the above " \
                     "parameters (e.g. h.tstop) is changed outside of Blender (e.g. via a script or NEURON GUI)."

    def execute(self, context):
        self.node.ui_properties.simulator_settings.from_neuron()

        return{'FINISHED'}


class CUSTOM_OT_show_voltage_plot(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.show_voltage_plot"
    bl_label = "Show Voltage Plot"
    bl_description = "Show the NEURON > Graph > Voltage Axis plot (v of the active section vs time)"

    def execute(self, context):
        self.client.run_command("h.newPlotV()")

        return{'FINISHED'}


class CUSTOM_OT_init_and_run(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.init_and_run"
    bl_label = "Init & Run NEURON"
    bl_description = "Initializes and runs the NEURON simulation (i.e. `h.run()`)"

    def execute(self, context):
        self.client.run_command("h.run()")

        return{'FINISHED'}


class CUSTOM_OT_reset_groups(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.reset_groups"
    bl_label = "Reset Cell Groups"
    bl_description = "Removes all groups and clears the NEURON cell index"

    def execute(self, context):
        groups = list(self.node.groups.values())

        for group in groups:
            group.remove()

        return{'FINISHED'}


class CUSTOM_OT_import_selected_groups(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.import_selected_groups"
    bl_label = "Import Group Data"
    bl_description = "Imports cell group data (morhology and activity) into Blender"

    def execute(self, context):
        blender_groups = [group.to_dict() for group in self.node.groups.values() if group.selected]

        compressed = self.client.initialize_groups(blender_groups)
        nrn_groups = self.node.decompress(compressed)
        del compressed

        for nrn_group in nrn_groups:
            self.node.groups[nrn_group["name"]].from_full_NEURON_group(nrn_group)

        for group in self.node.groups.values():
            if group.selected:
                group.show(CellObjectView)

        return{'FINISHED'}


class CUSTOM_OT_export_selected_groups(Operator, AbstractCUSTOM_OT_cellgroup_operator):
    bl_idname = "custom.export_selected_groups"
    bl_label = "Export Group Data"
    bl_description = "Exports cell group data (morhology) to NEURON"

    def execute(self, context):

        for group in self.node.groups.values():
            if group.selected:
                group.from_view()

        blender_groups = [group.to_dict(
                              include_root_children=True,
                              include_coords_and_radii=True)
                          for group in self.node.groups.values()
                          if group.selected]

        self.client.update_groups(blender_groups)

        return{'FINISHED'}


