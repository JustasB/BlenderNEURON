from blenderneuron.blender.views.sectionobjectview import SectionObjectView
import bpy

class PhysicsMeshSectionObjectView(SectionObjectView):
    def __init__(self, group):
        super(PhysicsMeshSectionObjectView, self).__init__(group)

        # Disable any inter-point smoothing
        self.curve_template.resolution_u = 1

        # Disable bevel (line segments only)
        self.curve_template.bevel_depth = 0

        # Don't add the extra end caps
        self.closed_ends = False

    def show(self):
        super(PhysicsMeshSectionObjectView, self).show()

        self.containers_to_mesh()

        self.make_containers_rigid_bodies()

        self.add_branch_joints()

        self.run_physics_sim()

    def run_physics_sim(self):

        frames = self.group.ui_group.layer_aligner_settings.simulation_frames

        bpy.context.scene.rigidbody_world.point_cache.frame_start = 1
        bpy.context.scene.rigidbody_world.point_cache.frame_end = frames

        if bpy.context.scene.frame_end < frames:
            bpy.context.scene.frame_end = frames

        bpy.ops.ptcache.bake_all(bake=True)
        bpy.context.scene.frame_set(frames)

    def make_containers_rigid_bodies(self):

        mov_pattern = self.group.ui_group.layer_aligner_settings.moveable_sections_pattern

        # Make the sections matching pattern move in response to forces
        self.select_containers(pattern=mov_pattern)
        bpy.ops.rigidbody.objects_add(type='ACTIVE')

        # Make all other sections remain fixed
        self.select_containers(pattern=mov_pattern, pattern_inverse=True)
        bpy.ops.rigidbody.objects_add(type='PASSIVE')

    def add_branch_joints(self):

        # Recursively add the joints between parent-child sections
        for root in self.group.roots.values():
            self.add_joints_to_children(root)

    def add_joints_to_children(self, root):

        # Create joints between the parent and it's children
        root_cont = self.containers[root.hash]

        for child in root.children:
            child_cont = self.containers[child.hash]
            root_cont.create_joint_with(child_cont)
            del child_cont

        del root_cont

        # Recursively create the joints between the children and their children
        for child in root.children:
            self.add_joints_to_children(child)

    def update_group(self):

        for root in self.group.roots.values():
            self.update_each_container_section(root)

    def update_each_container_section(self, section):
        self.containers[section.hash].update_group_section(section, recursive=False)

        for child_sec in section.children:
            self.update_each_container_section(child_sec)

    def remove(self):
        super(PhysicsMeshSectionObjectView, self).remove()

        bpy.ops.rigidbody.world_remove()

