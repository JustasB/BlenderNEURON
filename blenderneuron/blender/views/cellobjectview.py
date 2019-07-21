from blenderneuron.blender.views.objectview import ObjectViewAbstract


class CellObjectView(ObjectViewAbstract):

    def show(self):
        if self.group.recording_granularity != "Section":
            raise NotImplementedError()

        for root in self.group.roots.values():
            self.create_section_container(root, include_children=True, origin_type="center")

        self.link_containers()

    def update_group(self):
        for root in self.group.roots.values():
            self.containers[root.hash].update_group_section(root, recursive=True)