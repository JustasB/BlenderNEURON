from blenderneuron.blender.views.objectview import ObjectViewAbstract
import bpy
from blenderneuron.blender.views.curvecontainer import CurveContainer

class SectionObjectView(ObjectViewAbstract):
    def show(self):

        if self.group.recording_granularity not in ["Section", "Cell"]:
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
                recursive=self.group.recording_granularity == 'Section'
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
        # If the parent was split, the split sections need to be chained together first
        # Then, the split section that is closest to the child will be the child's container's parent
        if parent_sec.was_split:

            # Parent chain the split sections together
            for i, split_sec in enumerate(parent_sec.split_sections[:-1]):
                start_cont = self.containers[split_sec.name]
                end_cont = self.containers[parent_sec.split_sections[i+1].name]
                end_cont.set_parent_object(start_cont)

            for child_sec in parent_sec.children:

                # Get the child container
                # If the child was split, child's first split section container will be the child
                if child_sec.was_split:
                    child_cont = self.containers[child_sec.split_sections[0].name]

                # Otherwise child's normal container will be child
                else:
                    child_cont = self.containers[child_sec.name]

                # When the parent was split, find the split section that's closest to the child
                closest_split, _ = self.get_closest_split_section(
                    parent_sec.split_sections,
                    child_sec.coords[0:3]
                )

                # it will become the child section container's parent container
                parent_cont = self.containers[closest_split.name]

                # Set the relationship between the containers
                child_cont.set_parent_object(parent_cont)

                del child_cont, parent_cont

        # If the parent was not split, then the parent container is its normal container
        else:
            parent_cont = self.containers[parent_sec.name]

            for child_sec in parent_sec.children:

                # Get the child container
                # If the child was split, child's first split section container will be the child
                if child_sec.was_split:
                    try:
                        child_cont = self.containers[child_sec.split_sections[0].name]
                    except:
                        raise

                # Otherwise child's normal container will be child
                else:
                    child_cont = self.containers[child_sec.name]

                # Set the relationship between the containers
                child_cont.set_parent_object(parent_cont)

                del child_cont

            # Cleanup before recursing
            del parent_cont

        if recursive:
            for child_sec in parent_sec.children:
                self.set_childrens_parent(child_sec)

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

    def create_container_for_each_section(self, root, recursive=True, is_top_level=True, material = None):
        if is_top_level:
            origin_type = "center"
        else:
            origin_type = "first"

        self.create_section_container(root, include_children=False,
                                      origin_type=origin_type,
                                      container_material=material)

        if recursive:
            for child in root.children:
                self.create_container_for_each_section(child,
                                                       recursive=True,
                                                       is_top_level=False,
                                                       material=material)

    def update_group(self):
        for root in self.group.roots.values():
            self.update_each_container_section(root)

    def update_each_container_section(self, section):
        if section.was_split:

            # Update split sections with the split container coords
            for split_sec in section.split_sections:
                container = self.containers.get(split_sec.name)

                if container is not None:
                    container.update_group_section(split_sec, recursive=False)

            # Update the coords of the unsplit section with the coords from the splits
            section.update_coords_from_split_sections()

        else:
            container = self.containers.get(section.name)

            if container is not None:
                container.update_group_section(section, recursive=False)

        for child_sec in section.children:
            self.update_each_container_section(child_sec)