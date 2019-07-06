import bpy, random

from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       PointerProperty,
                       FloatProperty)

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)


class CUSTOM_NEURON_Cell(PropertyGroup):
    # Update the root list group membership
    def on_selected_updated(self, context):

        root = context.scene.BlenderNEURON_neuron_roots[self.name]

        # Update the group of the selected section
        if self.selected:

            new_group_index = context.scene.BlenderNEURON_neuron_cellgroups_index

            # If in an existing group and the new group are not the same
            if new_group_index != root.group_index:
                if root.group_index != -1:
                    current_group = context.scene.BlenderNEURON_neuron_cellgroups[root.group_index]

                    # Remove from the existing group
                    # This will also set the root group to -1
                    current_group.cells[self.name].selected = False

                # Add to current group
                root.group_index = new_group_index

        else:
            root.group_index = -1


    index = IntProperty()
    selected = BoolProperty(default=False, update=on_selected_updated)
    group_index = IntProperty(default=-1) # Unassigned to group

class CUSTOM_NEURON_CellGroup(PropertyGroup):
    index = IntProperty()
    selected = BoolProperty(default=True)

    cells = CollectionProperty(type=CUSTOM_NEURON_Cell)
    cells_index = IntProperty()

    import_activity = BoolProperty(
        default=True,
        description="Imports the recorded values from the selected variable (based on granularity) "
                    "and shows it at variation in Blender segment brightness")

    import_synapses = BoolProperty(
        default=True,
        description="Imports synaptic connections and visually represents them in Blender"
    )

    record_variable = StringProperty(
        default="v",
        description="The NEURON section variable to record"
                    " (e.g. 'v' of soma(0.5).v) and display as segment brigthness in Blender"
    )

    recording_granularity = bpy.props.EnumProperty(
        items=[
            ('0', 'Cell Group', 'Coarsest. Reports the mean value across all selected cell somas (root segments)'),
            ('1', 'Soma', 'Reports the value at each selected cell soma (root)'),
            ('2', 'Section', 'Reports the values at each selected cell section'),
            ('3', 'Segment', 'Finest. Reports the values at each selected cell section segment'),
        ],
        name="Recording granularity",
        description="The granularity used to record from selected cells. Finest recording "
                    "granularity requires more time and memory, coarsest less so.",
        default='2'
    )

    interaction_granularity = bpy.props.EnumProperty(
        items=[
            ('0', 'Cell Group', 'Coarsest. The group of selected cells is represented as '
                                'one object in Blender'),
            ('1', 'Cell', 'Each cell is represented as a Blender object'),
            ('2', 'Section', 'Finest. Each cell section is represented as a Blender object'),
        ],
        name="Interaction granularity",
        description="The granularity used to represent selected cells in Blender. "
                    "Finer granularity allows interaction with smaller parts of cells, "
                    "but can result in performance issues if the number of cells/sections "
                    "is large. Coarser interativity increases performance for larger models.",
        default='2'
    )

class CUSTOM_NEURON_SimulatorSettings(PropertyGroup):
    def get_client(self):
        return bpy.types.Object.BlenderNEURON_node.client

    def neuron_tstop_get(self):
        return self.get_client().run_command("return_value = h.tstop")

    def neuron_tstop_set(self, value):
        self.get_client().run_command("h.tstop = " + str(value))

    neuron_tstop = FloatProperty(
        min = 0,
        default = 100,
        description="The simulation stop time (e.g. h.tstop) in ms",
        get=neuron_tstop_get, set=neuron_tstop_set
    )

    time_step = FloatProperty(
        default=0.25,
        min = 0,
        description="The time step used by the Fixed Step integrator (in ms)"
    )

    abs_tolerance = FloatProperty(
        default=0.001,
        min=0,
        description="The absolute tolerace used by the Variable Step (CVODE) integrator"
    )

    temperature = FloatProperty(
        default=6.3,
        description="The simulation temperature in degrees Celsius"
    )

    integration_method = bpy.props.EnumProperty(
        items=[
            ('0', 'Fixed Step', 'Each simulation step is constant size'),
            ('1', 'Variable Step (CVODE)', 'Each simulation step is variable depending '
                                           'on the rate of state changes'),
        ],
        name="Integrator",
        description="Variable step tends to be faster for single cells and low firing "
                    "rates. Fixed step tends to be faster for networks and high firing rates.",
        default='1'
    )


def register():

    bpy.types.Scene.BlenderNEURON_neuron_cellgroups_index = IntProperty()

    bpy.types.Scene.BlenderNEURON_neuron_cellgroups = CollectionProperty(
        type=CUSTOM_NEURON_CellGroup
    )

    bpy.types.Scene.BlenderNEURON_neuron_roots = CollectionProperty(
        type=CUSTOM_NEURON_Cell
    )

    bpy.types.Scene.BlenderNEURON_simulator_settings = PointerProperty(
        type=CUSTOM_NEURON_SimulatorSettings
    )


def unregister():
    del bpy.types.Scene.BlenderNEURON_neuron_cellgroups
    del bpy.types.Scene.BlenderNEURON_neuron_cellgroups_index
    del bpy.types.Scene.BlenderNEURON_neuron_roots
    del bpy.types.Scene.BlenderNEURON_simulator_settings