import bpy, random
from blenderneuron.blender.panels import AbstractBlenderNEURONPanel

from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       FloatProperty)

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)


class CellListWidget(AbstractBlenderNEURONPanel, UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "selected", text="")
        layout.label(item.name)

        value = self.filter_name

        if value == '':
            value = '*'
        else:
            value = '*'+value+'*'

        self.get_group(bpy.context).node_group.root_filter = value

    def invoke(self, context, event):
        pass


class CellGroupListWidget(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "selected", text="")
        layout.prop(item, "name_editable", text="", emboss=False)

    def invoke(self, context, event):
        pass


class CellGroupsPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_CellGroups'
    bl_label = "Cell Groups"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        """
        Checks if a connection to NEURON has been established
        """
        return hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None

    def draw(self, context):
        scene = context.scene

        row = self.layout.row()

        row.template_list("CellGroupListWidget", "",
                          scene.BlenderNEURON, "groups",
                          scene.BlenderNEURON, "groups_index",
                          rows=3)

        col = row.column(align=True)
        col.operator("blenderneuron.cell_group_add", icon='ZOOMIN', text="")
        col.operator("blenderneuron.cell_group_remove", icon='ZOOMOUT', text="")


class GroupCellsPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_GroupCells'
    bl_label = "Cells in Group"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return AbstractBlenderNEURONPanel.groups_exist(context)

    def draw(self, context):
        group = self.get_group(context)

        self.layout.operator("blenderneuron.get_cell_list_from_neuron", text="Refresh NEURON Cell List",
                             icon="FILE_REFRESH")

        self.layout.template_list("CellListWidget", "",
                                  group, "root_entries",
                                  group, "root_entries_index",
                                  rows=5)

        col = self.layout.split(0.33)
        col.operator("blenderneuron.select_all_cells")
        col.operator("blenderneuron.unselect_all_cells")
        col.operator("blenderneuron.invert_cell_selection")

        self.layout.operator("blenderneuron.save_active_group_to_file", text="Save Group Cells to File",
                             icon="FILESEL")


class ImportPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_Import'
    bl_label = "Import / Export"

    @classmethod
    def poll(cls, context):
        return AbstractBlenderNEURONPanel.groups_exist(context)

    def draw(self, context):
        scene = context.scene

        self.layout.operator("blenderneuron.import_groups", text="Import Cell Groups to Blender",
                             icon="FORWARD")

        self.layout.operator("blenderneuron.display_groups", text="Show Imported Groups",
                             icon="RESTRICT_VIEW_OFF")

        self.layout.operator("blenderneuron.update_groups_with_view_data", text="Update Groups with View Changes",
                             icon="FILE_REFRESH")

        self.layout.operator("blenderneuron.export_groups", text="Export Cell Groups to NEURON",
                             icon="BACK")


class GroupSettingsPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_GroupSettings'
    bl_label = "Cell Group Options"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return AbstractBlenderNEURONPanel.groups_exist(context)

    def draw(self, context):
        group = self.get_group(context)

        if AbstractBlenderNEURONPanel.group_count(context) > 1:
            col = self.layout
            col.label(text="Clone group settings from:")
            row = col.row()
            row.prop(group, "copy_from_group", text='')
            row.operator("blenderneuron.copy_from_group", text='Copy',icon='PASTEDOWN')

        col = self.layout
        col.label(text="Interaction Settings:")
        col = self.layout.box()
        col.label('Interact with Each:')
        col.row().prop(group, "interaction_granularity", text="Interact", expand=True)

        col = self.layout
        col.label(text="Section Display Settings:")
        box = col.box().column()
        row = box.split(percentage=0.5)
        row.label("Sections as Lines")
        row.prop(group, "as_lines", text='')

        if not group.as_lines:
            box = box.column()
            box.enabled = not group.as_lines
            col = box.split(percentage=0.5)
            col.label('Init. Color:')
            col.prop(group.node_group.color_ramp_material.diffuse_ramp.elements[0], "color", text='')

            col = box.split(percentage=0.5)
            col.label('Init. Brightness:')
            col.prop(group, "default_brightness", text='')

            col = box.split(percentage=0.5)
            col.label('Smooth Curves:')
            col.prop(group, "smooth_sections", text='')

            col = box.split(percentage=0.5)
            col.enabled = group.smooth_sections
            col.label('Subdivisions:')
            col.prop(group, "segment_subdivisions", text='')

            col = box.split(percentage=0.5)
            col.label('N-gon Sides:')
            col.prop(group, "circular_subdivisions", text='')

            # col = box.split(percentage=0.5)
            # col.label('Spherical Somas:')
            # col.prop(group, "spherize_soma_if_DeqL", text='')

        col = self.layout
        col.separator()
        col.label(text="Recording Settings:")
        col = self.layout.box().column()
        row = col.split(percentage=0.5)
        row.label("Record Activity")
        row.prop(group, "record_activity", text='')

        if group.record_activity:
            col = col.column()
            col.enabled = group.record_activity
            col.label('Record from Each:')
            col.row().prop(group, "recording_granularity", expand=True)
            col.separator()

            row = col.split(percentage=0.5)
            row.label('Start Recording:')
            row.prop(group, "recording_time_start", text="")

            row = col.split(percentage=0.5)
            row.label('Stop Recording:')
            row.prop(group, "recording_time_end", text="")

            row = col.split(percentage=0.5)
            row.label('Record:')
            row.prop(group, "record_variable", text="")

            row = col.split(percentage=0.5)
            row.label('Sampling Period:')
            row.prop(group, "recording_period", text="")

            row = col.split(percentage=0.5)
            row.label('Frames per Millisecond:')
            row.prop(group, "frames_per_ms", text="")

            row = col.split(percentage=0.5)
            row.label('Simplification Tolerance:')
            row.prop(group, "simplification_epsilon", text="")


            row = col.split(percentage=0.5)
            row.label('Animate Brightness:')
            row.prop(group, "animate_brightness", text="")

            row = col.split(percentage=0.5)
            row.label('Animate Color:')
            row.prop(group, "animate_color", text="")

            if group.animate_color:
                col.separator()
                col = col.column()
                col.template_color_ramp(group.node_group.color_ramp_material, "diffuse_ramp", expand=True)
                col.separator()

            col.separator()
            row = col.split(percentage=0.50)
            row.label('Variable Low:')
            row.label('High:')
            row = col.split(percentage=0.50)
            row.prop(group, "animation_range_low", text="")
            row.prop(group, "animation_range_high", text="")



        # col = self.layout
        # col.separator()
        # col.label(text="Connectivity Settings:")
        # col = self.layout.box()
        # row = col.split(percentage=0.5)
        # row.label("Import Synapses")
        # row.prop(group, "import_synapses", text='')


class ConfineBetweenLayersPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_ConfineBetweenLayers'
    bl_label = "Confine Between Layers"

    @classmethod
    def poll(cls, context):
        return AbstractBlenderNEURONPanel.imported_groups_exist(context)

    def draw(self, context):
        scene = context.scene

        settings = context.scene.BlenderNEURON.group.layer_confiner_settings

        split = self.layout.split(percentage=0.33)
        split.label(text="Start Layer:")
        split.prop(settings, "start_mesh", text="")

        if settings.start_mesh is not None and settings.start_mesh.type != 'MESH':
            self.layout.label("Start layer must be a 'MESH' object", icon='ERROR')

        split = self.layout.split(percentage=0.33)
        split.label(text="End Layer:")
        split.prop(settings, "end_mesh", text="")

        if settings.end_mesh is not None and settings.end_mesh.type != 'MESH':
            self.layout.label("End layer must be a 'MESH' object", icon='ERROR')

        split = self.layout.split(percentage=0.33)
        split.label(text="Name Contains:")

        row = split.row(align=True)
        row.prop(settings, "moveable_sections_pattern", text="")

        split = self.layout.split(percentage=0.33)
        split.label(text="Random Seed:")
        split.prop(settings, "seed", text="")

        split = self.layout.split(percentage=0.33)
        split.label(text="Min Height:")
        split.prop(settings, "height_min", text="", slider=True)

        split = self.layout.split(percentage=0.33)
        split.label(text="Max Height:")
        split.prop(settings, "height_max", text="", slider=True)

        self.layout.separator()

        split = self.layout.split(percentage=0.33)
        split.label(text="Max Angle:")
        split.prop(settings, "max_bend_angle", text="", slider=True)

        self.layout.separator()

        split = self.layout.split(percentage=0.33)
        split.label(text="Max Length:")
        split.prop(settings, "max_section_length", text="")

        self.layout.separator()

        # split = self.layout.split(percentage=0.33)
        # split.label(text="Sim Frames:")
        # split.prop(settings, "simulation_frames", text="")
        #
        # split = self.layout.split(percentage=0.33)
        # split.label(text="Steps/sec:")
        # split.prop(settings, "physics_steps_per_sec", text="")
        #
        # split = self.layout.split(percentage=0.33)
        # split.label(text="Iterations/step:")
        # split.prop(settings, "physics_solver_iterations_per_step", text="")
        #
        # self.layout.separator()
        #
        # col = self.layout.column()
        # col.operator("blenderneuron.setup_confiner", text="Setup Aligner", icon="CONSTRAINT")
        # col.operator("ptcache.bake_all", text="Align", icon="SURFACE_DATA").bake=False
        # col.operator("blenderneuron.update_groups_with_view_data", text="Save Alignment Results",
        #                      icon="FILE_REFRESH")

        col = self.layout.column()
        col.operator("blenderneuron.confine_between_layers", text="Confine", icon="SURFACE_DATA")
        col.operator("blenderneuron.update_groups_with_view_data", text="Update Groups with Confinement Results",
                     icon="FILE_REFRESH")


class SynapseSetListWidget(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name_editable", text="", emboss=False)

    def invoke(self, context, event):
        pass


class FormSynapsesPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_FormSynapses'
    bl_label = "Form Synapses"

    @classmethod
    def poll(cls, context):
        """
        Checks if a connection to NEURON has been established and there are 2+ imported groups
        """
        return hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None and \
               AbstractBlenderNEURONPanel.group_count(context) > 1

    def draw(self, context):
        scene = context.scene

        self.layout.label(text='Synapse Sets:')

        row = self.layout.row()

        row.template_list("SynapseSetListWidget", "",
                          context.scene.BlenderNEURON, "synapse_sets",
                          context.scene.BlenderNEURON, "synapse_sets_index",
                          rows=4)

        col = row.column(align=True)
        col.operator("blenderneuron.synapse_set_add", icon='ZOOMIN', text="")
        col.operator("blenderneuron.synapse_set_remove", icon='ZOOMOUT', text="")

        settings = self.get_synapse_set(context)

        if settings is None:
            return

        layout = self.layout
        layout.label(text='Source Cells:')

        layout = self.layout.box()

        layout.prop(settings, "group_source", text="Group")
        layout.prop(settings, "section_pattern_source", text="Sections")

        split = layout.split(percentage=0.33)
        split.label(text="Is Reciprocal:")
        split.prop(settings, "is_reciprocal", text="")

        if settings.is_reciprocal:
            layout.prop(settings, "synapse_name_source", text="Synapse")
            layout.prop(settings, "synapse_params_source")

        split = layout.split(percentage=0.33)
        split.label(text="Create Spines:")
        split.prop(settings, "create_spines", text="")

        if settings.create_spines:
            layout.prop(settings, "spine_neck_diameter")
            layout.prop(settings, "spine_head_diameter")
            layout.prop(settings, "spine_name_prefix")

        self.layout.label(text='Destination Cells:')

        layout = self.layout.box()
        layout.prop(settings, "group_dest", text="Group")
        layout.prop(settings, "section_pattern_dest", text="Sections")
        layout.prop(settings, "synapse_name_dest", text="Synapse")
        layout.prop(settings, "synapse_params_dest")

        layout = self.layout
        split = layout.split(percentage=0.33)
        split.label(text="Use Radii:")
        split.prop(settings, "use_radius", text="")

        layout.prop(settings, "max_distance")
        layout.prop(settings, "max_syns_per_pt")

        layout.separator()

        if not settings.create_spines:
            layout.prop(settings, "conduction_velocity")

        layout.prop(settings, "synaptic_delay")
        layout.prop(settings, "initial_weight")
        layout.prop(settings, "threshold")
        layout.separator()

        if settings.group_source == settings.group_dest:
            layout.label("Source and Destination groups must be different. ", icon='ERROR')
            layout.label("Use 'Cell Groups' section to create a new group.")

        layout.operator('blenderneuron.find_synapse_locations', text='Find Synapse Locations', icon='VIEWZOOM')
        layout.operator('blenderneuron.create_synapses', text='Create Synapses', icon='CONSTRAINT')
        layout.operator('blenderneuron.save_synapseset', text='Save Synapse Set to .py File', icon='FILESEL')



class SimulationSettingsPanel(AbstractBlenderNEURONPanel, Panel):
    bl_idname = 'CUSTOM_PT_NEURON_SimulationSettings'
    bl_label = "NEURON"

    @classmethod
    def poll(cls, context):
        """
        Checks if a connection to NEURON has been established
        """
        return hasattr(bpy.types.Object, "BlenderNEURON_node") and \
               bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None

    def draw(self, context):
        settings = self.get_sim_settings(context)

        col = self.layout
        row = col.row()
        row.enabled = False
        row.prop(settings, "neuron_t", text="Time (ms)")

        col.prop(settings, "neuron_tstop", text="Stop Time (ms)")
        col.prop(settings, "temperature", text=u"Temperature (°C)")
        col.separator()

        col.operator("blenderneuron.show_voltage_plot", text="Show Voltage Plot", icon="FCURVE")
        col.separator()

        col.operator("blenderneuron.show_shape_plot", text="Show Shape Plot", icon="RENDER_RESULT")
        col.separator()

        col.prop(settings, "integration_method")

        if settings.integration_method == '0':
            col.prop(settings, "time_step", "Time Step (ms)")

        if settings.integration_method == '1':
            col.prop(settings, "abs_tolerance", text="Absolute tolerance")

        col.separator()
        col.operator("blenderneuron.init_and_run_neuron", text="Init & Run", icon="POSE_DATA")
        col.separator()
        col.prop(context.scene.BlenderNEURON_properties, "neuron_last_command")
        col.separator()
        col.operator("blenderneuron.exec_neuron_command", text="Send Command to NEURON", icon="CONSOLE")

        col.operator("blenderneuron.sim_settings_from_neuron", text="Get Sim Params From NEURON", icon="FORWARD")
