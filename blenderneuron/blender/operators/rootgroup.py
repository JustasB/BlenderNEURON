import bpy
from bpy.types import (Operator)
from bpy_extras.io_utils import ExportHelper
import numpy as np

from blenderneuron.blender import BlenderNodeClass
from blenderneuron.blender.views.cellobjectview import CellObjectView
from blenderneuron.blender.views.sectionobjectview import SectionObjectView
from blenderneuron.blender.views.synapseformerview import SynapseFormerView
from blenderneuron.blender.views.vectorconfinerview import VectorConfinerView

from blenderneuron.blender.utils import get_operator_context_override

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


class CellGroupAddOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.cell_group_add"
    bl_label = "Add new cell display group"
    bl_description = "Add new cell display group. Each group allows cells within it to have their own granularity " \
                     "and variable recording settings. E.g. to allow customization of cell display detail"


    def execute(self, context):

        self.node.add_group()

        return{'FINISHED'}


class CellGroupRemoveOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.cell_group_remove"
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

class GetCellListFromNeuronOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.get_cell_list_from_neuron"
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


class SelectAllCellsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.select_all_cells"
    bl_label = "Select All"
    bl_description = "Select all cells to be shown in Blender"

    def execute(self, context):
        node_group = self.node.ui_properties.group.node_group
        node_group.select_roots('All', node_group.root_filter)

        return{'FINISHED'}


class UnselectAllCellsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.unselect_all_cells"
    bl_label = "None"
    bl_description = "Unselect all cells for showing in Blender"

    def execute(self, context):
        node_group = self.node.ui_properties.group.node_group
        node_group.select_roots('None', node_group.root_filter)

        return{'FINISHED'}


class InvertCellSelectionOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.invert_cell_selection"
    bl_label = "Invert"
    bl_description = "Invert the selection of cells for showing in Blender"

    def execute(self, context):
        node_group = self.node.ui_properties.group.node_group
        node_group.select_roots('Invert', node_group.root_filter)

        return{'FINISHED'}


class CopyFromGroupOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.copy_from_group"
    bl_label = "Copy Group"
    bl_description = "Copies cell group settings from the selected group into the active group"

    def execute(self, context):
        target_group = self.node.ui_properties.group
        source_group = self.node.ui_properties.groups[target_group.copy_from_group]

        target_group.copy_from(source_group)

        return{'FINISHED'}


class SimulationSettingsToNeuronOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.sim_settings_to_neuron"
    bl_label = "Send simulation parameters to NEURON"
    bl_description = "Sends simulation parameters set in Blender to NEURON"

    def execute(self, context):
        self.node.ui_properties.simulator_settings.to_neuron()
        return{'FINISHED'}


class SimulationSettingsFromNeuronOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.sim_settings_from_neuron"
    bl_label = "Get simulation parameters from NEURON"
    bl_description = "Reads simulation parameters set in NEURON into Blender. Use this when one of the above " \
                     "parameters (e.g. h.tstop) is changed outside of Blender (e.g. via a script or NEURON GUI)."

    def execute(self, context):
        self.node.ui_properties.simulator_settings.from_neuron()

        return{'FINISHED'}


class ShowVoltagePlotOpearator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.show_voltage_plot"
    bl_label = "Show Voltage Plot"
    bl_description = "Show the NEURON > Graph > Voltage Axis plot (v of the active section vs time)"

    def execute(self, context):
        self.client.run_command("from neuron import gui; h.newPlotV();")

        return{'FINISHED'}


class ShowShapePlotOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.show_shape_plot"
    bl_label = "Show Shape Plot"
    bl_description = "Show the NEURON > Graph > Shape plot (a rough rendering of NEURON sections)"

    def execute(self, context):
        self.client.run_command("from neuron import gui; h.newshapeplot()")

        return{'FINISHED'}


class InitAndRunNeuronOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.init_and_run_neuron"
    bl_label = "Init & Run NEURON"
    bl_description = "Initializes and runs the NEURON simulation (i.e. `h.run()`)"

    def execute(self, context):
        self.client.run_command("h.run()")

        # Update the current time
        bpy.ops.blenderneuron.sim_settings_from_neuron()

        return{'FINISHED'}


class RemoveAllGroupsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.remove_all_groups"
    bl_label = "Reset Cell Groups"
    bl_description = "Removes all groups and clears the NEURON cell index"

    def execute(self, context):
        groups = list(self.node.groups.values())

        for group in groups:
            group.remove()

        return{'FINISHED'}


class ImportGroupsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.import_groups"
    bl_label = "Import Group Data"
    bl_description = "Imports cell group data (e.g. morphology and activity) from NEURON into Blender"

    def execute(self, context):

        selected_groups = self.node.get_selected_groups()

        self.node.import_groups_from_neuron(selected_groups)

        bpy.ops.blenderneuron.display_groups()

        return{'FINISHED'}


class DisplayGroupsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.display_groups"
    bl_label = "(Re)Display Imported Groups"
    bl_description = "Displays imported groups based on their interaction level"

    @classmethod
    def poll(cls, context):
        return BlenderNodeClass.imported_groups_exist(context)

    def execute(self, context):
        self.node.display_groups()

        return {'FINISHED'}


class UpdateGroupsWithViewDataOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.update_groups_with_view_data"
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


class ExportGroupsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.export_groups"
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



class SaveActiveGroupToFileOperator(Operator, ExportHelper, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.save_active_group_to_file"
    bl_label = "Save Active Group"
    bl_description = "Save Active Group to JSON file"

    @classmethod
    def poll(cls, context):
        groups = bpy.types.Object.BlenderNEURON_node.ui_properties.groups

        return len(groups) > 0 and \
               bpy.types.Object.BlenderNEURON_node.ui_properties.group.node_group.state == 'imported'

    # ExportHelper mixin class uses this
    filename_ext = ".json"

    def execute(self, context):
        self.node.ui_properties.group.node_group.to_file(self.filepath)

        self.report({'INFO'}, 'File saved: ' + self.filepath)

        return {'FINISHED'}


class SetupConfiner(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.setup_confiner"
    bl_label = "Setup Confiner"
    bl_description = "Prepares cell sections for confinement between selected layers"

    @classmethod
    def poll(cls, context):

        settings = context.scene.BlenderNEURON.group.layer_confiner_settings

        # Enable button only when a mesh is selected for layer
        return settings.start_mesh is not None and settings.start_mesh.type == 'MESH' and \
               settings.end_mesh is not None and settings.end_mesh.type == 'MESH'

    def execute(self, context):

        group = self.node.ui_properties.group.node_group

        group.setup_confiner()

        return{'FINISHED'}

class ConfineBetweenLayers(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.confine_between_layers"
    bl_label = "Confine Between Layers"
    bl_description = "Confines sections that match the name pattern between the " \
                     "selected layers"

    @classmethod
    def poll(cls, context):

        settings = context.scene.BlenderNEURON.group.layer_confiner_settings

        # Enable button only when a mesh is selected for layer
        return settings.start_mesh is not None and settings.start_mesh.type == 'MESH' and \
               settings.end_mesh is not None and settings.end_mesh.type == 'MESH'

    def execute(self, context):

        group = self.node.ui_properties.group.node_group

        group.setup_confiner()

        group.confine_between_layers()

        return{'FINISHED'}


class FindSynapseLocationsOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.find_synapse_locations"
    bl_label = "Find Synapse Locations"
    bl_description = "Finds the locations where synapses will be formed"

    @classmethod
    def poll(cls, context):

        settings = context.scene.BlenderNEURON.synapse_set

        # Enable only when two different groups are selected
        return settings.group_source is not None and \
               settings.group_dest is not None and \
               settings.group_source != settings.group_dest

    def execute(self, context):

        synapse_set = context.scene.BlenderNEURON.synapse_set

        pairs = synapse_set.get_synapse_locations()

        self.report({'INFO'}, 'Found ' + str(len(pairs)) + ' synapse locations')

        return {'FINISHED'}


class CreateSynapsesOperator(Operator, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.create_synapses"
    bl_label = "Create Synapses"
    bl_description = "Creates synapses in NEURON between cells in two BlenderNEURON groups"

    @classmethod
    def poll(cls, context):

        settings = context.scene.BlenderNEURON.synapse_set

        # Enable only when two different groups are selected
        return type(bpy.types.Object.BlenderNEURON_node.groups[settings.group_source].view) is SynapseFormerView


    def execute(self, context):

        synapse_set = context.scene.BlenderNEURON.synapse_set
        synapse_set.create_synapses()

        self.report({'INFO'}, 'Synapses created in NEURON')

        return{'FINISHED'}


class SaveSynapseSetOperator(Operator, ExportHelper, CellGroupOperatorAbstract):
    bl_idname = "blenderneuron.save_synapseset"
    bl_label = "Save Synapse Set"
    bl_description = "Saves the synapses in the synapse set to a JSON file"

    # ExportHelper mixin class uses this
    filename_ext = ".json"

    @classmethod
    def poll(cls, context):

        settings = context.scene.BlenderNEURON.synapse_set

        # Enable only when two different groups are selected
        return type(bpy.types.Object.BlenderNEURON_node.groups[settings.group_source].view) is SynapseFormerView

    def execute(self, context):

        synapse_set = context.scene.BlenderNEURON.synapse_set
        synapse_set.save_synapses(self.filepath)

        self.report({'INFO'}, 'File saved: ' + self.filepath)

        return{'FINISHED'}

class SynapseSetAddOperator(Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.synapse_set_add"
    bl_label = "Create a new synapse set"
    bl_description = "Create a new synapse set"

    @classmethod
    def poll(cls, context):
        """
        Checks if there are 2+ groups
        """
        return BlenderNodeClass.group_count(context) > 1

    def execute(self, context):
        self.node.add_synapse_set()

        return {'FINISHED'}


class SynapseSetRemoveOperator(Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.synapse_set_remove"
    bl_label = "Remove highlighted synapse set"
    bl_description = "Remove highlighted synapse set"

    @classmethod
    def poll(cls, context):
        return len(context.scene.BlenderNEURON.synapse_sets) > 1

    def execute(self, context):
        UI_properties = context.scene.BlenderNEURON
        UI_properties.synapse_sets.remove(UI_properties.synapse_sets_index)
        UI_properties.synapse_sets_index = max(0, UI_properties.synapse_sets_index - 1)

        return {'FINISHED'}







class AddNeonEffectOperator(Operator, BlenderNodeClass):
    bl_idname = "blenderneuron.add_neon_effect"
    bl_label = "Add neon effect to rendered images"
    bl_description = "Adds a glare filter to rendered images. Can be customized in Node Editor > " \
                     "Compositing > Glare"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        self.node.add_neon_effect()

        return {'FINISHED'}





