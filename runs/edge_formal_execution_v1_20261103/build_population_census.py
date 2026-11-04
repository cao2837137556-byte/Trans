"""Read already sealed metadata only; build exact population time-block frame."""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

from reporting import population_census, need

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def utc_ns(value):
    need(isinstance(value, str) and value.endswith('Z'), 'UTC_Z_CLOCK_REQUIRED')
    stamp = value[:-1]
    seconds, dot, fractional = stamp.partition('.')
    parsed = datetime.strptime(seconds, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    need(not dot or fractional.isdigit() and len(fractional) <= 9, 'UTC_NANOSECOND_PRECISION')
    epoch_seconds = (parsed-datetime(1970, 1, 1, tzinfo=timezone.utc)).days*86400 + parsed.hour*3600+parsed.minute*60+parsed.second
    return epoch_seconds*1_000_000_000 + int(fractional.ljust(9, '0') or '0')


def original_anchors(card):
    anchors = {('NORMAL', 'EDGE_NORMAL_SEGMENT_%d' % i): item['min_ns']
               for i, item in enumerate(card['capture_boundaries']['normal_segments'], 1)}
    for role in ('HTTP', 'UDP'):
        anchors[(role, 'EDGE_'+role)] = utc_ns(card['raw_inputs'][role]['UTC_range'][0])
    return anchors


def build(seal_directory, card_path, output, *, seconds=180):
    started = time.monotonic()
    deadline = started+seconds
    seal = Path(seal_directory)
    selection = read(seal/'QUERY_SELECTION_SEAL.json')
    meta_pin = selection['output_pins']['METADATA_CENSUS.json']
    need((seal/'METADATA_CENSUS.json').stat().st_size == meta_pin['bytes']
         and sha(seal/'METADATA_CENSUS.json') == meta_pin['sha256'], 'SELECTION_METADATA_CENSUS_PIN')
    meta = read(seal/'METADATA_CENSUS.json')
    card = read(card_path)
    expected_card = [pin for name, pin in meta['input_pins'].items()
                     if name.replace('\\', '/').endswith('EDGE_EXECUTION_CARD_DRAFT.json')]
    need(len(expected_card) == 1 and sha(card_path) == expected_card[0], 'METADATA_CARD_PIN')
    anchors = original_anchors(card)
    inputs = {str(Path(card_path)): sha(card_path),
              str(seal/'QUERY_SELECTION_SEAL.json'): sha(seal/'QUERY_SELECTION_SEAL.json'),
              str(seal/'METADATA_CENSUS.json'): sha(seal/'METADATA_CENSUS.json')}

    def rows():
        count = 0
        for role in ('NORMAL', 'HTTP', 'UDP'):
            item = meta['roles'][role]
            path = seal/item['metadata_file']
            before = (path.stat().st_size, path.stat().st_mtime_ns)
            need(sha(path) == item['metadata_sha256'], 'METADATA_SPOOL_SHA:'+role)
            inputs[str(path)] = item['metadata_sha256']
            with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
                for row in csv.DictReader(stream, delimiter='\t'):
                    if count % 65536 == 0:
                        need(time.monotonic() < deadline, 'METADATA_CENSUS_WALL_LIMIT')
                    row['source_role'] = role
                    row['timestamp_ns'] = int(row['timestamp_ns'])
                    row['protocol'] = int(row['protocol'])
                    count += 1
                    yield row
            need(before == (path.stat().st_size, path.stat().st_mtime_ns)
                 and sha(path) == item['metadata_sha256'], 'METADATA_CHANGED:'+role)

    result = population_census(rows(), anchors)
    for role in ('NORMAL', 'HTTP', 'UDP'):
        need(result['roles'][role]['population_count'] == meta['roles'][role]['counts']['query_candidates'],
             'COMPLETE_CANDIDATE_POPULATION_COUNT:'+role)
        need(result['roles'][role]['strata'] == meta['roles'][role]['strata'], 'CANDIDATE_STRATUM_COUNT:'+role)
    result.update(status='METADATA_ONLY_FULL_POPULATION_CENSUS_PASS',
                  elapsed_seconds=time.monotonic()-started, input_pins=inputs,
                  inputs_unchanged=True, model_calls=0, model_scores_read=False,
                  original_raw_packets_read=False,
                  zero_eligible_block_policy='Continuous first..last eligible candidate block span per capture/scenario; before-first eligible blocks excluded',
                  reference_or_commissioning_rows_in_denominator=False)
    output = Path(output)
    pending = output.with_name(output.name+'.pending')
    with pending.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(pending,output)
    output.with_name(output.name+'.sha256').write_text(sha(output)+'  '+output.name+'\n', encoding='utf-8')
    compressed = output.with_name(output.name+'.gz')
    pending = compressed.with_name(compressed.name+'.pending')
    with output.open('rb') as source, pending.open('wb') as destination:
        with gzip.GzipFile(filename='',fileobj=destination,mode='wb',mtime=0,compresslevel=6) as zipped:
            for block in iter(lambda:source.read(1024*1024),b''):
                zipped.write(block)
    os.replace(pending,compressed)
    compressed.with_name(compressed.name+'.sha256').write_text(sha(compressed)+'  '+compressed.name+'\n', encoding='utf-8')
    summary = dict(schema='EDGE_METADATA_TEMPORAL_CENSUS_SUMMARY_V1',status=result['status'],
        population_counts={role:v['population_count'] for role,v in result['roles'].items()},
        groups=[dict(source_role=g['source_role'],capture_id=g['capture_id'],scenario=g['scenario'],
                     anchor_ns=g['anchor_ns'],population_count=g['population_count'],
                     blocks=len(g['block_population_counts']),
                     zero_eligible_blocks=sum(n==0 for n in g['block_population_counts'].values()),
                     retained_normal_component_count=len(g['component_counts'])) for g in result['groups']],
        census_file=output.name,census_bytes=output.stat().st_size,census_sha256=sha(output),
        compressed_file=compressed.name,compressed_bytes=compressed.stat().st_size,
        compressed_sha256=sha(compressed),input_pins=inputs,
        source_scores_read=False,external_scores_read=False,raw_packets_read=False,
        model_calls=0,cloud_jobs_submitted=0)
    output.with_name('POPULATION_TEMPORAL_CENSUS_SUMMARY.json').write_text(
        json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'], elapsed_seconds=result['elapsed_seconds'],
        roles={role: value['population_count'] for role,value in result['roles'].items()},
        groups=len(result['groups']), output_bytes=output.stat().st_size)))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seal-directory', default=str(ROOT/'runs/edge_query_selection_v1_20261103/seal20k'))
    parser.add_argument('--card', default=str(ROOT/'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json'))
    parser.add_argument('--output', default=str(HERE/'POPULATION_TEMPORAL_CENSUS.json'))
    parser.add_argument('--wall-seconds', type=int, default=180)
    args = parser.parse_args()
    need(1 <= args.wall_seconds <= 180, 'BOUNDED_METADATA_ONLY_CENSUS')
    build(args.seal_directory, args.card, args.output, seconds=args.wall_seconds)
