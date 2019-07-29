from blenderneuron.blender.views.objectview import ObjectViewAbstract
import bpy


class SectionObjectView(ObjectViewAbstract):
    def show(self):
        if self.group.recording_granularity != "Section":
            raise NotImplementedError()

        for root in self.group.roots.values():
            self.create_container_for_each_section(root)

        self.link_containers()

        self.parent_containers()

    def parent_containers(self):
        """
        Create parent-child relationship between section-child_section blender objects. This
        function can only be called if the parent and child containers have been linked to the
        scene.
        """

        for root in self.group.roots.values():
            self.set_childrens_parent(root)

    def set_childrens_parent(self, parent_sec, recursive=True):
        if parent_sec.was_split:
            # Parent the split sections together
            for i, split_sec in enumerate(parent_sec.split_sections[:-1]):
                start_cont = self.containers[split_sec.hash]
                end_cont = self.containers[parent_sec.split_sections[i+1].hash]
                end_cont.set_parent_object(start_cont)

            # The parent container will be the last split section
            parent_cont = self.containers[parent_sec.split_sections[-1].hash]

        else:
            parent_cont = self.containers[parent_sec.hash]

        for child_sec in parent_sec.children:
            if child_sec.was_split:
                child_cont = self.containers[child_sec.split_sections[0].hash]
            else:
                child_cont = self.containers[child_sec.hash]

            child_cont.set_parent_object(parent_cont)

            del child_cont

        del parent_cont

        if recursive:
            for child_sec in parent_sec.children:
                self.set_childrens_parent(child_sec)

    def create_container_for_each_section(self, root, recursive=True, is_top_level=True):
        if is_top_level:
            origin_type = "center"
        else:
            origin_type = "first"

        self.create_section_container(root, include_children=False, origin_type=origin_type)

        if recursive:
            for child in root.children:
                self.create_container_for_each_section(child, recursive=True, is_top_level=False)

    def update_group(self):
        for root in self.group.roots.values():
            self.update_each_container_section(root)

    def update_each_container_section(self, section):
        if section.was_split:
            # Update split sections with the split container coords
            for split_sec in section.split_sections:
                container = self.containers.get(split_sec.hash)

                if container is not None:
                    container.update_group_section(section, recursive=False)

            # Update the coords of the unsplit section with the coords from the splits
            section.update_coords_from_split_sections()

        else:
            container = self.containers.get(section.hash)

            if container is not None:
                container.update_group_section(section, recursive=False)

        for child_sec in section.children:
            self.update_each_container_section(child_sec)