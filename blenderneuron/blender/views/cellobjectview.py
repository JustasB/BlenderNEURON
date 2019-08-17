from blenderneuron.blender.views.curvecontainer import CurveContainer
from blenderneuron.blender.views.objectview import ObjectViewAbstract


class CellObjectView(ObjectViewAbstract):

    def __init__(self, rootgroup, closed_ends=True):
        super(CellObjectView, self).__init__(rootgroup)

        self.closed_ends = closed_ends

    def show(self):
        if self.group.recording_granularity not in ["Section", "Cell"]:
            raise NotImplementedError(self.group.recording_granularity)

        for root in self.group.roots.values():
            # Cell gran: create one material for the whole cell
            if self.group.recording_granularity == 'Cell':
                material = CurveContainer.create_material(root.name)

            # Section gran: let each container create their own material
            else:
                material = None

            self.create_section_container(root,
                                          include_children=True,
                                          origin_type="center",
                                          container_material=material)

        self.link_containers()

    def update_group(self):
        for root in self.group.roots.values():
            container = self.containers.get(root.hash)

            if container is not None:
                container.update_group_section(root, recursive=True)