from blenderneuron.blender.views.sectionobjectview import SectionObjectView
import bpy, math
import numpy as np

class PhysicsMeshSectionObjectView(SectionObjectView):
    def __init__(self, group):
        super(PhysicsMeshSectionObjectView, self).__init__(group)

        # Disable any inter-point smoothing
        self.curve_template.resolution_u = 1

        # Disable bevel (line segments only)
        self.curve_template.bevel_depth = 0

        # Don't add the extra end caps
        self.closed_ends = False

        self.tip_template = self.create_tip_template()

    def create_tip_template(self):
        mesh = bpy.data.meshes.new('TipTemplateMesh')

        # Add 1 point at the (local) origin
        mesh.vertices.add(1)

        object = bpy.data.objects.new('TipTemplate', mesh)

        return object

    def show(self):
        self.split_long_sections()

        super(PhysicsMeshSectionObjectView, self).show()

        self.containers_to_mesh()

        self.make_containers_rigid_bodies()

        self.add_branch_joints()

        self.add_branch_tips()

        self.add_force_to_layer()

        self.setup_physics_sim()


    def align(self):
        bpy.ops.screen.animation_play()

    def add_force_to_layer(self):
        layer = self.group.ui_group.layer_aligner_settings.layer_mesh
        field = layer.field

        # Enable forcefield
        field.type = 'HARMONIC'
        field.shape = 'SURFACE'
        field.strength = 50.0
        field.harmonic_damping = 0.5
        field.rest_length = 1.0

    def setup_physics_sim(self):

        frames = self.group.ui_group.layer_aligner_settings.simulation_frames

        # Disable gravity
        bpy.context.scene.use_gravity = False

        bpy.context.scene.rigidbody_world.point_cache.frame_start = 1
        bpy.context.scene.rigidbody_world.point_cache.frame_end = frames

        if bpy.context.scene.frame_end < frames:
            bpy.context.scene.frame_end = frames

    def make_containers_rigid_bodies(self):

        mov_pattern = self.group.ui_group.layer_aligner_settings.moveable_sections_pattern

        # Make the sections matching pattern move in response to forces
        self.select_containers(pattern=mov_pattern)
        bpy.ops.rigidbody.objects_add(type='ACTIVE')

        # Make all other sections remain fixed
        self.select_containers(pattern=mov_pattern, pattern_inverse=True)
        bpy.ops.rigidbody.objects_add(type='PASSIVE')

    def add_branch_tips(self):
        # Recursively add dummy meshes at the end of branch tips
        for root in self.group.roots.values():
            self.add_branch_tip_mesh(root)

    def add_branch_tip_mesh(self, root):

        if not any(root.children):
            root_cont = self.containers[root.hash]
            root_cont.add_tip(self.tip_template)
            del root_cont

        # Recursively create the tip meshes for leaf sections
        for child in root.children:
            self.add_branch_tip_mesh(child)


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

        bpy.data.objects.remove(self.tip_template)


    def split_long_sections(self):
        for root in self.group.roots.values():
            self.split_long_section(root)

    def split_long_section(self, root):
        last_split = root.split_long()

        # Skip ahead to the last split section
        if last_split is not None:
            root = last_split

        for child_sec in root.children:
            self.split_long_section(child_sec)
