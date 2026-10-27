"""Parallel-plane confinement sweep using production import/confinement/export.

Run the controller inside Docker; each condition starts a fresh Blender/NEURON.
Plot with plot_confinement.py. Existing performance measurements are untouched.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from confinement_config import SETUP, EXAMPLES

SLAB = SETUP['slab_um']
TARGET = SETUP['target_um']
ANGLES = (5., 10., 15., 25.)
LENGTHS = (200., 100., 75., 50., 25.)


def containment(snapshot, bounds, dendrites_only=True):
    """Exact polyline/slab intersection length; native and uniform point counts."""
    import numpy as np
    points_out = points_total = samples_out = samples_total = 0
    total_length = inside_length = 0.
    for name, sec in snapshot.items():
        if dendrites_only and '.dend' not in name:
            continue
        p = np.asarray(sec['points'], dtype=float)
        x = p[:, SETUP['axis']]
        points_out += int(((x < bounds[0]) | (x > bounds[1])).sum())
        points_total += len(p)
        lengths = np.linalg.norm(np.diff(p, axis=0), axis=1)
        arc = np.r_[0., np.cumsum(lengths)]
        # Fixed 1 um spacing plus distal endpoint, independently per section.
        locations = np.r_[np.arange(0., arc[-1], 1.), arc[-1]]
        sx = np.interp(locations, arc, x)
        samples_out += int(((sx < bounds[0]) | (sx > bounds[1])).sum())
        samples_total += len(sx)
        for a, b, length in zip(x[:-1], x[1:], lengths):
            total_length += float(length)
            if a == b:
                fraction = float(bounds[0] <= a <= bounds[1])
            else:
                lo, hi = sorted(((bounds[0]-a)/(b-a), (bounds[1]-a)/(b-a)))
                fraction = max(0., min(1., hi)-max(0., lo))
            inside_length += float(length)*fraction
    return dict(points_outside=points_out, points_total=points_total,
                points_outside_percent=100*points_out/points_total,
                uniform_points_outside_percent=100*samples_out/samples_total,
                cable_length_um=total_length, cable_inside_um=inside_length,
                cable_outside_percent=100*(1-inside_length/total_length))


def render_cell(path, group):
    """Use exactly the same appearance and camera as the reviewed live scene."""
    import bpy
    from confinement_setup import apply_print_style
    apply_print_style(group)
    scene = bpy.context.scene
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    # Render the same cell state from +Z, hiding decorative geometry and
    # boundary meshes so that the top plane cannot obscure the cell.
    from mathutils import Vector
    camera = scene.camera
    camera_matrix = camera.matrix_world.copy()
    camera_width = camera.data.ortho_scale
    resolution = (scene.render.resolution_x, scene.render.resolution_y)
    hidden = [(obj, obj.hide_render) for obj in scene.objects]
    cells = {container.get_object() for container in group.view.containers.values()}
    try:
        for obj, _ in hidden:
            obj.hide_render = obj not in cells
        camera.location = SETUP['inset_camera_location_um']
        camera.rotation_euler = (Vector(SETUP['inset_camera_target_um'])-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.data.ortho_scale = SETUP['inset_width_um']
        scene.render.resolution_x, scene.render.resolution_y = SETUP['inset_resolution']
        scene.render.filepath = str(path.with_name(path.stem+'_top.png'))
        bpy.ops.render.render(write_still=True)
    finally:
        for obj, was_hidden in hidden:
            obj.hide_render = was_hidden
        camera.matrix_world = camera_matrix
        camera.data.ortho_scale = camera_width
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.filepath = str(path)


def worker(args):
    import bpy
    import performance_eval as perf
    from export_roundtrip import remote_snapshot
    result = {}

    def experiment(group, node):
        # Orient the original source morphology in NEURON, then capture its
        # area before the Z-up import; the initial helper import is unmeasured.
        node.client.run_command(
            "import sys; sys.path.insert(0, %r); "
            "from confinement_config import orient_neuron_cell; orient_neuron_cell()" % str(HERE))
        before = remote_snapshot(node)
        assert bpy.ops.blenderneuron.import_groups() == {'FINISHED'}
        from confinement_setup import main as setup_scene
        setup_scene(group=group, node=node, output=args.output.with_suffix('.blend'),
                    render=False, transform_cell=False, save=False)
        if args.before_render is not None:
            render_cell(args.before_render, group)
        settings = group.ui_group.layer_confiner_settings
        settings.max_bend_angle = args.angle
        settings.height_min, settings.height_max = SETUP['height_fractions']
        settings.max_section_length = args.length
        settings.seed = args.seed
        settings.moveable_sections_pattern = SETUP['section_pattern']
        start = time.perf_counter()
        group.setup_confiner()
        setup_seconds = time.perf_counter()-start
        object_count = len(group.view.containers)
        start = time.perf_counter()
        group.confine_between_layers()
        bpy.context.view_layer.update()
        confine_seconds = time.perf_counter()-start
        if args.render:
            render_cell(args.output.with_suffix('.png'), group)
        start = time.perf_counter()
        assert bpy.ops.blenderneuron.update_groups_with_view_data() == {'FINISHED'}
        assert bpy.ops.blenderneuron.export_groups() == {'FINISHED'}
        export_seconds = time.perf_counter()-start
        after = remote_snapshot(node)
        assert set(before) == set(after)
        assert all(before[n]['parent'] == after[n]['parent'] and before[n]['nseg'] == after[n]['nseg'] for n in before)
        geometry = {}
        for key in ('area', 'volume', 'length'):
            pre = sum(s[key] for s in before.values())
            post = sum(s[key] for s in after.values())
            geometry[key] = dict(before=pre, after=post, relative_change_percent=100*(post-pre)/pre,
                max_section_relative_change_percent=max(abs(100*(after[n][key]-before[n][key])/before[n][key]) for n in before))
        result.update(setup=SETUP, angle=args.angle, max_length_um=args.length, seed=args.seed,
                      nominal_flexibility_deg_per_um=args.angle/args.length,
                      sections=args.sections, split_objects=object_count,
                      setup_seconds=setup_seconds, confine_seconds=confine_seconds, export_seconds=export_seconds,
                      geometry=geometry, topology_unchanged=True,
                      before=before, after=after, containment={})
        for label, bounds in (('slab', SLAB), ('target', TARGET)):
            result['containment'][label] = {
                population: {stage: containment(snap, bounds, population == 'dendrites')
                             for stage, snap in (('before', before), ('after', after))}
                for population in ('dendrites', 'whole_cell')}
        result['blender'] = bpy.app.version_string
    perf.clear_scene()
    perf.import_live_neuron_group(1, args.sections, 'Section', 'Section', False, after_import=experiment)
    args.output.write_text(json.dumps(result, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker', action='store_true')
    p.add_argument('--angle', type=float, default=15.)
    p.add_argument('--length', type=float, default=25.)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--sections', type=int, default=16)
    p.add_argument('--seeds', type=int, default=5)
    p.add_argument('--render', action='store_true')
    p.add_argument('--before-render', type=Path, help='Also render the original cell before confinement')
    p.add_argument('--output', type=Path)
    p.add_argument('--results-dir', type=Path, default=HERE/'results/confinement_z_up')
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None)
    if args.worker:
        worker(args)
        return
    directory = args.results_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop('COVERAGE_PROCESS_START', None)
    rows = []
    aggregate = directory/'results.json'
    cached = json.loads(aggregate.read_text())['records'] if aggregate.exists() else []
    cache = {(r['angle'], r['max_length_um'], r['seed']): r for r in cached}
    for angle in ANGLES:
        for length in LENGTHS:
            for seed in range(args.seeds):
                path = directory/f'a{angle:g}_l{length:g}_s{seed}.json'
                render = args.render and seed == 0 and (angle, length) in {(a, l) for a, l, _ in EXAMPLES}
                row = cache.get((angle, length, seed))
                if row is None and path.exists():
                    row = json.loads(path.read_text())
                if row is None or (render and not path.with_suffix('.png').exists()):
                    command = ['blender', '--background', '--python-exit-code', '1', '--python', str(Path(__file__).resolve()),
                               '--', '--worker', '--angle', str(angle), '--length', str(length), '--seed', str(seed),
                               '--sections', str(args.sections), '--output', str(path)]
                    if render:
                        command.append('--render')
                    with path.with_suffix('.log').open('w') as log:
                        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
                    row = json.loads(path.read_text())
                if row.get('setup') != SETUP:
                    raise RuntimeError('Saved results use a different setup/style; use a fresh results directory')
                assert row['sections'] == args.sections, 'Use a new directory for a different cell'
                rows.append(row)
                (directory/'results.json').write_text(json.dumps(dict(setup=SETUP, slab_z_um=SLAB, target_z_um=TARGET, records=rows), indent=2))
                print(f'{len(rows)}/{len(ANGLES)*len(LENGTHS)*args.seeds}: angle={angle:g}, length={length:g}, seed={seed}', flush=True)


if __name__ == '__main__':
    main()
