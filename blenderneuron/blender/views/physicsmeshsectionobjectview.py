from blenderneuron.blender.views.sectionobjectview import SectionObjectView
import bpy, math
import numpy as np
from blenderneuron.blender.utils import create_many_copies

class PhysicsMeshSectionObjectView(SectionObjectView):
    def __init__(self, group):
        super(PhysicsMeshSectionObjectView, self).__init__(group)

        # Disable any inter-point smoothing
        self.curve_template.resolution_u = 1

        # Disable bevel (line segments only)
        # When converted to meshes, they collide and cause instabilities
        self.curve_template.bevel_depth = 0

        # Don't add the extra end caps
        self.closed_ends = False

        self.tip_template = self.create_tip_template()
        self.joint_template = None

    @property
    def max_bend_angle(self):
        return self.group.ui_group.layer_aligner_settings.max_bend_angle

    @property
    def max_section_length(self):
        return self.group.ui_group.layer_aligner_settings.max_section_length

    def show(self):

        # This will create section objects using the new split sections
        for root in self.group.roots.values():
            self.create_container_for_each_section(root)

        self.link_containers()

        self.parent_containers()

        # Physics sim does not work with curves, need meshes
        # The meshes will be single strand meshes without radii
        # This speeds up the simulation and makes it simple to recover the changed coords
        self.containers_to_mesh()

        self.make_containers_rigid_bodies()

        # Joints will allow sections to rotate around the branch point
        self.add_branch_joints()

        # Without explicit tips, the final sections tend to not align well
        self.add_branch_tips()

        self.add_force_to_layer()

        self.setup_physics_sim()

    def create_joint_template(self):
        # This does not work - the copy()s of the template do not seem to
        # copy over constraint data (values do but not behavior)
        # empty = bpy.data.objects.new("JointTemplate", None)  # None creates "Empty"
        #
        # # Add rigid body constraint to the empty - only works when linked to scene
        # bpy.context.scene.objects.link(empty)
        # bpy.context.scene.objects.active = empty
        # bpy.ops.rigidbody.constraint_add()
        #
        # return empty.name

        return "JointTemplate"

    def create_tip_template(self):
        mesh = bpy.data.meshes.new('TipTemplateMesh')

        # Add 1 point at the (local) origin
        mesh.vertices.add(1)

        object = bpy.data.objects.new('TipTemplate', mesh)

        return object.name


    def create_container_for_each_section(self, root, recursive=True, is_top_level=True):
        if is_top_level:
            origin_type = "center"
        else:
            origin_type = "first"

        self.create_section_container(root,
                                      include_children=False,
                                      origin_type=origin_type,
                                      split_longer_than=self.max_section_length)

        if recursive:
            for child in root.children:
                self.create_container_for_each_section(child, recursive=True, is_top_level=False)

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

        settings = self.group.ui_group.layer_aligner_settings

        # Disable gravity
        bpy.context.scene.use_gravity = False

        bpy.context.scene.rigidbody_world.point_cache.frame_start = 1
        bpy.context.scene.rigidbody_world.point_cache.frame_end = settings.simulation_frames


        bpy.context.scene.rigidbody_world.steps_per_second = settings.physics_steps_per_sec
        bpy.context.scene.rigidbody_world.solver_iterations = settings.physics_solver_iterations_per_step

        bpy.context.scene.frame_end = settings.simulation_frames

        bpy.context.scene.frame_set(settings.simulation_frames)

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
        if self.joint_template is None:
            self.joint_template = self.create_joint_template()

        if not any(root.children):
            if root.was_split:
                root_cont = self.containers[root.split_sections[-1].hash]
            else:
                root_cont = self.containers[root.hash]

            root_cont.add_tip(self.tip_template, self.joint_template)
            del root_cont

        # Recursively create the tip meshes for leaf sections
        for child in root.children:
            self.add_branch_tip_mesh(child)


    def add_branch_joints(self):
        if self.joint_template is None:
            self.joint_template = self.create_joint_template()

        # Recursively add the joints between parent-child sections
        for root in self.group.roots.values():
            self.add_joints_to_children(root)

    def add_joints_to_children(self, root):

        # If a long section was split, create joints between the split sections
        if root.was_split:

            for i, split_sec in enumerate(root.split_sections[:-1]):
                start_cont = self.containers[split_sec.hash]
                end_cont = self.containers[root.split_sections[i+1].hash]
                start_cont.create_joint_with(end_cont, self.joint_template, self.max_bend_angle)
                del start_cont, end_cont
            # Then link the last split section with original children
            root_cont = self.containers[root.split_sections[-1].hash]

        else:
            # Create joints between the parent and it's children
            root_cont = self.containers[root.hash]

        for child in root.children:
            # If a child was split, then use the first spit section as child container
            child_hash = (child.split_sections[0] if child.was_split else child).hash

            child_cont = self.containers[child_hash]
            root_cont.create_joint_with(child_cont, self.joint_template, self.max_bend_angle)
            del child_cont

        del root_cont

        # Recursively create the joints between the children and their children
        for child in root.children:
            self.add_joints_to_children(child)

    def remove(self):
        super(PhysicsMeshSectionObjectView, self).remove()

        if bpy.context.scene.rigidbody_world is not None:
            rbw_group = bpy.context.scene.rigidbody_world.group

            if rbw_group is not None:
                bpy.data.groups.remove(rbw_group)

            rbw_constraints = bpy.context.scene.rigidbody_world.constraints

            if rbw_constraints is not None:
                bpy.data.groups.remove(rbw_constraints)

            bpy.ops.rigidbody.world_remove()

        tip_temp = bpy.data.objects[self.tip_template]
        bpy.data.meshes.remove(tip_temp.data)
        bpy.data.objects.remove(tip_temp)

        if self.joint_template is not None:
            tmpl = bpy.data.objects.get(self.joint_template)
            if tmpl:
                bpy.data.objects.remove(tmpl)

        self.remove_split_sections()

    def remove_split_sections(self):
        for root in self.group.roots.values():
            root.remove_split_sections(recursive=True)

