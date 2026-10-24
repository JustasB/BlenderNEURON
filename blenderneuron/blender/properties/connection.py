import bpy, os, json, inspect, blenderneuron

class BlenderNEURONProperties(bpy.types.PropertyGroup):
    config_cache_valid = False

    connection_advanced_open: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})
    connection_message: bpy.props.StringProperty(options={'SKIP_SAVE'})

    pairing_secret_invalid: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    def get_fixed_listen_port(self):
        return bool(self.server_port)

    def set_fixed_listen_port(self, enabled):
        if enabled:
            if not self.server_port:
                node = getattr(bpy.types.Object, 'BlenderNEURON_node', None)
                self.server_port = str(node.server_port) if node is not None and node.server_port else '8000'
        else:
            self.server_port = ''

    fixed_listen_port: bpy.props.BoolProperty(
        name='Use a fixed listening port',
        description='Keep a predictable Blender port for SSH tunnels or container callbacks',
        get=get_fixed_listen_port, set=set_fixed_listen_port)

    def get_pairing_secret(self):
        from blenderneuron import connection
        return connection.load('Blender-manual.json', {}).get('secret', '')

    def set_pairing_secret(self, value):
        from blenderneuron import connection
        value = value.strip()
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            self.pairing_secret_invalid = True
            self.connection_message = 'Pairing secret must contain 64 lowercase hexadecimal characters.'
            return
        settings = connection.load('Blender-manual.json', {})
        settings.update(mode='manual', secret=value)
        connection.save('Blender-manual.json', settings)
        current = connection.load('Blender-connection.json', {'mode': 'local'})
        if current['mode'] == 'manual':
            current['secret'] = value
            connection.save('Blender-connection.json', current)
            node = getattr(bpy.types.Object, 'BlenderNEURON_node', None)
            if node is not None:
                node.connection_settings = current
                node.secret = value
                node.client = None
                node.client_address = None
        self.pairing_secret_invalid = False
        self.connection_message = 'Pairing secret saved privately on this computer.'

    pairing_secret: bpy.props.StringProperty(
        name='Pairing secret', subtype='PASSWORD', options={'SKIP_SAVE'},
        get=get_pairing_secret, set=set_pairing_secret,
        description='The 64-character secret from NEURON connection information; saved privately outside the blend file')

    def get_connection_mode(self):
        from blenderneuron import connection
        return 1 if connection.load('Blender-connection.json', {'mode': 'local'})['mode'] == 'manual' else 0

    def set_connection_mode(self, value):
        from blenderneuron import connection
        mode = 'manual' if value == 1 else 'local'
        node = getattr(bpy.types.Object, 'BlenderNEURON_node', None)
        if node is not None:
            node.configure_connection(mode=mode)
        else:
            settings = connection.load('Blender-manual.json', {}) if mode == 'manual' else {}
            settings.update(mode=mode)
            if mode == 'manual':
                settings.setdefault('secret', connection.local_secret())
            connection.save('Blender-connection.json', settings)
        self.connection_message = ''

    connection_mode: bpy.props.EnumProperty(
        items=[('LOCAL', 'On this computer', 'Automatically discover local NEURON'),
               ('MANUAL', 'In Docker or on another computer', 'Pair with a remote or container NEURON')],
        get=get_connection_mode, set=set_connection_mode)

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

        from blenderneuron import connection
        if prop_path.startswith(('default_ip|', 'default_port|')):
            if prop_path.startswith('default_port|') and value and (not value.isdigit() or not 1 <= int(value) <= 65535):
                raise ValueError('Port must be between 1 and 65535, or blank')
            values = connection.load('endpoint-settings.json', {})
            values[prop_path] = value
            connection.save('endpoint-settings.json', values)
            settings = connection.load('Blender-connection.json', {'mode': 'local'})
            if settings['mode'] == 'manual':
                from urllib.parse import urlparse
                if prop_path == 'default_ip|Blender':
                    settings['listen_host'] = value
                elif prop_path == 'default_port|Blender':
                    settings['listen_port'] = value
                else:
                    peer = urlparse(settings.get('peer_address', ''))
                    host = value if prop_path == 'default_ip|NEURON' else (peer.hostname or '127.0.0.1')
                    port = value if prop_path == 'default_port|NEURON' else str(peer.port or '')
                    settings['peer_address'] = 'http://' + host + ':' + port if port else ''
                connection.save('Blender-connection.json', settings)
                connection.save('Blender-manual.json', settings)
                node = getattr(bpy.types.Object, 'BlenderNEURON_node', None)
                if node is not None:
                    node.connection_settings = settings
            return
        current = self.config
        for prop in prop_path.split('|')[0:-1]:
            current = current[prop]
        current[prop_path.split('|')[-1]] = value

        self.save_config()

    def get_config_prop(self, prop_path):
        self.load_config()
        from blenderneuron import connection
        settings = connection.load('Blender-connection.json', {'mode': 'local'})
        if settings['mode'] == 'manual':
            from urllib.parse import urlparse
            if prop_path == 'default_ip|Blender':
                return settings.get('listen_host', '127.0.0.1')
            if prop_path == 'default_port|Blender':
                return settings.get('listen_port', '')
            peer = urlparse(settings.get('peer_address', ''))
            if prop_path == 'default_ip|NEURON':
                return peer.hostname or '127.0.0.1'
            if prop_path == 'default_port|NEURON':
                return str(peer.port or '')
        values = connection.load('endpoint-settings.json', {})
        if prop_path in values:
            return values[prop_path]


        current = self.config
        for prop in prop_path.split('|'):
            current = current[prop]

        return current

    # -------------------------------------------------- #

    def client_ip_set(self, value):
        self.set_config_prop("default_ip|NEURON", value)

    def client_ip_get(self):
        return self.get_config_prop("default_ip|NEURON")

    client_ip: bpy.props.StringProperty(
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

    client_port: bpy.props.StringProperty(
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

    server_ip: bpy.props.StringProperty(
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

    server_port: bpy.props.StringProperty(
        name="Port",
        description="The port of the Blender node server. Leave blank to find a free one",
        get=server_port_get, set=server_port_set
    )

    # -------------------------------------------------- #

    def neuron_launch_command_set(self, value):
        self.set_config_prop("NEURON_launch_command", value)

    def neuron_launch_command_get(self):
        return self.get_config_prop("NEURON_launch_command")

    neuron_launch_command: bpy.props.StringProperty(
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

    neuron_last_command: bpy.props.StringProperty(
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

    frames_per_ms: bpy.props.StringProperty(
        name="Frames per ms",
        description="The number of Blender frames to represent one NEURON millisecond",
        get=frames_per_ms_get, set=frames_per_ms_set
    )


def register():
    # Load config properties
    bpy.types.Scene.BlenderNEURON_properties = \
        bpy.props.PointerProperty(type=BlenderNEURONProperties)

def unregister():
    if hasattr(bpy.types.Scene, "BlenderNEURON_properties"):
        del bpy.types.Scene.BlenderNEURON_properties
