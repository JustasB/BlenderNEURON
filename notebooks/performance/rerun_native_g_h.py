"""Export authentic benchmark scenes, then time native Metal via BN RPC."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from blenderneuron import connection


def native_run(blend, log_path, blender):
    with tempfile.TemporaryDirectory(prefix='bn-native-render-') as config_dir:
        env = os.environ.copy()
        env.pop('COVERAGE_PROCESS_START', None)
        env['BLENDERNEURON_CONFIG_DIR'] = config_dir
        env['PYTHONPATH'] = str(ROOT)
        command = [str(blender), '--background', str(blend), '--python-exit-code', '1',
                   '--python', str(HERE / 'native_g_h_node.py')]
        with log_path.open('w') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 120
                address_path = Path(config_dir) / 'BlenderNEURON-Blender.address'
                while not address_path.exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(f'Native node startup failed; see {log_path}')
                    time.sleep(.2)
                address = json.loads(address_path.read_text())
                if not address.startswith('http://127.0.0.1:'):
                    raise RuntimeError('Expected a private loopback Blender node')
                secret = (Path(config_dir) / 'local-secret').read_text()
                client = connection.proxy(address, secret)
                assert client.ping() == 1
                task = client.enqueue_command(
                    "import sys; sys.path.insert(0, " + repr(str(HERE)) + "); "
                    "import native_g_h_node; return_value = native_g_h_node.measure()")
                deadline = time.monotonic() + 600
                while client.get_task_status(task) == 'QUEUED':
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise TimeoutError(f'Native rendering deadline; see {log_path}')
                    time.sleep(.25)
                if client.get_task_status(task) != 'SUCCESS':
                    raise RuntimeError(client.get_task_error(task))
                result = client.get_task_result(task)
                if 'Metal' not in result['graphics_renderer']:
                    raise RuntimeError(f'Expected native Metal: {result["graphics_renderer"]}')
                return result
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts', type=int, nargs='+', default=(8,16,32,64,128))
    parser.add_argument('--levels', nargs='+', default=('Cell','Section','3D Segment'))
    parser.add_argument('--export-container', default='blenderneuron-gh-export')
    parser.add_argument('--blender', type=Path, default=Path('/Applications/Blender.app/Contents/MacOS/Blender'))
    parser.add_argument('--results-dir', type=Path, default=HERE/'results'/'eevee_g_h_native')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--seed-results-dir', type=Path,
                        help='reuse the previous single-run measurements as repeat 1')
    args = parser.parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=True)
    scenes = HERE/'results'/'eevee_g_h_native_scenes'
    scenes.mkdir(parents=True, exist_ok=True)
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    conditions = []
    for repeat in range(1, args.repeats + 1):
        block = [(cells, level, repeat) for cells in args.counts for level in args.levels]
        random.Random(232 + repeat).shuffle(block)
        conditions.extend(block)
    aggregate = args.results_dir / 'results.json'
    previous = json.loads(aggregate.read_text())['records'] if aggregate.exists() else []
    rows = []
    for index, (cells, level, repeat) in enumerate(conditions, 1):
        slug = f'c{cells:03d}_{level.lower().replace(" ","_")}'
        blend = scenes/(slug+'.blend')
        seed = args.seed_results_dir/(slug+'.json') if args.seed_results_dir and repeat == 1 else None
        if args.repeats > 1:
            slug += f'_r{repeat:02d}'
        output = args.results_dir/(slug+'.json')
        print(f'[{index}/{len(conditions)}] {cells} cells / {level} / run {repeat}', flush=True)
        saved = [r for r in previous if r['cells'] == cells and r['recording'] == level
                 and r.get('repeat', 1) == repeat]
        if len(saved) == 1:
            result = saved[0]
        elif output.exists():
            result = json.loads(output.read_text())
        elif seed is not None and seed.exists():
            result = json.loads(seed.read_text())
            result.update(repeat=repeat, reused_from=str(seed))
            output.write_text(json.dumps(result, indent=2))
        else:
            if not blend.exists():
                relative = blend.relative_to(ROOT)
                with (args.results_dir/(slug+'_export.log')).open('w') as log:
                    subprocess.run(['docker','exec','-e','COVERAGE_PROCESS_START=',args.export_container,
                        'blender','--background','--python-exit-code','1','--python',
                        'notebooks/performance/render_figures_g_h.py','--','--save-blend',str(relative),
                        '--cells',str(cells),'--level',level], check=True, timeout=180,
                        stdout=log, stderr=subprocess.STDOUT)
            result = native_run(blend, args.results_dir/(slug+'.log'), args.blender)
            result['repeat'] = repeat
            output.write_text(json.dumps(result, indent=2))
        assert result['status'] == 'ok' and result['cells'] == cells and result['recording'] == level
        rows.append(result)
        (args.results_dir/'results.json').write_text(json.dumps(dict(records=rows, repeats=args.repeats,
            note='Fresh native Blender process per condition, controlled through authenticated BN RPC. '
            'Scenes exported via the unchanged live-NEURON/add-on benchmark path. '
            '12 warmed frames plus a separately timed first render. '
            'Host RAM: sampled peak across all renders minus pre-render current resident size; not VRAM.'), indent=2))
        print(f'  {result["seconds"]:.3f} s/frame; {result["rss_render_peak_delta_mib"]:.1f} MiB; '
              f'{result["graphics_renderer"]}', flush=True)


if __name__ == '__main__':
    main()
