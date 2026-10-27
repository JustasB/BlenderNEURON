"""Load an offline snapshot using the same geometry/animation builders as live import."""
import bpy

from blenderneuron.blender.blenderroot import BlenderRoot
from blenderneuron.blender.blenderrootgroup import BlenderRootGroup
from blenderneuron.results import RECORDING_KEYS, read_snapshot, validate_snapshot


def import_simulation_results(node, path):
    """Replace the imported dataset, preserving display settings by group name.

    File validation completes before any existing objects are removed. No
    callback to NEURON is made, even if a live connection happens to exist.
    """
    snapshot = read_snapshot(path)
    return import_simulation_snapshot(node, snapshot, path)


def import_simulation_snapshot(node, snapshot, source, restoring=False):
    from blenderneuron.blender.dataset import store_snapshot
    validate_snapshot(snapshot)
    # Clear the outbound connection before replacing cells; remembered pairing
    # stays in private connection settings and is never copied into the scene.
    node.client = None
    node.client_address = None
    store_snapshot(snapshot, source)
    bpy.context.scene.BlenderNEURON_properties.connection_message = ''
    names = {group['name'] for group in snapshot['groups']}
    for group in list(node.groups.values()):
        if group.view is not None:
            group.view.remove()
            group.view = None
        group.select_roots('None')
        if group.name not in names:
            group.remove()
    node.synapse_sets.clear()
    node.root_index.clear()
    for group in node.groups.values():
        group.ui_group.root_entries.clear()
    for data in snapshot['groups']:
        for root_data in data['roots']:
            name = root_data['name']
            node.root_index[name] = BlenderRoot(len(node.root_index), name)
    for data in snapshot['groups']:
        name = data['name']
        if name not in node.groups:
            group = node.groups[name] = BlenderRootGroup(name, node)
            group.add_to_UI()
        else:
            group = node.groups[name]
            for root in node.root_index.values():
                root.add_to_UI_group(group.ui_group)
        group.selected = data.get('_selected', True) if restoring else True
        group.record_activity = data['record_activity']
        for key in RECORDING_KEYS:
            setattr(group, key, data[key])
        for key, value in data.get('display', {}).items():
            setattr(group, key, value)
        for root in data['roots']:
            node.root_index[root['name']].add_to_group(group)
        group.from_full_NEURON_group(data)
    # File-backed groups cannot be exported to a subsequently connected model.
    for data in snapshot['groups']:
        group = node.groups[data['name']]
        if not restoring or data.get('_visible', True):
            group.show()
    if restoring:
        bpy.context.view_layer.update()
    return snapshot
