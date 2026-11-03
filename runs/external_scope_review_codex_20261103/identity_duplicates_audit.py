"""Read-only raw identity and exact duplicate checks; no feature/model imports."""
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runs/edge_iiotset_raw_qualification_v1_20261102'))
from scan_raw import RawRecords, sha

TARGET = 'dc:a6:32:fb:69:b5'
WINDOW_NS = 1_000_000_000
MAX_KEYS = 200_000
START = time.monotonic()
DEADLINE = START + 240


def dump(name, value):
    p = OUT / name
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (p.parent / (p.name + '.sha256')).write_text(sha(p) + '  ' + p.name + '\n', encoding='utf-8')


def exact_duplicates(path):
    before = sha(path)
    reader = RawRecords(path)
    seen, heap, examples = {}, [], []
    high = None
    duplicates = cross_interface = peak = count = 0
    error = None
    try:
        for frame, record in enumerate(reader, 1):
            ns, payload, caplen, wirelen, link, interface, _ = record
            count += 1
            if ns is None:
                raise ValueError('Missing timestamp: exact audit unavailable')
            high = ns if high is None else max(high, ns)
            floor = high - WINDOW_NS
            if ns < floor:
                raise ValueError('Lateness exceeds retained window: refuse whole-file duplicate claim')
            while heap and heap[0][0] < floor:
                _, _, key = heapq.heappop(heap)
                del seen[key]
            # Actual bytes, not a digest equality, decide duplicates.
            key = (ns, link, caplen, wirelen, payload)
            if key in seen:
                duplicates += 1
                first, first_interface = seen[key]
                cross_interface += interface != first_interface
                if len(examples) < 5:
                    examples.append(dict(first_frame=first, duplicate_frame=frame, timestamp_ns=ns))
            else:
                seen[key] = (frame, interface)
                heapq.heappush(heap, (ns, frame, key))
            peak = max(peak, len(seen))
            if peak > MAX_KEYS:
                raise MemoryError('Bounded duplicate key cap exceeded')
            if frame % 100_000 == 0 and time.monotonic() > DEADLINE:
                raise TimeoutError('Shared read-only 240s bound')
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    after = sha(path)
    return dict(path=str(path), sha256_before=before, sha256_after=after,
                input_unchanged=before == after, records_processed=count,
                complete=error is None, error=error,
                exact_duplicate_records=duplicates, cross_interface_exact_duplicates=cross_interface,
                peak_retained_keys=peak, examples=examples,
                semantics='Same integer timestamp, linktype, captured/wire lengths and exact captured bytes',
                proof='All records verified within 1s of high-water timestamp; eviction cannot hide a duplicate unless a later record violates this bound, which fails the audit.',
                not_proven=['Clock-shifted mirrors', 'Different-time repeated bytes are not automatically duplicates',
                            'Physical hardware serial identity'])


def main():
    q = ROOT / 'runs/edge_iiotset_raw_qualification_v1_20261102'
    manifest = json.loads((q / 'RESULT.json').read_text(encoding='utf-8-sig'))
    duplicate_results = {}
    for role in ('HTTP', 'UDP', 'NORMAL'):
        spec = manifest['inputs'][role]
        result = exact_duplicates(Path(spec['path']))
        assert result['sha256_before'] == spec['sha256']
        assert result['input_unchanged']
        duplicate_results[role] = result
        print(role, result['complete'], result['exact_duplicate_records'], flush=True)
    dump('EXACT_DUPLICATES.json', dict(results=duplicate_results,
         complete=all(x['complete'] for x in duplicate_results.values()),
         scope='Whole-file exact observations; no timestamps, order or input bytes changed'))

    assets = json.loads((ROOT / 'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json').read_text(encoding='utf-8-sig'))
    specs = {v['query']['rows']['path']: v['query']['rows'] for v in assets['pools'].values()}
    specs.update({v['dense_bank']['rows']['path']: v['dense_bank']['rows'] for v in assets['pools'].values()})
    specs[assets['a_history']['rows']['path']] = assets['a_history']['rows']
    learn = 'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/LEARN.jsonl.gz'
    specs[learn] = {'path': learn}
    owner_re = re.compile(rb'"owner"\s*:\s*"([0-9a-f:]{17})"', re.I)
    rows = []
    for relative, spec in specs.items():
        path = ROOT / relative
        before = sha(path)
        if 'sha256' in spec:
            assert before == spec['sha256']
        owners, lines, missing = set(), 0, 0
        with gzip.open(path, 'rb') as stream:
            for line in stream:
                lines += 1
                match = owner_re.search(line)
                if match:
                    owners.add(match.group(1).decode().lower())
                else:
                    missing += 1
                if lines % 100_000 == 0 and time.monotonic() > DEADLINE:
                    raise TimeoutError('Shared read-only 240s bound')
        assert before == sha(path)
        rows.append(dict(path=relative, bytes=path.stat().st_size, sha256=before,
                         prior_sha256_pin_check='MATCHED' if 'sha256' in spec else 'NOT_PROVIDED',
                         current_sha256_recorded=True, input_unchanged=True,
                         records=lines, missing_owner=missing,
                         owners=sorted(owners), edge_owner_matches=TARGET in owners))
    dump('LINEAGE_OWNER_AUDIT.json', dict(status='OBSERVED_METADATA_OWNER_COMPARISON_COMPLETE',
         target_owner=TARGET, inputs=rows, observed_overlap=any(x['edge_owner_matches'] for x in rows),
         limitations=['This is the named current source/A/B/bank metadata scope, not all ever downloaded datasets.',
                     'Historical target-owner roster and raw-source provenance must also be checked.',
                     'Absence of a MAC match does not prove encoder pretraining provenance or hardware serial identity.'],
         model_execution=False, elapsed_seconds=time.monotonic()-START))


if __name__ == '__main__':
    main()
