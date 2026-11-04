"""Read-only integrity audit of 181645 spools; no decoding, models or migration."""
import hashlib
import json
from pathlib import Path
import struct
import time

DEPLOY = Path('/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_gate_deployment_v2_20261103')
CARD_SHA = '54ad4848a9fe66864ba3fd0c6db489dc7461ed33985b6d66372509ca5692882f'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4*1024**2), b''): h.update(block)
    return h.hexdigest()


def read(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_size < 32*1024**2
    return json.loads(path.read_text())


def audit():
    start = time.monotonic()
    output = DEPLOY/'outputs/gate_181645'
    card_path = DEPLOY/'checkout/runs/edge_formal_gate_deployment_v2_20261103/ENGINEERING_CARD.json'
    assert sha(card_path) == CARD_SHA
    card = read(card_path)
    pointer = read(output/'CURRENT_ENGINEERING_ATTEMPT.json')
    assert pointer['status'] == 'STOP' and pointer['card_sha256'] == CARD_SHA
    stop_path = output/pointer['receipt']
    assert sha(stop_path) == pointer['receipt_sha256']
    stop = read(stop_path)
    assert stop['scratch_cleanup']['complete']
    results = {}
    for role in ('NORMAL', 'HTTP', 'UDP'):
        root = output/'spools'/role
        complete_path = root/'COMPLETE.json'
        if not complete_path.exists():
            results[role] = dict(status='INCOMPLETE_NOT_REUSABLE',
                committed_partial_chunks=len(list(root.glob('attempt-*/chunk-*/CHUNK.json'))))
            continue
        binding_path = root/'BINDING.json'
        binding = read(binding_path); complete = read(complete_path)
        assert complete['binding_sha256'] == sha(binding_path)
        assert complete['generator_exhausted'] and complete['raw_final_identity_pass']
        assert binding['role'] == role and complete['role'] == role
        identity = binding['identity']
        for key in ('dependency_envelope', 'runtime_identity', 'selection_seal_sha256'):
            assert identity[key] == card[key], key
        assert identity['scientific_artifact_pins'] == card['scientific_input_artifact_pins']
        assert complete['uids'] == binding['expected_uids']
        expected_rows = 24124 if role == 'NORMAL' else 20000
        assert len(complete['uids']) == expected_rows and len(set(complete['uids'])) == expected_rows
        assert Path(complete['attempt']).name == complete['attempt']
        attempt = root/complete['attempt']; assert not attempt.is_symlink()
        seen = set(); total = 0
        for i, record in enumerate(complete['chunks']):
            assert record['name'] == 'chunk-%06d' % i
            folder = attempt/record['name']; assert not folder.is_symlink()
            assert read(folder/'CHUNK.json') == record
            for name, field in [('snapshots.bin', 'data'), ('INDEX.json', 'index')]:
                path = folder/name; pin = record[field]
                assert path.is_file() and not path.is_symlink()
                assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256']
                total += pin['bytes']
            entries = read(folder/'INDEX.json'); assert len(entries) == record['rows']
            with (folder/'snapshots.bin').open('rb') as f:
                for entry in entries:
                    assert entry['uid'] not in seen and entry['header']['uid'] == entry['uid']
                    seen.add(entry['uid'])
                    size = struct.unpack('<Q', f.read(8))[0]
                    assert size == entry['bytes'] and f.tell() == entry['offset'] and size < 16*1024**2
                    assert hashlib.sha256(f.read(size)).hexdigest() == entry['sha256']
                assert not f.read(1)
        assert seen == set(complete['uids'])
        coverage = read(root/'REPLAY_COVERAGE.json')
        assert coverage['generator_exhausted'] and coverage['final_raw_identity_pass']
        assert coverage['last_frame'] == coverage['expected_records']
        assert coverage['raw_sha256'] == identity['raw_pins'][role]['sha256']
        results[role] = dict(status='COMPLETE_V2_BYTES_AND_BINDING_VERIFIED',
            rows=expected_rows, chunks=len(complete['chunks']), payload_and_index_bytes=total,
            binding_sha256=sha(binding_path), complete_sha256=sha(complete_path), coverage=coverage)
    return dict(schema='EDGE_181645_RETAINED_ROLE_AUDIT_V1', job_id='181645',
        status='V2_RETAINED_ARTIFACT_INTEGRITY_AUDITED_NOT_V3_MIGRATION', roles=results,
        seconds=time.monotonic()-start, model_calls=0, raw_packets_decoded=0,
        original_spools_modified=False, cross_version_migration_authorized=False,
        incomplete_role_reusable=False)


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
