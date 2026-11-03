"""Adopt only job-180670's complete preparation, never its lost E3 ledger.

The source tree is read-only. No raw PCAP traversal, decoder, contextual replay,
selection-policy change or model inference is performed by this module.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import sqlite3

import numpy as np

from hnr.common import ROOT, PACKAGE, VERSION, digest, read, require, rows, sha, write


EXPECTED = {'ref_rows': 8192, 'dev_rows': 4096}
FILES = ('LOGICAL_INPUT.json', 'ROLE_BINDING.json', 'DECODER_DIAGNOSTIC_AUDIT.json',
         'candidates.sqlite', 'selected_snapshots.jsonl.gz', 'decoder_pass1.stderr.log',
         'decoder_pass2.stderr.log')


def source_package(card):
    relative = Path(card['recovery']['prepared_source_package'])
    root = Path(ROOT).resolve(); source = root/relative
    require(not relative.is_absolute() and source.resolve().is_relative_to(root) and
            not source.is_symlink(), 'PREPARED_SOURCE_SCOPE')
    return source


def check_prepared(spec, card=None):
    """Validate source receipt, selected endpoint identities, roles and q14."""
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    card = read(PACKAGE/'EXECUTION_CARD.json') if card is None else card
    require(spec['key'] == 'NETATMO', 'ONLY_NETATMO_PREPARED_REUSE')
    package = source_package(card); source = package/'outputs/encoding/history/NETATMO'
    require(not source.is_symlink(), 'PREPARED_SOURCE_MEMBER_LINK')
    receipt_path = source/'PREPARE_RESULT.json'
    require(sha(package/'EXECUTION_CARD.json') == card['recovery']['prepared_source_card_sha256'] and
            sha(receipt_path) == card['recovery']['prepared_source_receipt_sha256'], 'PREPARED_SOURCE_PIN')
    receipt = read(receipt_path); logical = read(source/'LOGICAL_INPUT.json')
    require(receipt['status'] == 'PREPARED' and receipt['version'] == VERSION and
            receipt['input_readout'] == 'RECENT_CURRENT_INCLUSIVE' and
            receipt['real_E3_forwards'] == 0 and receipt['all_legal_endpoint_rows_exactly_replayed'] is True,
            'COMPLETE_PREPARED_RECEIPT')
    for name, field in [('LOGICAL_INPUT.json', 'logical_input_sha256'),
                        ('candidates.sqlite', 'census_sha256'),
                        ('selected_snapshots.jsonl.gz', 'snapshots_sha256'),
                        ('DECODER_DIAGNOSTIC_AUDIT.json', 'diagnostic_audit_sha256')]:
        require(not (source/name).is_symlink() and sha(source/name) == receipt[field], 'PREPARED_FILE_PIN:' + name)
    require(logical['source_kind'] == 'BYTE_PRESERVING_CHRONOLOGICAL_PCAPNG' and
            logical['source_sha256'] == receipt['source_sha256'] and
            all(logical[k] == spec[k] for k in ('raw', 'packet_index', 'chronological_order')),
            'PREPARED_LOGICAL_SOURCE')
    binding = read(source/'ROLE_BINDING.json')
    require(binding == receipt['role_binding'] and
            all(binding[k] == spec[k] for k in ('packets', 'bank_end_frame', 'reference_end_us', 'first_dev_time_us')),
            'PREPARED_ROLE_BINDING')
    diagnostic = read(source/'DECODER_DIAGNOSTIC_AUDIT.json')
    require(diagnostic['all_other_diagnostics_rejected'] is True and diagnostic['decoder_exit_zero'] is True and
            sha(source/'decoder_pass1.stderr.log') == diagnostic['prior_stderr_sha256'] and
            sha(source/'decoder_pass2.stderr.log') == diagnostic['new_stderr_sha256'], 'PREPARED_DIAGNOSTIC_LINK')
    selection = read(source/'selection/SELECTION.json')
    require(selection == receipt['selection'] and selection['status'] == 'SELECTED' and
            selection['device_scope'] == [spec['device']] and
            selection['census_sha256'] == receipt['census_sha256'], 'PREPARED_SELECTION_RECEIPT')
    metadata = []
    for field, role, use in [('ref_rows', 'HIST_REF', 'REFERENCE'), ('dev_rows', 'HIST_DEV', 'QUERY')]:
        item = selection[field]; path = source/'selection'/Path(item['path']).name
        require(Path(item['path']).resolve() == path.resolve() and not path.is_symlink() and
                sha(path) == item['sha256'], 'PREPARED_SELECTED_FILE_PIN')
        rr = list(rows(path)); ids = [r['uid'] for r in rr]
        require(len(rr) == item['rows'] == EXPECTED[field] and ids == sorted(ids) and
                len(set(ids)) == len(ids) and digest(ids) == item['uid_sha256'], 'PREPARED_SELECTED_UIDS')
        require(all(r['history_role'] == role and r['use'] == use and type(r['label']) is int and
                    r['label'] == 0 and r['device'] == spec['device'] and r['owner'] == spec['owner'] and
                    r['capture_id'] == spec['capture_id'] and r['source_sha256'] == receipt['source_sha256'] and
                    r['origin_raw_sha256'] == spec['raw']['sha256'] and r['uid'] ==
                    digest([receipt['source_sha256'], r['frame'], spec['owner']]) for r in rr),
                'PREPARED_SELECTED_ROLE_SOURCE')
        for row in rr:
            before = row['frame'] <= binding['bank_end_frame'] and row['timestamp_us'] <= binding['reference_end_us']
            after = row['frame'] > binding['bank_end_frame'] and row['timestamp_us'] >= binding['first_dev_time_us']
            require(before if use == 'REFERENCE' else after, 'PREPARED_SELECTED_ROLE_TIME')
        metadata.extend(rr)
    metadata.sort(key=lambda r: r['uid'])
    require(len({r['uid'] for r in metadata}) == len(metadata), 'PREPARED_REF_DEV_OVERLAP')
    snapshots = list(rows(source/'selected_snapshots.jsonl.gz'))
    require([e['uid'] for e in snapshots] == [r['uid'] for r in metadata], 'PREPARED_SNAPSHOT_UID_COVERAGE')
    db = sqlite3.connect('file:'+(source/'candidates.sqlite').resolve().as_posix()+'?mode=ro', uri=True)
    try:
        for entry, row in zip(snapshots, metadata):
            require(entry['row'] == row and entry['body']['source_sha256'] == receipt['source_sha256'],
                    'PREPARED_SNAPSHOT_SOURCE_ROW')
            found = db.execute('SELECT body FROM candidates WHERE uid=?', (row['uid'],)).fetchone()
            require(found is not None and json.loads(found[0]) == row, 'PREPARED_SELECTED_CENSUS_JOIN')
            origin = db.execute('SELECT raw_sha,ordinal,owner FROM physical_origins WHERE uid=?', (row['uid'],)).fetchone()
            require(origin == (row['origin_raw_sha256'], row['origin_packet_ordinal'], row['owner']),
                    'PREPARED_SELECTED_PHYSICAL_ORIGIN')
            descriptor = reference_descriptor if row['use'] == 'REFERENCE' else query_descriptor
            q14 = descriptor(entry['body'], row)[0]
            saved = np.asarray(entry['q14'], dtype=np.float32)
            require(q14.dtype == np.float32 and q14.shape == saved.shape == (14,) and
                    np.isfinite(saved).all() and saved.tobytes() == q14.tobytes(), 'PREPARED_Q14_REPLAY')
    finally:
        db.close()
    pins = {name: sha(source/name) for name in FILES}
    pins['PREPARE_RESULT.json'] = sha(receipt_path)
    pins['selection/SELECTION.json'] = sha(source/'selection/SELECTION.json')
    for field in EXPECTED:
        name = 'selection/'+Path(selection[field]['path']).name; pins[name] = selection[field]['sha256']
    return dict(source=source, receipt=receipt, selection=selection, files=pins,
                snapshots=len(snapshots), references=EXPECTED['ref_rows'], queries=EXPECTED['dev_rows'])


def _immutable_link(source, target, expected):
    require(not target.exists() and not source.is_symlink(), 'PREPARED_NEW_LINK')
    target.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat()
    try:
        os.link(source, target); method = 'HARDLINK_READ_ONLY_USE'
    except OSError:
        shutil.copyfile(source, target); method = 'COPY'
        require(sha(target) == expected, 'PREPARED_COPY_PIN')
    after = source.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'PREPARED_SOURCE_MUTATED')
    if method == 'HARDLINK_READ_ONLY_USE':
        require(os.path.samefile(source, target), 'PREPARED_HARDLINK_IDENTITY')
    return dict(sha256=expected, bytes=after.st_size, method=method)


def reuse_prepared(spec, destination, runtime=None, card=None):
    checked = check_prepared(spec, card); source = checked['source']; destination = Path(destination)
    require(not destination.exists(), 'PREPARED_DESTINATION_NEW')
    destination.mkdir(parents=True)
    copied = {}
    for name, expected in checked['files'].items():
        if name in ('PREPARE_RESULT.json', 'selection/SELECTION.json'):
            continue
        copied[name] = _immutable_link(source/name, destination/name, expected)
        if runtime is not None:
            runtime.update('PREPARED_ASSETS_REUSED', prepared_file=name, selected_snapshots=checked['snapshots'],
                           raw_decodes_this_attempt=0, prior_preparation_reused=True)
    copied['SOURCE_PREPARE_RESULT.json'] = _immutable_link(source/'PREPARE_RESULT.json',
        destination/'SOURCE_PREPARE_RESULT.json', checked['files']['PREPARE_RESULT.json'])
    selection = copy.deepcopy(checked['selection'])
    for field in EXPECTED:
        selection[field]['path'] = str(destination/'selection'/Path(selection[field]['path']).name)
    write(destination/'selection/SELECTION.json', selection)
    receipt = copy.deepcopy(checked['receipt']); receipt['selection'] = selection
    write(destination/'PREPARE_RESULT.json', receipt)
    write(destination/'PREPARED_REUSE.json', dict(status='COMPLETE_PREPARED_REUSED', previous_job='180670',
        source=str(source), source_receipt_sha256=checked['files']['PREPARE_RESULT.json'],
        source_selection_sha256=checked['files']['selection/SELECTION.json'], files=copied,
        derived_prepare_sha256=sha(destination/'PREPARE_RESULT.json'),
        derived_selection_sha256=sha(destination/'selection/SELECTION.json'),
        snapshots=checked['snapshots'], paths_explicitly_relocated=True,
        independent_selection_replay_before_encoding=True, model_forwards=0, raw_decodes=0,
        excluded=['encoded', 'selection_replay', 'chronological.pcapng', 'contexts_1.sqlite', 'contexts_2.sqlite']))
    return dict(status='COMPLETE_PREPARED_REUSED', references=checked['references'], queries=checked['queries'],
                snapshots=checked['snapshots'], source_receipt_sha256=checked['files']['PREPARE_RESULT.json'])
