"""Portable, versioned offline simulation snapshots (no Blender/NEURON imports)."""
import gzip
import math
import os
from pathlib import Path
import tempfile

from blenderneuron.utils import serialize, deserialize

FORMAT = 'BlenderNEURON simulation'
VERSION = 1
RECORDING_LEVELS = ('Cell', 'Section', '3D Segment')
DISPLAY_DEFAULTS = {
    'interaction_granularity': 'Cell', 'default_color': [0.14, 0.67, 0.02, 1.0],
    'smooth_sections': True, 'spherize_soma_if_DeqL': True, 'as_lines': False,
    'segment_subdivisions': 2, 'circular_subdivisions': 6,
    'default_brightness': 1.0, 'animate_brightness': True, 'max_brightness': 5.0,
    'animate_color': True, 'animation_range_low': -85.0,
    'animation_range_high': 20.0, 'simplification_epsilon': 0.1,
}
RECORDING_KEYS = ('record_variable', 'recording_granularity', 'recording_period',
                  'recording_time_start', 'recording_time_end', 'variable_units')


def validate_display(display):
    if not isinstance(display, dict):
        raise ValueError('Display settings must be a dictionary')
    for key, value in display.items():
        if key not in DISPLAY_DEFAULTS:
            raise ValueError('Unknown display setting: ' + key)
        default = DISPLAY_DEFAULTS[key]
        if key == 'interaction_granularity':
            valid = value in ('Group', 'Cell', 'Section')
        elif key == 'default_color':
            valid = (isinstance(value, (list, tuple)) and len(value) == 4
                     and all(isinstance(x, (int, float)) and math.isfinite(x)
                             and 0 <= x <= 1 for x in value))
        elif isinstance(default, bool):
            valid = isinstance(value, bool)
        else:
            valid = (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value))
            if key in ('segment_subdivisions', 'circular_subdivisions'):
                valid = valid and isinstance(value, int) and value >= (3 if key == 'circular_subdivisions' else 0)
            elif key not in ('animation_range_low', 'animation_range_high'):
                valid = valid and value >= 0
        if not valid:
            raise ValueError('Invalid display setting: ' + key)


def validate_recording(settings):
    for key in RECORDING_KEYS:
        if key not in settings:
            raise ValueError('Missing recording setting: ' + key)
    start, end, period = (settings[k] for k in
                          ('recording_time_start', 'recording_time_end', 'recording_period'))
    if (settings['recording_granularity'] not in RECORDING_LEVELS
            or not isinstance(settings['record_variable'], str) or not settings['record_variable']
            or not isinstance(settings['variable_units'], str)
            or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                   or not math.isfinite(v) for v in (start, end, period))
            or period <= 0 or start < 0 or (end != 0 and end < start)):
        raise ValueError('Invalid recording settings')


def validate_snapshot(snapshot):
    """Validate the entire payload before touching Blender's existing scene."""
    if (not isinstance(snapshot, dict) or snapshot.get('format') != FORMAT
            or snapshot.get('version') != VERSION):
        raise ValueError('Unsupported BlenderNEURON simulation format/version')
    groups = snapshot.get('groups')
    if not isinstance(groups, list) or not groups:
        raise ValueError('Simulation results must contain groups')
    group_names, root_names = set(), set()
    for group in groups:
        name = group.get('name')
        if not isinstance(name, str) or not name or name in group_names:
            raise ValueError('Invalid or duplicate group name')
        group_names.add(name)
        validate_display(group.get('display', {}))
        if not isinstance(group.get('record_activity'), bool):
            raise ValueError('Results require a boolean record_activity setting')
        validate_recording(group)
        recording = group['record_activity']
        times = group['activity']['times'] if recording else []
        if recording and (not times or any(not math.isfinite(t) for t in times)
                          or any(b <= a for a, b in zip(times, times[1:]))):
            raise ValueError('Group %r has missing or invalid sample times' % name)
        if not group['roots']:
            raise ValueError('Group %r has no cells' % name)
        level = group['recording_granularity']

        def check_values(activity):
            values = activity['values']
            if len(values) != len(times) or any(not math.isfinite(v) for v in values):
                raise ValueError('Group %r has invalid activity samples' % name)

        section_ids, section_names = set(), set()
        for root in group['roots']:
            if root['name'] in root_names:
                raise ValueError('A cell can belong to only one group: ' + root['name'])
            root_names.add(root['name'])
            stack = [(root, True)]
            while stack:
                section, is_root = stack.pop()
                if id(section) in section_ids or section['name'] in section_names:
                    raise ValueError('Repeated section in group ' + name)
                section_ids.add(id(section))
                section_names.add(section['name'])
                count = section['point_count']
                if (not isinstance(section['name'], str)
                        or not isinstance(count, int) or count < 2
                        or not isinstance(section['nseg'], int)
                        or section['nseg'] < 1
                        or len(section['coords']) != 3 * count
                        or len(section['radii']) != count
                        or any(not math.isfinite(v) for v in section['coords'])
                        or any(not math.isfinite(v) or v < 0 for v in section['radii'])):
                    raise ValueError('Invalid section morphology in group ' + name)
                # These fields are required by the Blender geometry builder.
                parent = section['parent_connection_loc']
                if ((parent is not None and (not isinstance(parent, (int, float)) or not 0 <= parent <= 1))
                        or section['connection_end'] not in (0, 1)):
                    raise ValueError('Invalid section connection in group ' + name)
                if recording and (level == 'Section' or (level == 'Cell' and is_root)):
                    check_values(section['activity'])
                elif recording and level == '3D Segment':
                    if set(section['segment_activity']) != {str(i) for i in range(count - 1)}:
                        raise ValueError('Missing segment activity in ' + section['name'])
                    for activity in section['segment_activity'].values():
                        check_values(activity)
                stack.extend((child, False) for child in section['children'])
    return snapshot


def write_snapshot(path, groups):
    snapshot = validate_snapshot({'format': FORMAT, 'version': VERSION,
                                 'units': {'time': 'ms', 'length': 'um'},
                                 'groups': groups})
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'wb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as stream:
                stream.write(serialize(snapshot).encode('utf-8'))
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_snapshot(path):
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            return validate_snapshot(deserialize(stream.read()))
    except (KeyError, TypeError, IndexError, AttributeError, EOFError, OSError) as error:
        raise ValueError('Invalid simulation results file: %s' % error) from error
