"""Scene-owned dataset source and offline persistence, independent of pairing."""
import base64
import os
import zlib

import bpy

from blenderneuron.results import DISPLAY_DEFAULTS, validate_snapshot
from blenderneuron.utils import serialize, deserialize

MODE = 'blenderneuron_dataset_mode'
SOURCE = 'blenderneuron_dataset_source'
PAYLOAD = 'blenderneuron_dataset_snapshot'


def is_offline():
    return bpy.context.scene.get(MODE, 'LIVE') == 'OFFLINE'


def require_live(node):
    if is_offline():
        raise RuntimeError('Offline results cannot communicate with NEURON. Switch to live mode first.')
    if node is None or node.client is None:
        raise RuntimeError('Connect to NEURON before using this operation.')
    return node.client


def store_snapshot(snapshot, source):
    scene = bpy.context.scene
    scene[PAYLOAD] = base64.b64encode(zlib.compress(serialize(snapshot).encode('utf-8'))).decode('ascii')
    scene[SOURCE] = os.path.abspath(source)
    scene[MODE] = 'OFFLINE'


def saved_snapshot():
    payload = bpy.context.scene.get(PAYLOAD)
    if not payload:
        raise ValueError('The offline scene has no saved simulation snapshot')
    return validate_snapshot(deserialize(zlib.decompress(base64.b64decode(payload)).decode('utf-8')))


def save_offline_state(_save_argument=None):
    """Keep display choices and visibility when saving; never store credentials."""
    if not is_offline():
        return
    scene = bpy.context.scene
    node = getattr(bpy.types.Object, 'BlenderNEURON_node', None)
    if node is None:
        return
    snapshot = saved_snapshot()
    groups = []
    for data in snapshot['groups']:
        group = node.groups.get(data['name'])
        if group is None:
            continue
        data['display'] = {key: (list(getattr(group, key)) if key == 'default_color'
                                 else getattr(group, key)) for key in DISPLAY_DEFAULTS}
        data['_selected'] = group.selected
        data['_visible'] = group.view is not None
        groups.append(data)
    # A scene with all groups removed can still retain its last valid snapshot;
    # saving/reopening must not silently switch it to live mode.
    snapshot['_empty'] = not bool(groups)
    if groups:
        snapshot['groups'] = groups
    store_snapshot(snapshot, scene.get(SOURCE, ''))


def clear_dataset(node):
    for group in list(node.groups.values()):
        group.remove()
    node.root_index.clear()
    node.synapse_sets.clear()


def switch_to_live(node):
    """Explicitly discard the offline dataset before attempting a live connection."""
    clear_dataset(node)
    node.client = None
    node.client_address = None
    node.export_requires_confirmation = False
    node._last_live_peer = None
    scene = bpy.context.scene
    scene[MODE] = 'LIVE'
    for key in (SOURCE, PAYLOAD):
        if key in scene:
            del scene[key]


def restore_offline_state(node):
    from blenderneuron.blender.offline import import_simulation_snapshot
    snapshot = saved_snapshot()
    # Rebuild runtime group references, retaining the saved scene timeline scale.
    node.ui_properties.groups.clear()
    node.ui_properties.groups_index = 0
    node.ui_properties.synapse_sets.clear()
    if snapshot.get('_empty'):
        return
    import_simulation_snapshot(node, snapshot, bpy.context.scene.get(SOURCE, ''), restoring=True)
