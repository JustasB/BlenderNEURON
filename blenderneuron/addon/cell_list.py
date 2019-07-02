import bpy, random

from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       FloatProperty)

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)

class CUSTOM_OT_NEURON_operator(object):
    @classmethod
    def poll(cls, context):
        return bpy.types.Object.BlenderNEURON_node is not None and \
               bpy.types.Object.BlenderNEURON_node.client is not None

class CUSTOM_OT_get_cell_list_from_neuron(Operator, CUSTOM_OT_NEURON_operator):
    bl_idname = "custom.get_cell_list_from_neuron"
    bl_label = "List NEURON Cells"
    bl_description = "Get all cells currently instantiated in NEURON"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        client = bpy.types.Object.BlenderNEURON_node.client
        cell_list = context.scene.BlenderNEURON_neuron_cells
        
        cell_list.clear()
        
        cell_data = client.get_root_section_names()
                
        for cell_info in cell_data:
            item = cell_list.add()
            item.name = cell_info[1]
            item.id = cell_info[0]
            
        return{'FINISHED'}

class CUSTOM_OT_select_all_neuron_cells(Operator, CUSTOM_OT_NEURON_operator):
    bl_idname = "custom.select_all_neuron_cells"
    bl_label = "Select All"
    bl_description = "Select all cells to be shown in Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        cells = context.scene.BlenderNEURON_neuron_cells
        
        for item in cells:
            item.selected = True
            
        return{'FINISHED'}

class CUSTOM_OT_select_none_neuron_cells(Operator, CUSTOM_OT_NEURON_operator):
    bl_idname = "custom.select_none_neuron_cells"
    bl_label = "None"
    bl_description = "Unselect all cells for showing in Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        cells = context.scene.BlenderNEURON_neuron_cells
        
        for item in cells:
            item.selected = False
            
        return{'FINISHED'}

class CUSTOM_OT_select_none_neuron_cells(Operator, CUSTOM_OT_NEURON_operator):
    bl_idname = "custom.select_none_neuron_cells"
    bl_label = "None"
    bl_description = "Unselect all cells for showing in Blender"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        cells = context.scene.BlenderNEURON_neuron_cells
        
        for item in cells:
            item.selected = False
            
        return{'FINISHED'}

class CUSTOM_OT_import_selected_neuron_cells(Operator, CUSTOM_OT_NEURON_operator):
    bl_idname = "custom.import_selected_neuron_cells"
    bl_label = "Import Selected Cells"
    bl_description = "Show the selected NEURON cells in Blender 3D View"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        cells = context.scene.BlenderNEURON_neuron_cells
        
        pass
            
        return{'FINISHED'}


class CUSTOM_UL_items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item,"selected",text="")
        layout.label(item.name)

    def invoke(self, context, event):
        pass   

class CUSTOM_PT_objectList(Panel):
    """Adds a custom panel to the TEXT_EDITOR"""
    bl_idname = 'TEXT_PT_my_panel'
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_label = "NEURON Cells"

    def draw(self, context):        
        scene = context.scene
        
        self.layout.operator("custom.get_cell_list_from_neuron", icon="FREEZE")
        
        self.layout.template_list("CUSTOM_UL_items", "", \
            scene, "BlenderNEURON_neuron_cells", \
            scene, "BlenderNEURON_neuron_cells_index", \
            rows=5)
            
        col = self.layout.split(0.33)
        col.operator("custom.select_all_neuron_cells")
        col.operator("custom.select_none_neuron_cells")
        col.operator("custom.select_invert_neuron_cells")
        
        col = self.layout.box().column(align=True)
        col.prop(scene, "BlenderNEURON_import_recording_granularity", text="Record")    
        col.prop(scene, "BlenderNEURON_record_variable", text="Variable")
        col.prop(scene, "BlenderNEURON_import_interaction_granularity", text="Interact")    
        
        col.separator()    
        col.operator("custom.import_selected_neuron_cells", text="Setup Selected Cells for Recording", icon="EYEDROPPER")
               
        col = self.layout 
        col.prop(scene, "BlenderNEURON_neuron_tstop", text="Stop Time")   
        col.prop(scene, "BlenderNEURON_temperature", text="Temperature")   
        
        
        col.operator("custom.import_selected_neuron_cells", text="Open Voltage Plot", icon="FCURVE")
        col.operator("custom.import_selected_neuron_cells", text="Init & Run", icon="POSE_DATA")
        col.prop(scene, "BlenderNEURON_integration_method")     
        
        col = self.layout.box().column(align=True)
        
        col.prop(scene, "BlenderNEURON_import_activity", text="Import Activity")
        col.prop(scene, "BlenderNEURON_import_synapses", text="Import Synapses")
        col.operator("custom.import_selected_neuron_cells", text="Display Selected Cells in Blender", icon="PLAY")



class CUSTOM_NEURON_Cell(PropertyGroup):
    index = IntProperty()
    selected = BoolProperty(default=True)


def register():
    bpy.utils.register_module(__name__)
    
    bpy.types.Scene.BlenderNEURON_neuron_cells = CollectionProperty(type=CUSTOM_NEURON_Cell)
    bpy.types.Scene.BlenderNEURON_neuron_cells_index = IntProperty() # this is needed for the list, but not used otherwise

    bpy.types.Scene.BlenderNEURON_record_variable = StringProperty(default="v", description="The NEURON section variable to record"
            " (e.g. 'v' of soma(0.5).v) and display as segment brigthness in Blender")

    bpy.types.Scene.BlenderNEURON_import_activity = BoolProperty(default=True, description="Imports the recorded values from the selected variable (based on granularity) and shows it at variation in Blender segment brightness")
    bpy.types.Scene.BlenderNEURON_import_synapses = BoolProperty(default=True, description="Imports synaptic connections and visually represents them in Blender")
    
    bpy.types.Scene.BlenderNEURON_neuron_tstop = IntProperty(min=0, description="The simulation stop time (e.g. h.tstop) in ms")
    bpy.types.Scene.BlenderNEURON_temperature = FloatProperty(default=6.3, description="The simulation temperature in degrees Celsius")

    bpy.types.Scene.BlenderNEURON_import_recording_granularity = bpy.props.EnumProperty(
        items = [
            ('0', 'Cell Group', 'Coarsest. Reports the mean value across all selected cell somas (root segments)'),
            ('1', 'Soma', 'Reports the value at each selected cell soma (root)'),
            ('2', 'Section', 'Reports the values at each selected cell section'),
            ('3', 'Segment', 'Finest. Reports the values at each selected cell section segment'),
        ],
        name = "Recording granularity",
        description = "The granularity used to record from selected cells. Finest recording granularity requires more time and memory, coarsest less so.",
        default = '2'
    )
    
    bpy.types.Scene.BlenderNEURON_import_interaction_granularity = bpy.props.EnumProperty(
        items = [
            ('0', 'Cell Group', 'Coarsest. The group of selected cells is represented as one object in Blender'),
            ('1', 'Cell', 'Each cell is represented as a Blender object'),
            ('2', 'Section', 'Finest. Each cell section is represented as a Blender object'),
        ],
        name = "Interaction granularity",
        description = "The granularity used to represent selected cells in Blender. Finer granularity allows interaction with smaller parts of cells, but can result in performance issues if the number of cells/sections is large. Coarser interativity increases performance for larger models.",
        default = '2'
    )
    
    bpy.types.Scene.BlenderNEURON_integration_method = bpy.props.EnumProperty(
        items = [
            ('0', 'Fixed Step', 'Each simulation step is constant size'),
            ('1', 'Variable Step (CVODE)', 'Each simulation step is variable depending on the rate of state changes'),
        ],
        name = "Integrator",
        description = "Variable step tends to be faster for single cells and low firing rates. Fixed step tends to be faster for networks and high firing rates.",
        default = '1'
    )

def unregister():
    del bpy.types.Scene.custom
    del bpy.types.Scene.custom_index


if __name__ == "__main__":
    register()