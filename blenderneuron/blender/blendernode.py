import bpy

from blenderneuron.blender.blenderroot import BlenderRoot
from blenderneuron.blender.blenderrootgroup import *
from blenderneuron.commnode import CommNode


class BlenderNode(CommNode):
    def __init__(self, *args, **kwargs):
        super(BlenderNode, self).__init__("Blender", *args, **kwargs)

    @property
    def ui_properties(self):
        return bpy.data.scenes[0].BlenderNEURON

    def add_group(self, name=None, include_groupless_roots=True):
        self.update_root_index()

        if name is None:
            name = self.find_unique_group_name()

        group = BlenderRootGroup(name, self)

        # Attach group to node
        self.groups[name] = group

        # Add group to the UI list
        group.add_to_UI()

        if include_groupless_roots:
            group.add_groupless_roots()

        return group

    def update_root_index(self):
        # Keep track which roots have been removed from NRN
        roots_to_delete = set(self.root_index.keys())

        # Get the list of root sections from NEURON
        try:
            root_data = self.client.get_roots()

            # Update new or existing root entries
            for i, root_info in enumerate(root_data):
                name = root_info["name"]

                existing_root = self.root_index.get(name)

                # Update existing root
                if existing_root is not None:
                    existing_root.index = root_info["index"]
                    existing_root.name = root_info["name"]

                    # Don't remove roots that previously existed and are present
                    roots_to_delete.remove(name)

                # Add a new root
                else:
                    new_root = self.root_index[name] = BlenderRoot(
                        root_info["index"],
                        root_info["name"]
                    )

                    # Make sure it's listed as selectable in all groups
                    for group in self.groups.values():
                        new_root.add_to_UI_group(group.ui_group)

        except ConnectionRefusedError:
            root_data = []

        finally:
            # Delete removed roots
            for name_to_delete in roots_to_delete:
                self.root_index[name_to_delete].remove(node=self)

    def find_unique_group_name(self):
        i_name = len(self.groups.values())

        while True:
            name = "Group." + str(i_name).zfill(3)

            if name in self.groups:
                i_name += 1
            else:
                break

        return name

    def get_group_data_from_neuron(self, group_list):

        # Convert blender groups to skeletal dicts (needed for XML rcp with NRN)
        # These dicts contain basic information (e.g. no 3D data, activity)
        blender_groups = self.get_group_dicts(group_list)

        # Send a request to NRN for the selected groups
        compressed = self.client.initialize_groups(blender_groups)

        # Decompress the result
        nrn_groups = self.decompress(compressed)

        return nrn_groups

    def import_groups_from_neuron(self, group_list):

        nrn_groups = self.get_group_data_from_neuron(group_list)

        # Update each blender node group with the data received from NRN
        for nrn_group in nrn_groups:
            node_group = self.groups[nrn_group["name"]]

            print('Importing group: ' + node_group.name + ' from NEURON...')

            # Remove any views of the cells
            if node_group.view is not None:
                node_group.view.remove()
                node_group.view = None

            # Update blender node group with the data received from NRN
            node_group.from_full_NEURON_group(nrn_group)

    def get_selected_groups(self):
        return [group for group in self.groups.values() if group.selected]

    def get_group_dicts(self, group_list):
        return [group.to_dict() for group in group_list]


    @property
    def synapse_sets(self):
        return bpy.context.scene.BlenderNEURON.synapse_sets

    def add_synapse_set(self, name=None):
        new_set = self.synapse_sets.add()

        if name is None:
            i_name = len(self.synapse_sets.values())

            while True:
                name = "SynapseSet." + str(i_name).zfill(3)

                if name in self.synapse_sets.keys():
                    i_name += 1
                else:
                    break

        new_set.name = name

        return new_set

    def display_groups(self):
        for group in self.groups.values():

            if group.selected:
                print('Showing group ' + group.name + ' in Blender')
                group.show()

            else:
                group.remove_view()


    def add_neon_effect(self):
        """
        Adds glare filter to the compositing node tree

        :return:
        """
        scene = bpy.context.scene
        scene.use_nodes = True

        links = scene.node_tree.links
        nodes = scene.node_tree.nodes

        layers = nodes.get('Render Layers')

        if layers is None:
            layers = nodes.new('CompositorNodeRLayers')

        glare = nodes.new('CompositorNodeGlare')

        composite = nodes.get('Composite')

        if composite is None:
            composite = nodes.new('CompositorNodeComposite')

        links.new(layers.outputs['Image'], glare.inputs['Image'])
        links.new(glare.outputs['Image'], composite.inputs['Image'])

        glare.quality = 'MEDIUM'
        glare.iterations = 3
        glare.color_modulation = 0.2
        glare.threshold = 0.1
        glare.streaks = 7
        glare.fade = 0.75
