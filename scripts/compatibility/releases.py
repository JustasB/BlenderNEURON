"""Resolve stable upstream binary releases for the floating CI lane."""
import json
import re
from urllib.request import urlopen

PYPI = 'https://pypi.org/pypi/neuron/json'
PYTHON = 'https://raw.githubusercontent.com/docker-library/python/master/versions.json'
BLENDER = 'https://download.blender.org/release/'


def fetch(url):
    with urlopen(url, timeout=30) as response:
        return response.read().decode('utf-8')


def version(value):
    return tuple(map(int, value.split('.')))


def resolve_neuron(data, python_images, major=None):
    stable = [v for v, files in data['releases'].items()
              if re.fullmatch(r'\d+\.\d+\.\d+', v)
              and (major is None or version(v)[0] == major)
              and any(not f.get('yanked', False) for f in files)]
    if not stable:
        raise ValueError('No stable NEURON release found')
    neuron = max(stable, key=version)
    minors = set()
    for file in data['releases'][neuron]:
        if file.get('yanked', False):
            continue
        match = re.fullmatch(
            r'neuron-[^-]+-cp(3\d+)-cp\1-([^/]+)\.whl', file['filename'], re.I)
        if match and any(re.fullmatch(r'manylinux[^.]*_x86_64', tag)
                         for tag in match.group(2).split('.')):
            digits = match.group(1)
            minors.add('3.' + digits[1:])
    candidates = [entry['version'] for minor, entry in python_images.items()
                  if minor in minors and re.fullmatch(r'\d+\.\d+\.\d+', entry['version'])]
    if not candidates:
        raise ValueError('Newest NEURON {} has no stable official Python image with an AMD64 wheel'.format(neuron))
    python = max(candidates, key=version)
    entry = python_images['.'.join(python.split('.')[:2])]
    if 'slim-bookworm' not in entry['variants']:
        raise ValueError('Newest supported Python {} has no slim-bookworm image'.format(python))
    return neuron, python + '-slim-bookworm'


def resolve_blender():
    series = re.findall(r'href="Blender(\d+\.\d+)/"', fetch(BLENDER))
    if not series:
        raise ValueError('No Blender release series found')
    # The newest directory can contain prereleases only. Walk back until a
    # stable Linux archive exists; never accept alpha/beta/RC filenames.
    for release in sorted(set(series), key=version, reverse=True):
        archives = re.findall(r'href="blender-(\d+\.\d+\.\d+)-linux-x64\.tar\.xz"',
                              fetch(BLENDER + 'Blender' + release + '/'))
        if archives:
            return max(archives, key=version)
    raise ValueError('No stable Blender Linux AMD64 archive found')


def resolve_latest():
    neuron, python = resolve_neuron(json.loads(fetch(PYPI)), json.loads(fetch(PYTHON)))
    return neuron, python, resolve_blender()
