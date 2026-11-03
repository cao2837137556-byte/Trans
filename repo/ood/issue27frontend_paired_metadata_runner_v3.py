"""One explicitly authorized B-header projection. No model imports or forwards."""
from __future__ import annotations

import csv
import json
import subprocess
import threading
import time
import traceback
import types
import zipfile
from pathlib import Path

import issue27frontend_paired_metadata_v1 as s
from issue27frontend_paired_metadata_io_fix_v3 import atomic_json
s = types.SimpleNamespace(**vars(s))
s.atomic_json = atomic_json


def decoder_api():
    f3 = s.project_legacy('issue27frontend_f3_conflict_field_sufficiency_v1.py',
        {'tshark_command', 'normalize_tshark_cell', 'normalize_reset_frame_number'}, {'TSHARK_RESOURCE_PROFILE', 'SESSION_AUTO_RESET_PACKETS'})
    mod = s.project_legacy('issue27frontend_inheritance_outer_runner_v1.py', {'decoder_rows'}, extra={
        'csv': csv, 'subprocess': subprocess, 'threading': threading, 'zipfile': zipfile,
        's': types.SimpleNamespace(require=s.require), 'f3': f3})
    return mod.decoder_rows, f3


class Progress:
    def __init__(self, folder, caps, start):
        self.folder, self.caps, self.start = folder, caps, start
        self.state = {'status': 'PREPARING', 'packets': 0, 'packet_total': caps['packets'],
                      'targets_complete': 0, 'targets_total': caps['targets'], 'members_complete': 0,
                      'members_total': caps['members'], 'identity_files_complete': 0,
                      'model_calls': 0, 'optimizer_steps': 0, 'retries': 0}
        self.last = -1

    def check(self, force=False):
        now = time.monotonic()
        s.require(now - self.start < self.caps['wall_seconds'] - 2, 'WORKER_WALL_CAP')
        for key, cap in (('packets', 'packets'), ('targets_complete', 'targets'), ('members_complete', 'members')):
            s.require(self.state[key] <= self.caps[cap], 'ACTION_CAP_' + key)
        if force or now - self.last >= 1:
            self.last = now
            self.state['elapsed_seconds'] = now - self.start
            s.atomic_json(self.folder / 'progress.json', self.state)


def extract(targets, members, parser_set, decode, tshark, progress):
    """All decoded non-target rows are discarded; only scoped B descriptors persist."""
    descriptors = []
    for m in members:
        selected = [t for t in targets if t['owner'] == 'B' and
                    (t['source_group'], t['member']) == (m['source_group'], m['member'])]
        # This mapping is deliberately label/teacher/score free.
        by_position = {t['position']: {k: t[k] for k in ('uid', 'source_group', 'member', 'position', 'tier', 'timestamp_epoch')}
                       for t in selected}
        s.require(len(by_position) == len(selected) == m['selected_B_targets'], 'MEMBER_SELECTED_IDENTITY')
        s.require(max(by_position) + 1 == m['single_pass_prefix_packets'], 'MEMBER_EXACT_CUTOFF')
        identity = {**m, 'raw_source_path': m['member']}
        progress.state.update(status='READING_B_HEADERS', current_member=m['member'], member_packets=0,
                              member_packet_total=m['single_pass_prefix_packets'])
        progress.check(True)
        found = set()
        iterator = decode(tshark, identity, m['single_pass_prefix_packets'], parser_set[0].TSHARK_FIELDS, progress.check)
        try:
            for position, raw in enumerate(iterator):
                s.require(position < m['single_pass_prefix_packets'], 'PACKET_OVERRUN')
                progress.state['packets'] += 1
                progress.state['member_packets'] = position + 1
                if position in by_position:
                    descriptors.append(s.descriptor(raw, by_position[position], parser_set))
                    found.add(position); progress.state['targets_complete'] += 1
                progress.check()
        finally:
            if hasattr(iterator, 'close'):
                iterator.close()
        s.require(found == set(by_position) and progress.state['member_packets'] == m['single_pass_prefix_packets'], 'MEMBER_INCOMPLETE')
        progress.state['members_complete'] += 1
        progress.check(True)
    return sorted(descriptors, key=lambda d: d['uid'])


RESULT_FILES = {'B_route_descriptors.json', 'membership.csv', 'components.json', 'dependency_edges.json',
                'coverage.csv', 'schedule.json', 'membership_result.json', 'access_receipt.json'}


def write_result(output, result, descriptors, access):
    s.atomic_json(output / 'B_route_descriptors.json', descriptors)
    s.write_csv(output / 'membership.csv', result['membership'])
    for field in ('components', 'dependency_edges', 'schedule'):
        s.atomic_json(output / (field + '.json'), result[field])
    s.write_csv(output / 'coverage.csv', result['coverage'])
    s.atomic_json(output / 'membership_result.json', result['summary'])
    s.atomic_json(output / 'access_receipt.json', access)


def worker(output, config, start):
    progress = Progress(output, config['caps'], start)
    access = {'raw_container_hash_bytes': 0, 'raw_container_hash_files': 0, 'decoder_calls': 0,
              'project_packets_decoded': 0, 'B_descriptors': 0, 'non_B_descriptors': 0,
              'feature_arrays_opened': 0, 'model_loads': 0, 'model_forwards': 0, 'optimizer_steps': 0,
              'teacher_forwards': 0, 'select_research_rows': 0, 'sealed_role_files_opened': 0, 'retries': 0}
    try:
        targets, members = s.load_inputs()
        progress.check(True)
        # Hash immutable source containers once; ZIP decoding remains selected-member only.
        seen = set()
        for m in members:
            path = Path(m['container_path'])
            if str(path) in seen:
                continue
            s.require(path.stat().st_size == m['container_bytes'], 'RAW_CONTAINER_SIZE')
            progress.state.update(status='HASHING_INPUT_IDENTITY', identity_file=str(path),
                                  identity_bytes_total=config['raw_identity_bytes'])
            progress.check(True)
            s.require(s.sha_file(path, progress.check) == m['container_sha256_inherited'], 'RAW_CONTAINER_SHA256')
            seen.add(str(path))
            access['raw_container_hash_bytes'] += path.stat().st_size
            access['raw_container_hash_files'] += 1
            progress.state.update(identity_files_complete=len(seen), identity_bytes_complete=access['raw_container_hash_bytes'])
        progress.state.pop('identity_file', None)
        parser_set = s.parsers()
        decode, _ = decoder_api()

        def counted(*args):
            access['decoder_calls'] += 1
            s.require(access['decoder_calls'] <= config['caps']['members'], 'DECODER_CALL_CAP')
            return decode(*args)

        descriptors = extract(targets, members, parser_set, counted, config['tshark_path'], progress)
        access.update(project_packets_decoded=progress.state['packets'], B_descriptors=len(descriptors))
        s.require(access['project_packets_decoded'] == config['caps']['packets'] and
                  len(descriptors) == config['caps']['targets'] and access['decoder_calls'] == config['caps']['members'], 'FINAL_ACTION_COUNTS')
        progress.state.update(status='GROUPING_AND_FREEZING_MEMBERSHIP')
        progress.check(True)
        result = s.build_membership(targets, descriptors)
        write_result(output, result, descriptors, access)
        progress.check(True)
        terminal = {'status': 'METADATA_WORK_COMPLETE', 'result': result['summary'],
                    'access': access, 'config_sha256': s.digest(s.canonical(config)),
                    'output_hashes': {name: s.sha_file(output / name) for name in sorted(RESULT_FILES)}}
    except Exception as exc:
        terminal = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': type(exc).__name__ + ': ' + str(exc)[:2000],
                    'traceback': traceback.format_exc()[-12000:], 'access': access,
                    'partial_counts': progress.state, 'scientific_capability': 'NOT_TESTED'}
    s.atomic_json(output / 'worker_terminal.json', terminal)


def verify_worker(receipt, folder, config, synthetic=False):
    s.require(receipt['status'] in ('METADATA_WORK_COMPLETE', 'INPUT_OR_EXECUTION_STOP'), 'WORKER_STATUS')
    if receipt['status'] != 'METADATA_WORK_COMPLETE':
        return {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': receipt.get('reason', 'WORKER_STOP'), 'scientific_capability': 'NOT_TESTED'}
    s.require(not synthetic, 'SYNTHETIC_SUCCESS_REQUIRES_EXPLICIT_VALIDATOR')
    s.require(receipt['config_sha256'] == s.digest(s.canonical(config)), 'WORKER_CONFIG')
    s.require(set(receipt['output_hashes']) == RESULT_FILES, 'WORKER_OUTPUT_SET')
    for name, h in receipt['output_hashes'].items():
        s.require(s.sha_file(folder / name) == h, 'WORKER_OUTPUT_HASH')
    access = receipt['access']
    s.require(access == s.read_json(folder / 'access_receipt.json'), 'ACCESS_RECEIPT')
    s.require(access['project_packets_decoded'] == 8207642 and access['B_descriptors'] == 6737
              and access['decoder_calls'] == 22 and access['raw_container_hash_bytes'] == config['raw_identity_bytes']
              and access['raw_container_hash_files'] == config['raw_identity_files'], 'WORKER_DENOMINATOR')
    zero = ('non_B_descriptors', 'feature_arrays_opened', 'model_loads', 'model_forwards', 'optimizer_steps',
            'teacher_forwards', 'select_research_rows', 'sealed_role_files_opened', 'retries')
    s.require(all(access[k] == 0 for k in zero), 'FORBIDDEN_ACCESS')
    targets, _ = s.load_inputs()
    result = s.build_membership(targets, s.read_json(folder / 'B_route_descriptors.json'))
    for field in ('components', 'dependency_edges', 'schedule'):
        s.require(result[field] == s.read_json(folder / (field + '.json')), 'RECOMPUTED_' + field)
    s.require(result['summary'] == receipt['result'] == s.read_json(folder / 'membership_result.json'), 'RECOMPUTED_SUMMARY')
    for field, filename in (('membership', 'membership.csv'), ('coverage', 'coverage.csv')):
        normalized = [{k: '' if v is None else str(v) for k, v in row.items()} for row in result[field]]
        s.require(normalized == s.read_csv(folder / filename), 'RECOMPUTED_' + field)
    return result['summary']
