"""Install a pinned NumPy overlay into a fresh private run directory, offline."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from common import read, require, sha, write


def prepare(package, output, python=sys.executable):
    package, output = Path(package).resolve(), Path(output).resolve()
    require(not output.exists(), 'NEW_PRIVATE_RUNTIME_REQUIRED')
    require(sys.platform == 'linux' and sys.version_info[:2] == (3, 11),
            'LINUX_CP311_RUNTIME_REQUIRED')
    spec = read(package / 'config/runtime.json')
    wheel = package / spec['numpy_wheel']
    require(sha(wheel) == spec['numpy_wheel_sha256'], 'NUMPY_WHEEL_SHA')
    output.mkdir(parents=True)
    overlay = output / 'numpy201'
    # --target affects only this new job directory, never the shared environment.
    with (output / 'pip.log').open('x') as log:
        subprocess.run([python, '-m', 'pip', 'install', '--no-index', '--no-deps',
                        '--no-compile', '--target', str(overlay), str(wheel)], check=True,
                       timeout=180, stdout=log, stderr=subprocess.STDOUT)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(overlay) + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['HF_HUB_OFFLINE'] = env['TRANSFORMERS_OFFLINE'] = '1'
    # A new interpreter imports the actual E3 dependency closure, not just
    # distribution metadata or a NumPy toy operation.
    probe = package / 'src/runtime_probe.py'
    subprocess.run([python, '-B', str(probe), '--overlay', str(overlay),
                    '--output', str(output / 'environment.json'), '--versions',
                    str(package / 'vendor/encoding_v2/config.json')],
                   env=env, check=True, timeout=180)
    return dict(status='COMPLETE', overlay=str(overlay), runtime_gate='IMPORT_ONLY_NO_FORWARD',
                numpy_wheel_sha256=spec['numpy_wheel_sha256'], numerical_parity='NOT_ASSESSED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prepare(args.package, args.output)
    write(Path(args.output) / 'RESULT.json', result)


if __name__ == '__main__':
    main()
