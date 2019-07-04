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


class CUSTOM_NEURON_Cell(PropertyGroup):
    # Update the root list group membership
    def on_selected_updated(self, context):
        context.scene.BlenderNEURON_neuron_roots[self.name].group_index = \
            context.scene.BlenderNEURON_neuron_cellgroups_index

    index = IntProperty()
    selected = BoolProperty(default=True, update=on_selected_updated)
    group_index = IntProperty(default=-1) # Unassigned to group

class CUSTOM_NEURON_CellGroup(PropertyGroup):
    index = IntProperty()
    selected = BoolProperty(default=True)

    group_cells = CollectionProperty(type=CUSTOM_NEURON_Cell)
    group_cells_index = IntProperty()


def register():

    bpy.types.Scene.BlenderNEURON_neuron_cellgroups_index = IntProperty()
    bpy.types.Scene.BlenderNEURON_neuron_cellgroups = CollectionProperty(
        type=CUSTOM_NEURON_CellGroup
    )

    bpy.types.Scene.BlenderNEURON_neuron_roots = CollectionProperty(
        type=CUSTOM_NEURON_Cell
    )

    bpy.types.Scene.BlenderNEURON_record_variable = StringProperty(
        default="v",
        description="The NEURON section variable to record"
            " (e.g. 'v' of soma(0.5).v) and display as segment brigthness in Blender"
    )

    bpy.types.Scene.BlenderNEURON_import_activity = BoolProperty(
        default=True,
        description="Imports the recorded values from the selected variable (based on granularity) "
                    "and shows it at variation in Blender segment brightness")
    bpy.types.Scene.BlenderNEURON_import_synapses = BoolProperty(
        default=True,
        description="Imports synaptic connections and visually represents them in Blender"
    )
    
    bpy.types.Scene.BlenderNEURON_neuron_tstop = IntProperty(
        min=0,
        description="The simulation stop time (e.g. h.tstop) in ms"
    )
    bpy.types.Scene.BlenderNEURON_temperature = FloatProperty(
        default=6.3,
        description="The simulation temperature in degrees Celsius"
    )

    bpy.types.Scene.BlenderNEURON_import_recording_granularity = bpy.props.EnumProperty(
        items = [
            ('0', 'Cell Group', 'Coarsest. Reports the mean value across all selected cell somas (root segments)'),
            ('1', 'Soma', 'Reports the value at each selected cell soma (root)'),
            ('2', 'Section', 'Reports the values at each selected cell section'),
            ('3', 'Segment', 'Finest. Reports the values at each selected cell section segment'),
        ],
        name = "Recording granularity",
        description = "The granularity used to record from selected cells. Finest recording "
                      "granularity requires more time and memory, coarsest less so.",
        default = '2'
    )
    
    bpy.types.Scene.BlenderNEURON_import_interaction_granularity = bpy.props.EnumProperty(
        items = [
            ('0', 'Cell Group', 'Coarsest. The group of selected cells is represented as '
                                'one object in Blender'),
            ('1', 'Cell', 'Each cell is represented as a Blender object'),
            ('2', 'Section', 'Finest. Each cell section is represented as a Blender object'),
        ],
        name = "Interaction granularity",
        description = "The granularity used to represent selected cells in Blender. "
                      "Finer granularity allows interaction with smaller parts of cells, "
                      "but can result in performance issues if the number of cells/sections "
                      "is large. Coarser interativity increases performance for larger models.",
        default = '2'
    )
    
    bpy.types.Scene.BlenderNEURON_integration_method = bpy.props.EnumProperty(
        items = [
            ('0', 'Fixed Step', 'Each simulation step is constant size'),
            ('1', 'Variable Step (CVODE)', 'Each simulation step is variable depending '
                                           'on the rate of state changes'),
        ],
        name = "Integrator",
        description = "Variable step tends to be faster for single cells and low firing "
                      "rates. Fixed step tends to be faster for networks and high firing rates.",
        default = '1'
    )


def unregister():
    del bpy.types.Scene.BlenderNEURON_neuron_cellgroups
    del bpy.types.Scene.BlenderNEURON_neuron_cellgroups_index
    del bpy.types.Scene.BlenderNEURON_record_variable
    del bpy.types.Scene.BlenderNEURON_import_activity
    del bpy.types.Scene.BlenderNEURON_import_synapses
    del bpy.types.Scene.BlenderNEURON_neuron_tstop
    del bpy.types.Scene.BlenderNEURON_temperature
    del bpy.types.Scene.BlenderNEURON_import_recording_granularity
    del bpy.types.Scene.BlenderNEURON_import_interaction_granularity
    del bpy.types.Scene.BlenderNEURON_integration_method