"""Repackage sixteen byte-pinned source assets; never open target query files."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import tarfile


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployment-root', type=Path, required=True)
    parser.add_argument('--head-run', type=Path,
                        default=Path('/srv/paper04/runs/query_twelve_heads_20261022_v1'))
    parser.add_argument('--query-code', type=Path,
                        default=Path('/srv/paper04/assets/query_tail_v2r3'))
    args = parser.parse_args()
    expected = json.loads((Path(__file__).parent / 'source_members.json').read_text())
    assert len(expected) == 16, 'SOURCE_ALLOWLIST_COUNT'
    sources = {}
    for name, item in expected.items():
        role, relative = name.split('/', 1)
        assert role in ('run', 'query_code'), 'SOURCE_ROLE'
        parent = (args.head_run if role == 'run' else args.query_code).resolve()
        source = (parent / relative).resolve()
        assert source.is_relative_to(parent), 'SOURCE_PATH_ESCAPE'
        assert source.is_file() and source.stat().st_size == item['bytes'], name
        assert sha(source) == item['sha256'], 'SOURCE_BYTE_IDENTITY:' + name
        sources[name] = source
    destination = args.deployment_root.resolve() / 'inputs/source_head_archive'
    assert not destination.exists(), 'NO_RETRY_SOURCE_ARCHIVE'
    destination.mkdir(parents=True)
    part = destination / 'source-only-000000.tar'
    with tarfile.open(part, mode='x', format=tarfile.PAX_FORMAT) as archive:
        for name, source in sources.items():
            archive.add(source, arcname=name, recursive=False)
    for name, source in sources.items():
        assert sha(source) == expected[name]['sha256'], 'SOURCE_CHANGED_DURING_COPY'
    index = dict(schema='learned-onboarding-source-transport-v1',
                 scope='SOURCE_HEAD_ALLOWLIST_ONLY_NOT_FULL_RESULT_BACKUP',
                 format='tar-stream-concatenate-parts-in-order', complete=True,
                 compression='none', bytes=part.stat().st_size,
                 chunks=[dict(name=part.name, bytes=part.stat().st_size, sha256=sha(part))],
                 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 original_member_identities=expected,
                 source_paths={name: str(path) for name, path in sources.items()},
                 target_query_files_opened=0)
    with (destination / 'BACKUP_INDEX.json').open('x', encoding='utf-8') as stream:
        json.dump(index, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status='SOURCE_TRANSPORT_READY', files=len(sources),
                          bytes=index['bytes'], index_sha256=sha(destination/'BACKUP_INDEX.json'),
                          target_query_files_opened=0)))


if __name__ == '__main__':
    main()
