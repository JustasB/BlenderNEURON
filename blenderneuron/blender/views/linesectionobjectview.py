from blenderneuron.blender.views.sectionobjectview import SectionObjectView
import bpy

class LineSectionObjectView(SectionObjectView):
    def __init__(self, group):
        super(LineSectionObjectView, self).__init__(group)

        # Disable any inter-point smoothing
        self.curve_template.resolution_u = 1

        # Disable bevel (line segments only)
        self.curve_template.bevel_depth = 0

        # Don't add the extra end caps
        self.closed_ends = False

    def show(self):
        super(LineSectionObjectView, self).show()

        self.containers_to_mesh()

        import pydevd
        pydevd.settrace('192.168.0.100', port=4200)

        self.make_containers_rigid_bodies()

        self.add_branch_joints()

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

        # # Add the joint objects (empties) to the scene
        # link = bpy.context.scene.objects.link

        # for cont in self.containers.values():
        #     for joint in cont.joints:
        #         link(joint)

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
        pass