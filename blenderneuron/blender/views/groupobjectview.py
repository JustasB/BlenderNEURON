"""Display a forest of cells as a single curve object."""
from blenderneuron.blender.views.cellobjectview import CellObjectView
from blenderneuron.blender.views.curvecontainer import CurveContainer


class GroupObjectView(CellObjectView):
    def show(self):
        if self.group.recording_granularity not in ('Cell', 'Section', '3D Segment'):
            raise NotImplementedError(self.group.recording_granularity)
        self.reserve_import(group_view=True)
        roots = list(self.group.roots.values())
        if roots:
            root_materials = {}
            if self.group.recording_granularity == 'Cell':
                root_materials = {
                    root.name: CurveContainer.create_material(
                        root.name, self.group.default_color, self.group.default_brightness,
                        self.registry, self.identity_scope)
                    for root in roots
                }
            container = CurveContainer(
                roots[0], self.curve_template, self.group.smooth_sections,
                self.group.default_color, self.group.default_brightness,
                self.group.recording_granularity, closed_ends=self.closed_ends,
                material_template=self.material_template, registry=self.registry,
                identity_scope=self.identity_scope, roots=roots,
                container_name=self.group.name, root_materials=root_materials,
            )
            self.containers[container.name] = container
            self.materials.update(container.materials)
            for root in roots:
                self.animate_section_material(
                    root, recursive=self.group.recording_granularity != 'Cell')
        self.link_containers()

    def update_group_with_view_data(self):
        container = self.containers.get(self.group.name)
        if container is not None:
            for root in self.group.roots.values():
                container.update_group_section_with_view_data(root, recursive=True)
