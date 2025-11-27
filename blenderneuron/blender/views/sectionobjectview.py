from blenderneuron.blender.views.objectview import ObjectViewAbstract
import bpy
from blenderneuron.blender.views.curvecontainer import CurveContainer

class SectionObjectView(ObjectViewAbstract):
    def show(self):

        if self.group.recording_granularity not in ["Section", "Cell", "3D Segment"]:
            raise NotImplementedError(self.group.recording_granularity)

        color = self.group.default_color
        brightness = self.group.default_brightness

        total = len(self.group.roots.values())
        for ri, root in enumerate(self.group.roots.values()):
            print('Showing cell ' + root.name + ' %s out of %s' % (ri+1, total))

            # Create one material for the whole cell
            if self.group.recording_granularity == 'Cell':
                material = CurveContainer.create_material(root.name, color, brightness)

            # Let each container create their own material
            else:
                material = None

            self.create_container_for_each_section(root, material=material)

            # Animate section activity
            self.animate_section_material(
                root,
                recursive=self.group.recording_granularity in ('Section', '3D Segment')
            )

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

            # Lock scaling the parent (rotations and translations are allowed)
            container_name = root.split_sections[0].name if root.was_split else root.name
            self.containers[container_name].get_object().lock_scale = [True] * 3

    def set_childrens_parent(self, parent_sec, recursive=True):
        """
        Iteratively sets the Blender parent-child relationships between containers based on the section hierarchy.

        :param parent_sec: The parent section whose children will have their parent containers set.
        :param recursive: Whether to process child sections recursively.
        :return: None
        """

        # If the parent was split, the split sections need to be chained together first
        if parent_sec.was_split:
            # Parent chain the split sections together
            for i, split_sec in enumerate(parent_sec.split_sections[:-1]):
                start_cont = self.containers[split_sec.name]
                end_cont = self.containers[parent_sec.split_sections[i + 1].name]
                end_cont.set_parent_object(start_cont)

        # Stack entries will be tuples: (current_sec, parent_sec)
        stack = [(child_sec, parent_sec) for child_sec in parent_sec.children]

        while stack:
            current_sec, current_parent_sec = stack.pop()

            # Determine parent container for current section
            if current_parent_sec.was_split:
                # When the parent was split, find the split section that's closest to the child
                closest_split, _ = self.get_closest_split_section(
                    current_parent_sec.split_sections,
                    current_sec.coords[0:3]
                )
                # It will become the child section container's parent container
                parent_cont = self.containers[closest_split.name]
            else:
                # If the parent was not split, then the parent container is its normal container
                parent_cont = self.containers[current_parent_sec.name]

            # Get the child container
            # If the child was split, child's first split section container will be the child
            if current_sec.was_split:
                child_cont = self.containers[current_sec.split_sections[0].name]

                # Chain the split sections together for current_sec
                for i, split_sec in enumerate(current_sec.split_sections[:-1]):
                    start_cont = self.containers[split_sec.name]
                    end_cont = self.containers[current_sec.split_sections[i + 1].name]
                    end_cont.set_parent_object(start_cont)
            else:
                # Otherwise child's normal container will be child
                child_cont = self.containers[current_sec.name]

            # Set the relationship between the containers
            child_cont.set_parent_object(parent_cont)

            del child_cont
            del parent_cont  # Cleanup before processing next section

            if recursive:
                # Add the children of the current section to the stack
                for child_sec in current_sec.children:
                    stack.append((child_sec, current_sec))

    def get_closest_split_section(self, split_sections, coord):
        closest_sec = split_sections[0]
        min_dist = closest_sec.dist_to_closest_coord(coord)

        for split_sec in split_sections[1:]:
            dist = split_sec.dist_to_closest_coord(coord)

            if dist < min_dist:
                closest_sec = split_sec
                min_dist = dist

                if min_dist == 0:
                    break

        return closest_sec, min_dist

    def create_container_for_each_section(self, root, recursive=True, is_top_level=True, material=None):
        """
        Iteratively creates a container for each section starting from the root section.

        :param root: The root section to start creating containers from.
        :param recursive: Whether to process child sections recursively.
        :param is_top_level: Indicates if the root is the top-level section.
        :param material: The material to use for the containers.
        :return: None
        """
        stack = [(root, is_top_level)]
        while stack:
            current_section, current_is_top_level = stack.pop()

            if current_is_top_level:
                origin_type = "center"
            else:
                origin_type = "first"

            self.create_section_container(
                current_section,
                include_children=False,
                origin_type=origin_type,
                container_material=material
            )

            if recursive:
                # Add child sections to the stack to process them iteratively
                # Reverse the children to maintain traversal order
                for child in reversed(current_section.children):
                    stack.append((child, False))

    def update_group_with_view_data(self):
        for root in self.group.roots.values():
            self.update_each_container_section_with_view_data(root)

    def update_each_container_section_with_view_data(self, section):
        """
        Iteratively updates each container BlenderSection section with 3d data from Blender Curve objects.
        If a section was split, it updates the split sections with the
        split container coordinates and then updates the original section's coordinates from the splits. Otherwise,
        it updates the section directly.

        :param section: The root section to start the update from
        """

        stack = [section]
        while stack:
            current_section = stack.pop()
            if current_section.was_split:

                # Update split sections with the split container coords
                for split_sec in current_section.split_sections:
                    container = self.containers.get(split_sec.name)

                    if container is not None:
                        container.update_group_section_with_view_data(split_sec, recursive=False)

                # Update the coords of the unsplit section with the coords from the splits
                current_section.update_coords_from_split_section_views()

            else:
                container = self.containers.get(current_section.name)

                if container is not None:
                    container.update_group_section_with_view_data(current_section, recursive=False)

            # Add child sections to the stack to process them iteratively
            stack.extend(current_section.children)
