import bpy, random
from blenderneuron.addon.panels import BlenderNEURONPanel

from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       FloatProperty)

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)


class CUSTOM_UL_CellListWidget(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "selected", text="")
        layout.label(item.name)

    def invoke(self, context, event):
        pass


class CUSTOM_UL_CellGroupListWidget(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "selected", text="")
        layout.prop(item, "name", text="", emboss=False)

    def invoke(self, context, event):
        pass


class CUSTOM_PT_NEURON_CellGroups(BlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_CellGroups'
    bl_label = "Cell Groups"

    def draw(self, context):
        scene = context.scene

        row = self.layout.row()

        row.template_list("CUSTOM_UL_CellGroupListWidget", "", \
                          scene, "BlenderNEURON_neuron_cellgroups", \
                          scene, "BlenderNEURON_neuron_cellgroups_index", \
                          rows=3)

        col = row.column(align=True)
        col.operator("custom.cell_group_add", icon='ZOOMIN', text="")
        col.operator("custom.cell_group_remove", icon='ZOOMOUT', text="")


class CUSTOM_PT_NEURON_GroupCells(BlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_GroupCells'
    bl_label = "Cells in Group"

    @classmethod
    def poll(cls, context):
        return BlenderNEURONPanel.groups_exist(context)

    def draw(self, context):
        scene = context.scene

        # Get the group for which the list of cells will be shown
        group_index = scene.BlenderNEURON_neuron_cellgroups_index
        group = scene.BlenderNEURON_neuron_cellgroups[group_index]

        self.layout.template_list("CUSTOM_UL_CellListWidget", "", \
                                  group, "group_cells", \
                                  group, "group_cells_index", \
                                  rows=5)

        col = self.layout.split(0.33)
        col.operator("custom.select_all_neuron_cells")
        col.operator("custom.select_none_neuron_cells")
        col.operator("custom.select_invert_neuron_cells")


class CUSTOM_PT_NEURON_GroupSettings(BlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_GroupSettings'
    bl_label = "Cell Group Options"

    @classmethod
    def poll(cls, context):
        return BlenderNEURONPanel.groups_exist(context)

    def draw(self, context):
        scene = context.scene

        col = self.layout
        col.prop(scene, "BlenderNEURON_import_recording_granularity", text="Record")
        col.prop(scene, "BlenderNEURON_record_variable", text="Variable")
        col.prop(scene, "BlenderNEURON_import_interaction_granularity", text="Interact")
        col.separator()

        row = col.split(0.5)
        row.prop(scene, "BlenderNEURON_import_activity", text="Import Activity")
        row.prop(scene, "BlenderNEURON_import_synapses", text="Import Synapses")


class CUSTOM_PT_NEURON_SimulationSettings(BlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_SimulationSettings'
    bl_label = "Import"

    def draw(self, context):
        scene = context.scene

        self.layout.operator("custom.import_selected_neuron_cells", text="Display Selected Cells in Blender",
                             icon="PLAY")


class CUSTOM_PT_NEURON_SimulationSettings(BlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_SimulationSettings'
    bl_label = "Simulation"

    def draw(self, context):
        scene = context.scene

        col = self.layout
        col.prop(scene, "BlenderNEURON_neuron_tstop", text="Stop Time")
        col.prop(scene, "BlenderNEURON_temperature", text="Temperature")

        col.operator("custom.import_selected_neuron_cells", text="Open Voltage Plot", icon="FCURVE")
        col.prop(scene, "BlenderNEURON_integration_method")
        col.operator("custom.import_selected_neuron_cells", text="Init & Run", icon="POSE_DATA")

