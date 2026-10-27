"""Install a checksum-verified Blender archive for development or CI."""
from __future__ import print_function
import argparse
import glob
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile


def install(version, destination, with_coverage=False):
    destination = Path(destination).resolve()
    if destination.exists():
        print('Blender folder found, skipped download: ' + str(destination), flush=True)
    else:
        series = '.'.join(version.split('.')[:2])
        archive = 'blender-{}-linux-x64.tar.xz'.format(version)
        base = 'https://mirror.clarkson.edu/blender/release/Blender' + series + '/'
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(destination.parent)) as temporary:
            temporary = Path(temporary)
            downloaded = temporary / archive
            checksum = temporary / 'blender.sha256'
            for url, path in ((base + archive, downloaded),
                              (base + 'blender-' + version + '.sha256', checksum)):
                subprocess.check_call(['curl', '-fL', '--retry', '3', '--connect-timeout', '30',
                                       '--max-time', '600', url, '-o', str(path)])
            matches = [line.split()[0] for line in checksum.read_text().splitlines()
                       if line.split() and line.split()[-1].lstrip('*') == archive]
            if len(matches) != 1:
                raise RuntimeError('Expected one checksum for ' + archive)
            digest = hashlib.sha256()
            with downloaded.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != matches[0]:
                raise RuntimeError('Blender archive checksum mismatch')
            unpacked = temporary / 'unpacked'
            unpacked.mkdir()
            subprocess.check_call(['tar', '-xJf', str(downloaded), '--strip-components=1',
                                   '-C', str(unpacked)])
            os.rename(str(unpacked), str(destination))
        print('Blender installed in: ' + str(destination), flush=True)
    if with_coverage:
        bundled_python = next(path for path in glob.glob(str(destination / '*/python/bin/python3*'))
                              if re.search(r'/python3\.\d+$', path))
        subprocess.check_call([bundled_python, '-m', 'ensurepip'])
        coverage_pin = '7.10.7' if bundled_python.endswith('python3.9') else '7.12'
        subprocess.check_call([bundled_python, '-m', 'pip', 'install', 'coverage==' + coverage_pin])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='5.2.3')
    parser.add_argument('--destination', default='./blender')
    parser.add_argument('--coverage', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        parser.error('Version must contain major.minor.patch')
    install(args.version, args.destination, args.coverage)


if __name__ == '__main__':
    main()
