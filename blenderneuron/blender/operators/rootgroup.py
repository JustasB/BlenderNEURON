import bpy
from bpy.types import (Operator)
from bpy_extras.io_utils import ExportHelper

from blenderneuron.blender import BlenderNodeClass
from blenderneuron.blender.views.cellobjectview import CellObjectView
from blenderneuron.blender.views.sectionobjectview import SectionObjectView
from blenderneuron.blender.views.commandview import CommandView
from blenderneuron.blender.views.physicsmeshsectionobjectview import PhysicsMeshSectionObjectView

class CellGroupOperatorAbstract(BlenderNodeClass):
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        """
        Checks if a connection to NEURON has been established
        """
        return hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None


class CUSTOM_OT_cell_group_add(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.cell_group_add"
    bl_label = "Add new cell display group"
    bl_description = "Add new cell display group. Each group allows cells within it to have their own granularity " \
                     "and variable recording settings. E.g. to allow customization of cell display detail"


    def execute(self, context):

        self.node.add_group()

        return{'FINISHED'}


class CUSTOM_OT_cell_group_remove(Operator, CellGroupOperatorAbstract):
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

class CUSTOM_OT_get_cell_list_from_neuron(Operator, CellGroupOperatorAbstract):
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


class CUSTOM_OT_select_all_neuron_cells(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.select_all_neuron_cells"
    bl_label = "Select All"
    bl_description = "Select all cells to be shown in Blender"

    def execute(self, context):
        roots = self.node.ui_properties.group.root_entries

        for item in roots:
            item.selected = True

        return{'FINISHED'}


class CUSTOM_OT_select_none_neuron_cells(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.select_none_neuron_cells"
    bl_label = "None"
    bl_description = "Unselect all cells for showing in Blender"

    def execute(self, context):
        roots = self.node.ui_properties.group.root_entries

        for item in roots:
            item.selected = False

        return{'FINISHED'}


class CUSTOM_OT_select_invert_neuron_cells(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.select_invert_neuron_cells"
    bl_label = "Invert"
    bl_description = "Invert the selection of cells for showing in Blender"

    def execute(self, context):
        roots = self.node.ui_properties.group.root_entries

        for item in roots:
            item.selected = not item.selected

        return{'FINISHED'}


class CUSTOM_OT_sim_settings_to_neuron(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.sim_settings_to_neuron"
    bl_label = "Send simulation parameters to NEURON"
    bl_description = "Sends simulation parameters set in Blender to NEURON"

    def execute(self, context):
        self.node.ui_properties.simulator_settings.to_neuron()
        return{'FINISHED'}


class CUSTOM_OT_sim_settings_from_neuron(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.sim_settings_from_neuron"
    bl_label = "Get simulation parameters from NEURON"
    bl_description = "Reads simulation parameters set in NEURON into Blender. Use this when one of the above " \
                     "parameters (e.g. h.tstop) is changed outside of Blender (e.g. via a script or NEURON GUI)."

    def execute(self, context):
        self.node.ui_properties.simulator_settings.from_neuron()

        return{'FINISHED'}


class CUSTOM_OT_show_voltage_plot(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.show_voltage_plot"
    bl_label = "Show Voltage Plot"
    bl_description = "Show the NEURON > Graph > Voltage Axis plot (v of the active section vs time)"

    def execute(self, context):
        self.client.run_command("h.newPlotV()")

        return{'FINISHED'}


class CUSTOM_OT_show_shape_plot(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.show_shape_plot"
    bl_label = "Show Shape Plot"
    bl_description = "Show the NEURON > Graph > Shape plot (a rough rendering of NEURON sections)"

    def execute(self, context):
        self.client.run_command("h.newshapeplot()")

        return{'FINISHED'}


class CUSTOM_OT_init_and_run(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.init_and_run"
    bl_label = "Init & Run NEURON"
    bl_description = "Initializes and runs the NEURON simulation (i.e. `h.run()`)"

    def execute(self, context):
        self.client.run_command("h.run()")

        # Update the current time
        bpy.ops.custom.sim_settings_from_neuron()

        return{'FINISHED'}


class CUSTOM_OT_reset_groups(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.reset_groups"
    bl_label = "Reset Cell Groups"
    bl_description = "Removes all groups and clears the NEURON cell index"

    def execute(self, context):
        groups = list(self.node.groups.values())

        for group in groups:
            group.remove()

        return{'FINISHED'}


class CUSTOM_OT_import_selected_groups(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.import_selected_groups"
    bl_label = "Import Group Data"
    bl_description = "Imports cell group data (morhology and activity) from NEURON into Blender"

    def execute(self, context):

        blender_groups = [group.to_dict() for group in self.node.groups.values() if group.selected]

        compressed = self.client.initialize_groups(blender_groups)
        nrn_groups = self.node.decompress(compressed)
        del compressed

        for nrn_group in nrn_groups:
            node_group = self.node.groups[nrn_group["name"]]

            if node_group.view is not None:
                node_group.view.remove()
                node_group.view = None

            node_group.from_full_NEURON_group(nrn_group)

        bpy.ops.custom.display_selected_groups()

        return{'FINISHED'}


class CUSTOM_OT_display_selected_groups(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.display_selected_groups"
    bl_label = "Show Imported Groups"
    bl_description = "Displays imported groups based on their interaction level"

    @classmethod
    def poll(cls, context):
        return BlenderNodeClass.imported_groups_exist(context)

    def execute(self, context):

        for group in self.node.groups.values():
            if group.selected:
                if group.interaction_granularity == 'Cell':
                    group.show(CellObjectView)

                if group.interaction_granularity == 'Section':
                    group.show(SectionObjectView)

        return{'FINISHED'}


class CUSTOM_OT_update_groups_from_view(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.update_groups_from_view"
    bl_label = "Update Groups with View Changes"
    bl_description = "Updates group data with the changes visible in the 3D View"

    @classmethod
    def poll(cls, context):
        return BlenderNodeClass.visible_groups_exist(context)

    def execute(self, context):

        for group in self.node.groups.values():
            if group.selected:
                group.from_view()

        return{'FINISHED'}


class CUSTOM_OT_export_selected_groups(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.export_selected_groups"
    bl_label = "Export Group Data"
    bl_description = "Exports cell group data (morhology) to NEURON"

    @classmethod
    def poll(cls, context):
        return BlenderNodeClass.imported_groups_exist(context)

    def execute(self, context):

        blender_groups = [group.to_dict(
                              include_root_children=True,
                              include_coords_and_radii=True)
                          for group in self.node.groups.values()
                          if group.selected]

        self.client.update_groups(blender_groups)

        return{'FINISHED'}



class SaveModelCoords(Operator, ExportHelper, CellGroupOperatorAbstract):
    bl_idname = "custom.save_selected_groups"
    bl_label = "Save Group Data"
    bl_description = "Save Changes to NEURON .py file"

    @classmethod
    def poll(cls, context):
        return BlenderNodeClass.imported_groups_exist(context)

    # ExportHelper mixin class uses this
    filename_ext = ".py"

    def execute(self, context):
        group = self.node.ui_properties.group.node_group

        group.from_view()

        content = CommandView(group).show()

        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        self.report({'INFO'}, 'File saved')

        return {'FINISHED'}


class CUSTOM_OT_select_aligner_moveable_sections(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.select_aligner_moveable_sections"
    bl_label = "Select Fixed Sections"
    bl_description = "Selects/Highlights the sections that will be aligned with the selected layer"

    def execute(self, context):

        ui_group = self.node.ui_properties.group
        group = ui_group.node_group

        group.show(SectionObjectView)
        group.view.select_containers(pattern=ui_group.layer_aligner_settings.moveable_sections_pattern)

        return{'FINISHED'}

class CUSTOM_OT_setup_aligner(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.setup_aligner"
    bl_label = "Setup Aligner"
    bl_description = "Sets up joints (at branchpoints), rigid body constraints, and layer force field" \
                     " to align the pattern matching sections with the layer"

    @classmethod
    def poll(cls, context):

        group_aligner = context.scene.BlenderNEURON.group.layer_aligner_settings

        # Enable button only when a mesh is selected for layer
        return group_aligner.layer_mesh is not None and group_aligner.layer_mesh.type == 'MESH'

    def execute(self, context):

        group = self.node.ui_properties.group.node_group

        group.setup_aligner()

        return{'FINISHED'}

class CUSTOM_OT_align_to_layer(Operator, CellGroupOperatorAbstract):
    bl_idname = "custom.align_to_layer"
    bl_label = "Align to Layer"
    bl_description = "Aligns sections that match the align pattern to the " \
                     "selected layer using a force-based physics simulation"

    @classmethod
    def poll(cls, context):

        group = context.scene.BlenderNEURON.group.node_group

        return type(group.view) is PhysicsMeshSectionObjectView

    def execute(self, context):

        group = self.node.ui_properties.group.node_group

        group.align_to_layer()

        return{'FINISHED'}



