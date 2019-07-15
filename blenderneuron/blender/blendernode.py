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


    def add_group(self):
        self.update_root_index()

        name = self.find_unique_group_name()

        group = BlenderRootGroup(name, self)

        # Attach group to node
        self.groups[name] = group

        # Add group to the UI list
        group.add_to_UI()

        group.add_groupless_roots()

    def update_root_index(self):

        # Get the list of root sections from NEURON
        root_data = self.client.get_roots()

        # Keep track which roots have been removed from NRN
        roots_to_delete = set(self.root_index.keys())

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

