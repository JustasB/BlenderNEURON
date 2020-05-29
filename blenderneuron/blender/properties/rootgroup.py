import bpy, random, numpy

from blenderneuron.blender.views.synapseformerview import SynapseFormerView
from blenderneuron.blender import BlenderNodeClass

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
                       UIList,
                       Object)


class BlenderRootProperties(PropertyGroup, BlenderNodeClass):
    name = StringProperty()
    index = IntProperty()

    def on_selected_updated(self, context):
        new_group = self.node.ui_properties.group.node_group if self.selected else None
        self.node.root_index[self.name].add_to_group(new_group)

    selected = BoolProperty(default=False, update=on_selected_updated)


class LayerConfinerProperties(PropertyGroup, BlenderNodeClass):
    start_mesh = PointerProperty(
        type=Object,
        name="Start Layer",
        description="The mesh above which the pattern matching sections will be confined"
    )

    end_mesh = PointerProperty(
        type=Object,
        name="End Layer",
        description="The second mesh under which the sections will be confined"
    )

    moveable_sections_pattern = StringProperty(
        name="Section Pattern",
        default="*dend*",
        description="If the name of a section matches this pattern (* and ? wildcards allowed), "
                    "the section(s) will be confined between the selected layers"
    )

    max_bend_angle = FloatProperty(
        default=15,
        min=0,
        max=180,
        name="Max bend angle (degrees)",
        description="The maximum angle (degrees) by which the sections are allowed to"
                    " deviate from their original positions"
    )

    seed = IntProperty(
        default=0,
        min=0,
        name="Random seed",
        description="Random seed for the aligner"
    )

    height_min = FloatProperty(
        min=-3,
        default=0,
        max=3,
        name="Layer height min fraction",
        description="The fraction of distance between the two layers where the confinement"
                    "bfegins. 0: as close to the starting layer. 1: as close to the end layer. Negative"
                    "values will start confinement below the starting layer. >1 values will end the confinement"
                    "above the end layer"
    )

    height_max = FloatProperty(
        min=-3,
        default=0.5,
        max=3,
        name="Layer height max fraction",
        description="The fraction of distance between the two layers where the confinement"
                    "stops. 0: as close to the starting layer. 1: as close to the end layer. Negative"
                    "values will start confinement below the starting layer. >1 values will end the confinement"
                    "above the end layer"
    )

    max_section_length = FloatProperty(
        default=200,
        min=1,
        name="Maximum section length",
        description="Sections that are longer than this value will be split into smaller, same length sections. "
                    "Set to value longer than longest section (e.g. 99999) to disable splitting"
    )




class SynapseConnectorProperties(PropertyGroup, BlenderNodeClass):

    def get_name(self):
        return self.name

    def set_name(self, new_name):

        syn_sets = bpy.context.scene.BlenderNEURON.synapse_sets

        # Don't update to an existing set name
        if (new_name in syn_sets.keys() and self.name != '') or \
           new_name == '' or \
           self.name == new_name:
            return

        self.name = new_name

    name_editable = StringProperty(get=get_name, set=set_name)

    group_source = bpy.props.EnumProperty(items=BlenderNodeClass.get_group_list,
                                          name="From Cell Group",
                                          description="Cells in this BlenderNEURON group will "
                                                    "be connected to cells in the other group")

    group_dest = bpy.props.EnumProperty(items=BlenderNodeClass.get_group_list,
                                        name="To Cell Group",
                                        description="Cells in this groups will receive connections"
                                                  " from cells in the first group")

    max_distance = FloatProperty(
        default=5,
        min=0,
        name="Max Proximity Distance (um)",
        description="The maximum distance between segments that will be used to form synapses"
    )

    use_radius = BoolProperty(
        default=True,
        name="Use Radius",
        description="Whether 3D point radii should be utilized when searching for synapse "
                    "formation locations. When False, the proximity distance only uses "
                    "distances between 3D points without including diameters (slightly faster)"
    )

    max_syns_per_pt = IntProperty(
        default=4,
        name="Max Syns/Pt",
        description="The maximum number of synapses that are allowed to be positioned at a given "
                    "section 3D point"
    )

    section_pattern_source = StringProperty(
        default="*apic*",
        name="From Section Pattern",
        description="The section name pattern to use when selecting source cell sections. "
                    "Use ? and * wildcards to match one or more characters respectively"
    )

    section_pattern_dest = StringProperty(
        default="*dend*",
        name="To section pattern",
        description="The section name pattern to use when selecting destination cell sections. "
                    "Use ? and * wildcards to match one or more characters respectively"
    )

    synapse_name_dest = StringProperty(
        default="ExpSyn",
        name="Synapse Class Name",
        description="The name of NEURON synaptic mechanism that will be "
                    "placed on the destination cell"
    )

    synapse_params_dest = StringProperty(
        default="{'g':1,'tau':10}",
        name="Parameters",
        description="Optional synapse mechanism parameters as a Python dictionary e.g. {'g':1,'tau':10}"
    )

    is_reciprocal = BoolProperty(
        default=False,
        name="Is Reciprocal",
        description="Whether the synapses should be reciprocal (from->to->from) or uni-directional (from->to)"
    )

    synapse_name_source = StringProperty(
        default="ExpSyn",
        name="Reciprocal Synapse Class Name",
        description="The name of NEURON synaptic mechanism that will be placed on the "
                    "source cell (when reciprocal)"
    )

    synapse_params_source = StringProperty(
        default="{'g':1,'tau':10}",
        name="Parameters",
        description="Optional reciprocal synapse mechanism parameters as a Python dictionary e.g. {'g':1,'tau':10}"
    )

    create_spines = BoolProperty(
        default=True,
        name="Create Spines",
        description="Whether a spine (neck+head) should be created from source to destination sections"
    )

    spine_neck_diameter = FloatProperty(
        default=0.2,
        min=0,
        name="Neck Diam (um)",
        description="Diameter of spine necks (um). Length is determined by the distance between source and "
                    "destination sections. If distance between source and destination section is less than "
                    "the head diameter, the spine neck is omitted"
    )

    spine_head_diameter = FloatProperty(
        default=1,
        min=0,
        name="Head Diam (um)",
        description="Diameter of spine heads (um). Length is same as diameter (e.g. spherical)"
    )

    spine_name_prefix = StringProperty(
        default="Spine",
        name="Prefix",
        description="The prefix used in names of spine sections. E.g. 'Spine' becomes Spine[0...N].neck/.head"
    )

    conduction_velocity = FloatProperty(
        default=1,
        min=0,
        name="Conduction Velocity (m/s)",
        description="Conduction velocity to use when computing the synaptic delay"
    )

    synaptic_delay = FloatProperty(
        default=0.5,
        min=0.001,
        name="Synaptic Delay (ms)",
        description="The time between crossing pre-synaptic threshold and the "
                    "onset of post-synaptic current (NetCon.delay)"
    )

    initial_weight = FloatProperty(
        default=1,
        min=0,
        name="Initial Weight",
        description="The initial synaptic weight"
    )

    threshold = FloatProperty(
        default=0,
        name="Firing Threshold (mV)",
        description="The threshold that the source cell segment membrane potential "
                    "must cross to trigger the synaptic event"
    )

    @property
    def pairs(self):
        try:
            return self.node.groups[self.group_source].view.synapse_pairs
        except:
            return []

    def get_synapse_locations(self):

        source_group = self.node.groups[self.group_source]
        dest_group = self.node.groups[self.group_dest]

        # Detect if any of the selected groups haven't been imported (no 3d data)
        import_groups = [group for group in [source_group, dest_group] if group.state != 'imported']

        # Import them
        if len(import_groups) > 0:
            for group in import_groups:
                group.interaction_granularity = 'Cell'
                group.recording_granularity = 'Cell'
                group.record_activity = False
                group.import_synapses = False

            self.node.import_groups_from_neuron(import_groups)

        source_group.show(SynapseFormerView, dest_group)

        pairs = source_group.view.get_synapse_locations(
            self.max_distance,
            self.use_radius,
            self.max_syns_per_pt,
            self.section_pattern_source,
            self.section_pattern_dest
        )

        return pairs
    
    def create_synapses(self):
        from_group = self.node.groups[self.group_source]

        if type(from_group.view) is not SynapseFormerView:
            raise Exception('Synapses need to be found before they can be created in NEURON')

        from_group.view.create_synapses(
            self.name,
            self.synapse_name_dest,
            self.synapse_params_dest,
            self.conduction_velocity,
            self.synaptic_delay,
            self.initial_weight,
            self.threshold,
            self.is_reciprocal,
            self.synapse_name_source,
            self.synapse_params_source,
            self.create_spines,
            self.spine_neck_diameter,
            self.spine_head_diameter,
            self.spine_name_prefix
        )

    def save_synapses(self, file_name):
        from_group = self.node.groups[self.group_source]

        if type(from_group.view) is not SynapseFormerView:
            raise Exception('Synapses need to be found before they can be saved')

        from_group.view.save_synapses(
            file_name,
            self.name,
            self.synapse_name_dest,
            self.synapse_params_dest,
            self.conduction_velocity,
            self.synaptic_delay,
            self.initial_weight,
            self.threshold,
            self.is_reciprocal,
            self.synapse_name_source,
            self.synapse_params_source,
            self.create_spines,
            self.spine_neck_diameter,
            self.spine_head_diameter,
            self.spine_name_prefix
        )



class RootGroupProperties(PropertyGroup, BlenderNodeClass):

    def get_name(self):
        return self.name

    def set_name(self, new_name):

        
        # Don't update to an existing name
        if (new_name in self.node.groups and self.name != '') or \
           new_name == '' or \
           self.name == new_name:
            return

        # To rename a group, we need to change the key name
        if self.name != '':

            # This is done by removing the old value
            # and placing it at the new name key
            node_group = self.node.groups.pop(self.name)
            self.node.groups[new_name] = node_group

            # Update the node group name
            node_group.name = new_name

        # Update UI group name
        self.name = new_name

    name_editable = StringProperty(get=get_name, set=set_name)

    @property
    def node_group(self):
        return self.node.groups[self.name]

    # The following two methods are helper methods for setting node group properties via the GUI
    def get_prop(prop):
        def get(self):
            return getattr(self.node_group, prop)
        return get

    def set_prop(prop):
        def set(self, value):
            setattr(self.node_group, prop, value)
        return set

    index = IntProperty(get=get_prop("index"), set=set_prop("index"))
    selected = BoolProperty(default=True, get=get_prop("selected"), set=set_prop("selected"))

    root_entries = CollectionProperty(type=BlenderRootProperties)
    root_entries_index = IntProperty()

    copy_from_group = bpy.props.EnumProperty(items=BlenderNodeClass.get_group_list,
                                          name="Copy Cell Group",
                                          description="Group options will be copied to "
                                                      "the current group from the selected group")

    record_activity = BoolProperty(
        default=True,
        get=get_prop("record_activity"),
        set=set_prop("record_activity"),
        description="Imports the recorded values from the selected variable (based on granularity) "
                    "and shows it as variation in Blender segment brightness")

    recording_time_start = FloatProperty(
        default=0,
        min=0,
        get=get_prop("recording_time_start"),
        set=set_prop("recording_time_start"),
        description="The simulation time at which to start recording (ms)"
    )

    recording_time_end = FloatProperty(
        default=0,
        min=0,
        get=get_prop("recording_time_end"),
        set=set_prop("recording_time_end"),
        description="The simulation time at which to stop recording (ms). "
                    "0 will record until the end of simulation"
    )

    import_synapses = BoolProperty(
        default=True,
        get=get_prop("import_synapses"),
        set=set_prop("import_synapses"),
        description="Imports synaptic connections and visually represents them in Blender"
    )

    recording_period = FloatProperty(
        default=1.0,
        min=0.0,
        get=get_prop("recording_period"),
        set=set_prop("recording_period"),
        description="How often to collect the recording variable during simulation (ms)"
    )

    record_variable = StringProperty(
        default="v",
        get=get_prop("record_variable"),
        set=set_prop("record_variable"),
        description="The NEURON section variable to record"
                    " (e.g. 'v' of soma(0.5).v) and use to animate segments in Blender"
    )

    animate_brightness = BoolProperty(
        default=True,
        get=get_prop("animate_brightness"),
        set=set_prop("animate_brightness"),
        description="Whether to translate recorded variable (e.g. Vm) values to brightness"
    )

    animate_color = BoolProperty(
        default=True,
        get=get_prop("animate_color"),
        set=set_prop("animate_color"),
        description="Whether to translate recorded variable (e.g. Vm) values to color"
    )

    animation_range_low = FloatProperty(
        default=-85,
        get=get_prop("animation_range_low"),
        set=set_prop("animation_range_low"),
        description="This value of the recorded variable (e.g. Vm) will map to the"
                    " lowest brightness and to the leftmost color (0 position) of the "
                    "color ramp above"
    )

    animation_range_high = FloatProperty(
        default=20,
        get=get_prop("animation_range_high"),
        set=set_prop("animation_range_high"),
        description="This value of the recorded variable (e.g. Vm) will map to the"
                    " highest brightness and to the rightmost color (1.0 position) of the "
                    "color ramp above"
    )

    simplification_epsilon = FloatProperty(
        default=0.1,
        min=0,
        get=get_prop("simplification_epsilon"),
        set=set_prop("simplification_epsilon"),
        description="Co-llinearity deviations of this amount will be"
                    " simplified to the nearest line segment. Units are same as the"
                    " units of the recording variable (e.g. mV for 'v'). 0 will remove"
                    " only completely co-linear activity points (e.g. lossless)"
    )

    frames_per_ms = FloatProperty(
        default=1,
        min=0,
        get=get_prop("frames_per_ms"),
        set=set_prop("frames_per_ms"),
        description="The number of Blender frames to use to represent 1 ms of NEURON "
                    "activity"
    )

    gran2int = {
        "Group": 3,
        "Cell": 2,
        "Section": 1,
        "3D Segment": 0
    }

    int2gran = dict(reversed(item) for item in gran2int.items())

    def get_gran_prop(prop):
        def get(self):
            return self.gran2int[getattr(self.node_group, prop)]
        return get

    def set_gran_prop(prop):
        def set(self, value):
            setattr(self.node_group, prop, self.int2gran[value])
        return set

    '''
    ('Group', 'Cell Group', 'Coarsest. Reports the mean value across all selected cell somas (root segments)', 3),
    ('3D Segment', '3D Segment', 'Finest. Reports values between each cell section 3D point', 0),    
    '''
    recording_granularity = bpy.props.EnumProperty(
        items=[
            ('Cell', 'Soma', 'Reports the value at each selected cell soma (root)', 2),
            ('Section', 'Section', 'Reports values at each selected cell section', 1),
        ],
        name="Recording granularity",
        description="The granularity used to record from selected cells. Finest recording "
                    "granularity requires more time and memory, coarsest less so",
        default='Cell',
        get=get_gran_prop("recording_granularity"),
        set=set_gran_prop("recording_granularity")
    )

    '''
    ('Group', 'Cell Group', 'Coarsest. The group of selected cells is represented as '
                            'one object in Blender', 3),
    '''
    interaction_granularity = bpy.props.EnumProperty(
        items=[
           ('Cell', 'Cell', 'Each cell is represented as a Blender object', 2),
            ('Section', 'Section', 'Finest. Each cell section is represented as a Blender object', 1),
        ],
        name="Interaction granularity",
        description="The granularity used to represent selected cells in Blender. "
                    "Finer granularity allows interaction with smaller parts of cells, "
                    "but can result in performance issues if the number of cells/sections "
                    "is large. Coarser interactivity increases performance for larger models",
        default='Cell',
        get=get_gran_prop("interaction_granularity"),
        set=set_gran_prop("interaction_granularity")
    )

    layer_confiner_settings = PointerProperty(
        type=LayerConfinerProperties
    )

    default_brightness = FloatProperty(
        get=get_prop("default_brightness"),
        set=set_prop("default_brightness"),
        description='The initial brightness of all sections in the group'
    )

    smooth_sections = BoolProperty(
        default=True,
        description="Whether to render sections as smooth bezier curves, instead of straight lines. "
                    "True results in more visually appealing morphology, but requires more polygons",
        get=get_prop("smooth_sections"),
        set=set_prop("smooth_sections")
    )


    spherize_soma_if_DeqL = BoolProperty(
        default=True,
        description="Whether to display a soma section with diameter ~= length as a sphere in Blender",
        get=get_prop("spherize_soma_if_DeqL"),
        set=set_prop("spherize_soma_if_DeqL")
    )


    as_lines = BoolProperty(
        default=False,
        description="Whether to display sections as line segments (no radius). This is fast, but does not show "
                    "up in rendered images",
        get=get_prop("as_lines"),
        set=set_prop("as_lines")
    )

    segment_subdivisions = IntProperty(
        min=1,
        max=10,
        description="Number of linear subdivisions to use when displaying a 3D point segment. Higher results in "
                    "smoother section curvature, but requires more polygons",
        get=get_prop("segment_subdivisions"),
        set=set_prop("segment_subdivisions")
    )


    circular_subdivisions = IntProperty(
        min=4,
        max=12,
        description="Number of sides to use when creating circular section cross-sections. "
                    "Only even values are allowed. Higher values use more polygons",
        get=get_prop("circular_subdivisions"),
        set=set_prop("circular_subdivisions")
    )

    def copy_from(self, source_group):

        self.interaction_granularity = source_group.interaction_granularity

        self.as_lines = source_group.as_lines
        self.node_group.color_ramp_material.diffuse_ramp.elements[0].color = \
            source_group.node_group.color_ramp_material.diffuse_ramp.elements[0].color
        self.default_brightness = source_group.default_brightness
        self.smooth_sections = source_group.smooth_sections
        self.segment_subdivisions = source_group.segment_subdivisions
        self.circular_subdivisions = source_group.circular_subdivisions
        self.spherize_soma_if_DeqL = source_group.spherize_soma_if_DeqL

        self.record_activity = source_group.record_activity
        self.recording_granularity = source_group.recording_granularity
        self.record_variable = source_group.record_variable
        self.recording_period = source_group.recording_period
        self.recording_time_start = source_group.recording_time_start
        self.recording_time_end = source_group.recording_time_end
        self.frames_per_ms = source_group.frames_per_ms
        self.simplification_epsilon = source_group.simplification_epsilon
        self.animate_brightness = source_group.animate_brightness
        self.animate_color = source_group.animate_color
        self.animation_range_low = source_group.animation_range_low
        self.animation_range_high = source_group.animation_range_high

        self.import_synapses = source_group.import_synapses




class SimulatorSettings(BlenderNodeClass, PropertyGroup):

    def to_neuron(self, context=None):
        self.client.set_sim_params({
            "tstop": self.neuron_tstop,
            "dt": self.time_step,
            "atol": self.abs_tolerance,
            "celsius": self.temperature,
            "cvode": self.integration_method,
        })

    def from_neuron(self):
        client = self.client

        if client is None:
            return

        params = client.get_sim_params()

        self.neuron_t = params["t"]
        self.neuron_tstop = params["tstop"]
        self.time_step = params["dt"]
        self.abs_tolerance = params["atol"]
        self.temperature = params["celsius"]
        self.integration_method = str(int(float(params["cvode"])))

    neuron_t = FloatProperty(
        description="The current simulation time (e.g. h.t) in ms"
    )

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
                    "rates. Fixed step tends to be faster for networks and high firing rates",
        default='1',
        update=to_neuron
    )


class BlenderNEURONProperties(PropertyGroup):

    @property
    def group(self):
        """
        :return: The currently highlighted UI group
        """
        return self.groups[self.groups_index]

    @property
    def synapse_set(self):
        if len(self.synapse_sets) > self.synapse_sets_index:
            return self.synapse_sets[self.synapse_sets_index]
        else:
            return None



    def clear(self):
        self.property_unset("groups")
        self.property_unset("groups_index")
        self.property_unset("simulator_settings")
        self.property_unset("synapse_sets")
        self.property_unset("synapse_sets_index")

    groups_index = IntProperty()

    groups = CollectionProperty(
        type=RootGroupProperties
    )

    simulator_settings = PointerProperty(
        type=SimulatorSettings
    )

    synapse_sets_index = IntProperty()

    synapse_sets = CollectionProperty(
        type=SynapseConnectorProperties
    )


def register():
    bpy.types.Scene.BlenderNEURON = PointerProperty(type=BlenderNEURONProperties)


def unregister():
    del bpy.types.Scene.BlenderNEURON