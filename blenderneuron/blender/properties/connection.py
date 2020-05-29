import bpy, os, json, inspect, blenderneuron

class BlenderNEURONProperties(bpy.types.PropertyGroup):
    config_cache_valid = False

    def load_config(self):
        package_dir = os.path.dirname(os.path.abspath(inspect.getfile(blenderneuron)))
        config_file = os.path.join(package_dir, 'config.json')

        with open(config_file, "r") as f:
            self.config = json.load(f)[0]

    def save_config(self):
        package_dir = os.path.dirname(os.path.abspath(inspect.getfile(blenderneuron)))
        config_file = os.path.join(package_dir, 'config.json')

        with open(config_file, "w") as f:
            json.dump([self.config], f, indent=4, sort_keys=True)

    def set_config_prop(self, prop_path, value):
        self.load_config()

        current = self.config
        for prop in prop_path.split('|')[0:-1]:
            current = current[prop]
        current[prop_path.split('|')[-1]] = value

        self.save_config()

    def get_config_prop(self, prop_path):
        self.load_config()

        current = self.config
        for prop in prop_path.split('|'):
            current = current[prop]

        return current

    # -------------------------------------------------- #

    def client_ip_set(self, value):
        self.set_config_prop("default_ip|NEURON", value)

    def client_ip_get(self):
        return self.get_config_prop("default_ip|NEURON")

    client_ip = bpy.props.StringProperty(
        name="IP Address",
        description="The IP address of the machine running NEURON. Use 127.0.0.1 when Blender and "
                    "NEURON are on the same machine",
        get=client_ip_get, set=client_ip_set
    )

    # -------------------------------------------------- #

    def client_port_set(self, value):
        self.set_config_prop("default_port|NEURON", value)

    def client_port_get(self):
        return self.get_config_prop("default_port|NEURON")

    client_port = bpy.props.StringProperty(
        name="Port",
        description="The port of the NEURON node server. Leave blank to auto-discover one (on local"
                    " machines only)",
        get=client_port_get, set=client_port_set
    )

    # -------------------------------------------------- #

    def server_ip_set(self, value):
        self.set_config_prop("default_ip|Blender", value)

    def server_ip_get(self):
        return self.get_config_prop("default_ip|Blender")

    server_ip = bpy.props.StringProperty(
        name="Blender IP",
        description="The IP address of the machine running Blender. Use 127.0.0.1 when Blender and "
                    "NEURON are on the same machine",
        get=server_ip_get, set=server_ip_set
    )

    # -------------------------------------------------- #

    def server_port_set(self, value):
        self.set_config_prop("default_port|Blender", value)

    def server_port_get(self):
        return self.get_config_prop("default_port|Blender")

    server_port = bpy.props.StringProperty(
        name="Port",
        description="The port of the Blender node server. Leave blank to find a free one",
        get=server_port_get, set=server_port_set
    )

    # -------------------------------------------------- #

    def neuron_launch_command_set(self, value):
        self.set_config_prop("NEURON_launch_command", value)

    def neuron_launch_command_get(self):
        return self.get_config_prop("NEURON_launch_command")

    neuron_launch_command = bpy.props.StringProperty(
        name="NEURON command",
        description="The command that will be executed to launch NEURON+BlenderNEURON node",
        get=neuron_launch_command_get, set=neuron_launch_command_set
    )

    # -------------------------------------------------- #

    def neuron_last_command_set(self, value):
        self.set_config_prop("NEURON_last_command", value)

    def neuron_last_command_get(self):
        return self.get_config_prop("NEURON_last_command")

    def on_neuron_last_command_updated(self, value):
        bpy.ops.blenderneuron.exec_neuron_command()

    neuron_last_command = bpy.props.StringProperty(
        name="Send command",
        description="A Python command (e.g. 'h.run()' or 'h.load_file(...)')that will be executed in "
                    "NEURON. Printed output can be seen in the Blender console window",
        get=neuron_last_command_get, set=neuron_last_command_set, update=on_neuron_last_command_updated
    )

    # -------------------------------------------------- #

    def frames_per_ms_set(self, value):
        self.set_config_prop("Blender_frames_per_ms", value)

    def frames_per_ms_get(self):
        return self.get_config_prop("Blender_frames_per_ms")

    frames_per_ms = bpy.props.StringProperty(
        name="Frames per ms",
        description="The number of Blender frames to represent one NEURON millisecond",
        get=frames_per_ms_get, set=frames_per_ms_set
    )


def register():
    # Load config properties
    bpy.types.Scene.BlenderNEURON_properties = \
        bpy.props.PointerProperty(type=BlenderNEURONProperties)

def unregister():
    del bpy.types.Scene.BlenderNEURON_properties