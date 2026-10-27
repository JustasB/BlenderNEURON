"""Render four reviewed examples inside Docker, using a fresh cell per trial.

python notebooks/performance/render_confinement_examples.py
"""
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
from confinement_config import SETUP, EXAMPLES
CONDITIONS = tuple((angle, length) for angle, length, _ in EXAMPLES)


def main():
    results = HERE/'results/confinement_panels'
    results.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop('COVERAGE_PROCESS_START', None)
    rows = []
    for i, (angle, length) in enumerate(CONDITIONS):
        output = results/f'confined_{angle}deg_{length}um.json'
        command = ['blender', '--background', '--python-exit-code', '1',
                   '--python', str(HERE/'confinement.py'), '--', '--worker',
                   '--angle', str(angle), '--length', str(length), '--seed', '0',
                   '--render', '--output', str(output)]
        if i == 0:
            command += ['--before-render', str(results/'before_confinement.png')]
        with output.with_suffix('.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=300)
        row = json.loads(output.read_text())
        if rows:
            assert row['before'] == rows[0]['before'], 'Trials must start from identical original geometry'
            assert row['setup'] == rows[0]['setup']
        rows.append(row)
        print(f'Rendered {angle} degrees / {length} um, seed 0', flush=True)
    (results/'results.json').write_text(json.dumps({'records': rows}, indent=2))
    # The aggregate retains every measurement; per-worker JSON/logs are redundant.
    for angle, length in CONDITIONS:
        for suffix in ('.json', '.log'):
            (results/f'confined_{angle}deg_{length}um{suffix}').unlink()
    print('Panel source renders and measurements saved in', results, flush=True)


if __name__ == '__main__':
    main()
