import bpy, random, numpy

from bpy.props import (IntProperty,
                       BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       PointerProperty,
                       FloatProperty,
                       FloatVectorProperty)

from bpy.types import (Operator,
                       Panel,
                       PropertyGroup,
                       UIList)


class CUSTOM_NEURON_Activity(PropertyGroup):
    times = numpy.array([])
    values = numpy.array([])

    def clear(self):
        self.times = numpy.array([])
        self.values = numpy.array([])

    def from_NEURON_dict(self, nrn_activity):
        self.times = numpy.array(nrn_activity["times"])
        self.values = numpy.array(nrn_activity["values"])

class CUSTOM_NEURON_CellSectionTEST(CUSTOM_NEURON_CellSection):
    children = CollectionProperty(type=CUSTOM_NEURON_CellSection)

class CUSTOM_NEURON_CellSection(PropertyGroup):
    coords = numpy.array([]) # Point XYZ coordinates, stored as [x1,y1,z1, x2,y2,z2, ... ]
    radii = numpy.array([])  # Point radii - length should be exactly coords/3

    coord_activity = CollectionProperty(type=CUSTOM_NEURON_Activity)
    activity = PointerProperty(type=CUSTOM_NEURON_Activity)

    # 0-1.0 - location along the parent section where this section is connected
    # In NEURON: child_sec.parentseg().x
    parent_connection_loc = FloatProperty(min=0, max=1, default=1.0)

    # Which end 0 or 1 of this section that connects to the parent section
    # In NEURON: child_sec.orientation()
    connection_end = IntProperty(min=0, max=1, default=0)

    def clear_activity(self):
        self.activity.clear()

        for ca in self.coord_activity:
            ca.clear()

        for child in self.children:
            child.clear_activity()

    def to_dict_for_NEURON(self):
        return {
            "name": self.name,
            "coords": self.coords.tolist(),
            "radii": self.radii.tolist(),
            "children": [child.to_dict_for_NEURON() for child in self.children],
            "parent_connection_loc": self.parent_connection_loc,
            "connection_end": self.connection_end,
            "activity": { "times": [], "values": [] },
            "coord_activity": {"times": [], "values": []},
        }

    def from_NEURON_dict(self, nrn_section):
        self.coords = numpy.array(nrn_section["coords"])
        self.radii = numpy.array(nrn_section["radii"])

        for nrn_child in nrn_section["children"]:
            self.children[nrn_child["name"]].from_NEURON_dict(nrn_child)

        self.parent_connection_loc = nrn_section["parent_connection_loc"]
        self.connection_end = nrn_section["connection_end"]

        self.activity.from_NEURON_dict(nrn_section["activity"])
        self.coord_activity.from_NEURON_dict(nrn_section["coord_activity"])


class CUSTOM_NEURON_Cell(PropertyGroup):

    # Update the root list group membership
    def on_selected_updated(self, context):

        root = context.scene.BlenderNEURON_neuron_roots[self.name]

        # Update the group of the selected section
        if self.selected:

            new_group_index = context.scene.BlenderNEURON_cellgroups_index

            # If in an existing group and the new group are not the same
            if new_group_index != root.group_index:
                if root.group_index != -1:
                    current_group = context.scene.BlenderNEURON_cellgroups[root.group_index]

                    # Remove from the existing group
                    # This will also set the root group to -1
                    current_group.cells[self.name].selected = False

                # Add to current group
                root.group_index = new_group_index

        else:
            root.group_index = -1

    # Group membership properties
    selected = BoolProperty(default=False, update=on_selected_updated)
    group_index = IntProperty(default=-1)  # Unassigned to group
    index = IntProperty()

    # Topology properties
    roots = CollectionProperty(type=CUSTOM_NEURON_CellSection)

    activity = PointerProperty(type=CUSTOM_NEURON_Activity)

    def clear_activity(self):
        self.activity.clear()

    def to_dict_for_NEURON(self):
        return {
            "name": self.name,
            "roots": [root.to_dict_for_NEURON() for root in self.roots],
            "activity": { "times": [], "values": [] }
        }

    def from_NEURON_dict(self, nrn_cell):

        for nrn_root in nrn_cell["roots"]:
            self.roots[nrn_root["name"]].from_NEURON_dict(nrn_root)

        self.activity.from_NEURON_dict(nrn_cell["activity"])


class CUSTOM_NEURON_CellGroup(PropertyGroup):

    activity = PointerProperty(type=CUSTOM_NEURON_Activity)

    def clear_activity(self):
        self.activity.clear()

        for root in self.roots:
            root.clear_activity()

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

    # TODO move this to a map property
    smooth_sections = BoolProperty(
        default=True,
        description="Whether to render sections as smooth bezier curves, instead of straight lines. "
                    "True results in more visually appealing morphology, but requires more polygons."
    )

    # TODO move this to a map property
    spherize_soma_if_DeqL = BoolProperty(
        default=True,
        description="Whether to display a soma section with diameter ~= length as a sphere in Blender"
    )

    # TODO move this to a map property
    as_lines = BoolProperty(
        default=False,
        description="Whether to display sections as line segments (no radius). This is fast, but cannot be rendered."
    )

    # TODO move this to a map property
    segment_subdivisions = IntProperty(
        default=3,
        min=2,
        description="Number of linear subdivisions to use when displaying a section. Higher results in smooth-"
                    "looking section curvature, but requires more polygons."
    )

    # TODO move this to a map property
    circular_subdivisions = IntProperty(
        default=12,
        min=5,
        description="Number of linear subdivisions to use when displaying a section. Higher results in smooth-"
                    "looking section curvature."
    )

    recording_period = FloatProperty(
        default=1.0,
        min=0.0,
        description="How often to collect the recording variable during simulation (ms)"
    )

    record_variable = StringProperty(
        default="v",
        description="The NEURON section variable to record"
                    " (e.g. 'v' of soma(0.5).v) and display as segment brigthness in Blender"
    )

    recording_granularity = bpy.props.EnumProperty(
        items=[
            ('Group', 'Cell Group', 'Coarsest. Reports the mean value across all selected cell somas (root segments)'),
            ('Cell', 'Soma', 'Reports the value at each selected cell soma (root)'),
            ('Section', 'Section', 'Reports the values at each selected cell section'),
            ('3D Point', '3D Point', 'Finest. Reports the values at each cell section 3D point'),
        ],
        name="Recording granularity",
        description="The granularity used to record from selected cells. Finest recording "
                    "granularity requires more time and memory, coarsest less so.",
        default='Section'
    )

    interaction_granularity = bpy.props.EnumProperty(
        items=[
            ('Group', 'Cell Group', 'Coarsest. The group of selected cells is represented as '
                                'one object in Blender'),
            ('Cell', 'Cell', 'Each cell is represented as a Blender object'),
            ('Section', 'Section', 'Finest. Each cell section is represented as a Blender object'),
        ],
        name="Interaction granularity",
        description="The granularity used to represent selected cells in Blender. "
                    "Finer granularity allows interaction with smaller parts of cells, "
                    "but can result in performance issues if the number of cells/sections "
                    "is large. Coarser interativity increases performance for larger models.",
        default='Cell'
    )

    def to_dict_for_NEURON(self):
        result = {
            'name': self.name,
            'activity': { "times": [], "values": [] },
            'cells': [cell.to_dict_for_NEURON() for cell in self.cells if cell.selected],
            'import_activity': self.import_activity,
            'record_variable': self.record_variable,
            'recording_period': self.recording_period,
            'recording_granularity': self.recording_granularity,
        }

        return result

    def from_NEURON_dict(self, nrn_group):

        self.clear_activity()
        self.activity.from_NEURON_dict(nrn_group["activity"])

        for nrn_cell in nrn_group["cells"]:
            cell_name = nrn_cell["name"]
            self.cells[cell_name].from_NEURON_dict(nrn_cell)

        result = {
            'cells': [cell.to_dict_for_NEURON() for cell in self.cells if cell.selected],
            'import_activity': self.import_activity,
            'record_variable': self.record_variable,
            'recording_period': self.recording_period,
            'recording_granularity': self.recording_granularity,
        }

        return result

class CUSTOM_NEURON_SimulatorSettings(PropertyGroup):

    def get_client(self):
        try:
            return bpy.types.Object.BlenderNEURON_node.client
        except:
            return None

    def to_neuron(self, context=None):
        self.get_client().set_sim_params({
            "tstop": self.neuron_tstop,
            "dt": self.time_step,
            "atol": self.abs_tolerance,
            "celsius": self.temperature,
            "cvode": self.integration_method,
        })

    def from_neuron(self):
        client = self.get_client()

        if client is None:
            return

        params = client.get_sim_params()

        self.neuron_tstop = params["tstop"]
        self.time_step = params["dt"]
        self.abs_tolerance = params["atol"]
        self.temperature = params["celsius"]
        self.integration_method = str(int(float(params["cvode"])))

    neuron_tstop = FloatProperty(
        min = 0,
        default = 100,
        description="The simulation stop time (e.g. h.tstop) in ms",
        update=to_neuron
    )

    time_step = FloatProperty(
        default=0.25,
        min = 0,
        precision=3,
        description="The time step used by the Fixed Step integrator (in ms)",
        update=to_neuron
    )

    abs_tolerance = FloatProperty(
        default=0.001,
        min=0,
        precision=5,
        description="The absolute tolerace used by the Variable Step (CVODE) integrator",
        update=to_neuron
    )

    temperature = FloatProperty(
        default=6.3,
        description="The simulation temperature in degrees Celsius",
        update=to_neuron
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
        default='1',
        update=to_neuron
    )

def register():

    bpy.types.Scene.BlenderNEURON_cellgroups_index = IntProperty()

    bpy.types.Scene.BlenderNEURON_cellgroups = CollectionProperty(
        type=CUSTOM_NEURON_CellGroup
    )

    bpy.types.Scene.BlenderNEURON_neuron_roots = CollectionProperty(
        type=CUSTOM_NEURON_Cell
    )

    bpy.types.Scene.BlenderNEURON_simulator_settings = PointerProperty(
        type=CUSTOM_NEURON_SimulatorSettings
    )


def unregister():
    del bpy.types.Scene.BlenderNEURON_cellgroups
    del bpy.types.Scene.BlenderNEURON_cellgroups_index
    del bpy.types.Scene.BlenderNEURON_neuron_roots
    del bpy.types.Scene.BlenderNEURON_simulator_settings