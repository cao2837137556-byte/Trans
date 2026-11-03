"""Hash-only deployment check; no numerical arrays or models are loaded."""
from lg.common import PACKAGE, ROOT, read_json, require, sha


def main():
    manifest = read_json(PACKAGE/'SOURCE_TRANSFER_MANIFEST.json')
    for rel, spec in manifest['files'].items():
        path = (ROOT/rel).resolve()
        require(path.is_relative_to(ROOT), 'INPUT_PATH_ESCAPE')
        require(path.is_file(), 'MISSING_SOURCE_INPUT:' + rel)
        require(path.stat().st_size == spec['bytes'] and sha(path) == spec['sha256'],
                'SOURCE_INPUT_MISMATCH:' + rel)
    print('SOURCE_DEPLOYMENT_SHA_PASS', len(manifest['files']), 'files; zero numerical operations')


if __name__ == '__main__':
    main()
