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
                hash = root_info["hash"]

                existing_root = self.root_index.get(hash)

                # Update existing root
                if existing_root is not None:
                    existing_root.index = root_info["index"]
                    existing_root.name = root_info["name"]

                    # Don't remove roots that previously existed and are present
                    roots_to_delete.remove(hash)

                # Add a new root
                else:
                    self.root_index[hash] = BlenderRoot(
                        root_info["index"],
                        hash,
                        root_info["name"]
                    )
        except ConnectionRefusedError:
            root_data = []

        finally:
            # Delete removed roots
            for hash_to_delete in roots_to_delete:
                self.root_index[hash_to_delete].remove(node=self)

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

