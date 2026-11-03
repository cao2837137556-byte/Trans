"""Source-only structural audit; no model, mining, target queries or training.

The historical SOURCE_REFS file also contains DEV references. Only its LEARN
partition enters this audit. FIT/CAL identities and all original rows stay fixed.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / 'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022'
FIELDS = ('uid', 'device', 'source_sha256', 'capture_id', 'session_id',
          'component_id', 'timestamp', 'reference_end', 'protocol', 'partition',
          'use', 'label')
OUTER = ('Amcrest Camera', 'Philips Hue Bridge')
FOLDS = (('SimCam', 'Atomi Coffee Maker'), ('ArloQ Camera', 'Globe Lamp'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def validate(row, reference=False):
    missing = [field for field in FIELDS if field not in row]
    require(not missing, 'MISSING_FIELDS:' + ','.join(missing))
    require(row['partition'] == 'LEARN', 'TARGET_ROLE_FORBIDDEN')
    require(row['label'] in (0, 1), 'LABEL')
    require(all(isinstance(row[k], (int, float)) and math.isfinite(row[k])
                for k in ('timestamp', 'reference_end')), 'FINITE_TIME')
    require(all(isinstance(row[k], str) and row[k]
                for k in ('uid', 'device', 'source_sha256', 'capture_id',
                          'session_id', 'component_id')), 'IDENTITY')
    if reference:
        require(row['use'] == 'REFERENCE' and row['label'] == 0,
                'NORMAL_REFERENCE_ONLY')
        require(row['timestamp'] <= row['reference_end'], 'REFERENCE_TIME')
    else:
        require(row['use'] != 'REFERENCE', 'QUERY_USE')
        require(row.get('fit_role') in ('FIT', 'CAL'), 'FIT_CAL_ROLE')


def legal_components(query, refs):
    """Timestamp-only upper bound; frame causality is not checked here."""
    legal = [r for r in refs if r['device'] == query['device']
             and r['protocol'] == query['protocol']
             and r['reference_end'] < query['timestamp']
             and r['uid'] != query['uid']]
    all_components = {r['component_id'] for r in legal}
    different_dependency = {r['component_id'] for r in legal
                   if r['component_id'] != query['component_id']
                   and (r['source_sha256'], r['session_id']) !=
                       (query['source_sha256'], query['session_id'])}
    other_captures = {r['component_id'] for r in legal
                      if r['source_sha256'] != query['source_sha256']
                      and r['component_id'] != query['component_id']}
    return all_components, different_dependency, other_captures


def pilot_support_summary(groups):
    """Summarize existing counters; no new selection, scoring or source pass."""
    summary = []
    for region, devices in (('inner_development', set(FOLDS[0]) | set(FOLDS[1])),
                            ('outer_device_holdout', set(OUTER))):
        for role in ('FIT', 'CAL'):
            for label in (0, 1):
                selected = [g for g in groups if g['device'] in devices
                            and g['role'] == role and g['label'] == label]
                counts = {g['device']: g['support_rows'].get(
                    'with_at_least_two_timestamp_prior_components', 0) for g in selected}
                summary.append(dict(region=region, role=role, label=label,
                    rows=sum(g['rows'] for g in selected),
                    min_two_timestamp_prior_component_rows=sum(counts.values()),
                    min_two_timestamp_prior_component_rows_by_device=counts,
                    devices_with_any_min_two_component_support=sorted(
                        d for d, count in counts.items() if count),
                    devices_without_min_two_component_support=sorted(
                        d for d, count in counts.items() if not count)))
    return summary


def audit(query_rows, references):
    by_bank = defaultdict(list)
    ref_ids = set()
    reference_ends = {}
    for r in references:
        validate(r, reference=True)
        require(r['uid'] not in ref_ids, 'DUPLICATE_REFERENCE_UID')
        ref_ids.add(r['uid'])
        require(reference_ends.setdefault(r['device'], r['reference_end']) ==
                r['reference_end'], 'COMPLETE_DEVICE_BANK_END_MISMATCH')
        by_bank[(r['device'], r['protocol'])].append(r)
    counts, groups = Counter(), {}
    roles_by_dependency, roles_by_component = defaultdict(set), defaultdict(set)
    per_device_captures, per_device_components = defaultdict(set), defaultdict(set)
    missing = Counter()
    ordered_roles = []
    seen_uids = set()
    for r in query_rows:
        validate(r)
        require(r['uid'] not in seen_uids, 'DUPLICATE_QUERY_UID')
        require(r['uid'] not in ref_ids, 'SOURCE_REFERENCE_QUERY_UID_OVERLAP')
        seen_uids.add(r['uid'])
        ordered_roles.append(r['fit_role'])
        role, device = r['fit_role'], r['device']
        counts[role] += 1
        key = (device, role, r['label'])
        a = groups.setdefault(key, {'rows': 0, 'captures': set(),
            'dependencies': set(), 'components': set(), 'activities': set(),
            'protocol_rows': Counter(), 'support_rows': Counter()})
        a['rows'] += 1
        dependency = (r['source_sha256'], r['session_id'])
        a['captures'].add(r['source_sha256'])
        a['dependencies'].add(dependency)
        a['components'].add(r['component_id'])
        a['activities'].add(r.get('activity', 'MISSING'))
        a['protocol_rows'][str(r['protocol'])] += 1
        roles_by_dependency[dependency].add(role)
        roles_by_component[r['component_id']].add(role)
        per_device_captures[device].add(r['source_sha256'])
        per_device_components[device].add(r['component_id'])
        for field in ('activity', 'reference_dependency_stratum',
                      'label_metric_weight_denominator',
                      'balanced_bce_weight_denominator'):
            if field not in r:
                missing[field] += 1
        legal, different_dependency, other = legal_components(r, by_bank[(device, r['protocol'])])
        s = a['support_rows']
        s['with_any_timestamp_prior_component' if legal else 'no_timestamp_prior_component'] += 1
        if len(legal) >= 2:
            s['with_at_least_two_timestamp_prior_components'] += 1
        if legal and not different_dependency:
            s['timestamp_prior_support_only_same_component_or_dependency'] += 1
        if different_dependency:
            s['with_different_dependency_component'] += 1
        if len(different_dependency) >= 2:
            s['with_at_least_two_different_dependency_components'] += 1
        if other:
            s['with_different_capture_component'] += 1
    report_groups = []
    for (device, role, label), a in sorted(groups.items()):
        report_groups.append(dict(device=device, role=role, label=label,
            **{k: len(v) if isinstance(v, set) else dict(v) if isinstance(v, Counter)
               else v for k, v in a.items()}))
    banks = []
    for (device, protocol), rr in sorted(by_bank.items()):
        banks.append(dict(device=device, protocol=protocol, rows=len(rr),
            components=len({r['component_id'] for r in rr}),
            dependency_groups=len({(r['source_sha256'], r['session_id']) for r in rr}),
            captures=len({r['source_sha256'] for r in rr}),
            reference_ends=sorted({r['reference_end'] for r in rr})))
    devices = set(per_device_captures)
    planned = set(OUTER) | set(FOLDS[0]) | set(FOLDS[1])
    outer_caps = set().union(*(per_device_captures[d] for d in OUTER))
    train_caps = set().union(*(per_device_captures[d] for d in devices-set(OUTER)))
    outer_components = set().union(*(per_device_components[d] for d in OUTER))
    train_components = set().union(*(per_device_components[d] for d in devices-set(OUTER)))
    report = dict(schema='learned-onboarding-source-task-audit-v1',
        query_rows=len(ordered_roles), role_rows=dict(counts), reference_rows=len(references),
        devices=sorted(devices), banks=banks, groups=report_groups,
        proposed_pilot_support=pilot_support_summary(report_groups),
        missing_optional_fields=dict(missing),
        fit_cal_dependency_overlap=sum(len(v)>1 for v in roles_by_dependency.values()),
        fit_cal_component_overlap=sum(len(v)>1 for v in roles_by_component.values()),
        proposed_split=dict(outer_holdout_devices=list(OUTER),
            inner_query_folds=[list(f) for f in FOLDS],
            roster_exactly_covered=planned == devices,
            outer_train_capture_overlap=len(outer_caps & train_caps),
            outer_train_component_overlap=len(outer_components & train_components),
            outer_train_device_overlap=0,
            rationale='Specified before target-query selection; structural pilot only.',
            capture_isolation_established=not bool(outer_caps & train_caps)))
    return report, ordered_roles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).with_name('source_task_audit.json'))
    args = parser.parse_args()
    source_refs = []
    excluded = Counter()
    for r in rows(args.cache/'inputs/SOURCE_REFS.jsonl.gz'):
        if r.get('partition') == 'LEARN':
            source_refs.append(r)
        else:
            excluded[str(r.get('partition'))] += 1
    report, roles = audit(rows(args.cache/'inputs/LEARN.jsonl.gz'), source_refs)
    for split in ('FIT', 'CAL'):
        with np.load(args.cache/'inputs'/(split+'.npz'), allow_pickle=False) as z:
            indices = z['indices']
            expected = np.flatnonzero(np.asarray(roles) == split)
            require(indices.dtype == np.int64 and np.array_equal(indices, expected),
                    'FROZEN_SPLIT_INDICES_MISMATCH:'+split)
    features = {}
    for role in ('LEARN', 'SOURCE_REFS'):
        path = args.cache/'features'/(role+'.npy')
        value = np.load(path, mmap_mode='r', allow_pickle=False)
        features[role] = dict(path=str(path.resolve()), shape=list(value.shape),
            dtype=str(value.dtype), feature_interpretation='first 768 columns E3; total 794 includes old state')
        value._mmap.close()
    report.update(status='COMPLETE_STRUCTURAL_AUDIT_ONLY',
        model_training_readiness='NOT_READY_RECIPE_AND_AUXILIARY_HEADS_PENDING',
        support_count_scope='TIMESTAMP_ONLY_STRUCTURAL_UPPER_BOUND_NOT_EXACT_V3_ELIGIBILITY',
        frame_causality_checked=False,
        generated_at=datetime.now(timezone.utc).isoformat(),
        lineage='NEW_RECONSTRUCTION_LINEAGE', parent_parity='PARENT_PARITY_UNAVAILABLE',
        source_inputs={k: str((args.cache/'inputs'/k).resolve())
                       for k in ('LEARN.jsonl.gz', 'SOURCE_REFS.jsonl.gz', 'FIT.npz', 'CAL.npz')},
        excluded_reference_partitions=dict(excluded), feature_headers=features,
        frozen_fit_cal_indices_exact=True, target_query_files_opened=0,
        model_forward_calls=0, optimizer_updates=0, large_feature_rehash=False,
        evidence_limits=[
            'Metadata support counts are availability only, not geometric support or efficacy.',
            'Causal same-component history can be legitimate; different dependency IDs do not establish statistical independence.',
            'Two timestamp-prior components is a structural upper bound, not exact v3 eligibility; same-capture frame and bank-end-frame causality remain unchecked.',
            'Source reference-query UID overlap remains forbidden; the target pre-bank exception is not extended to LEARN.',
            'No query rows are deleted; pre-reference queries must retain base-head decisions.',
            'CAL remains calibration-only and cannot enter fitting or hard-example mining.',
            'Full-FIT heads have seen source devices; auxiliary held-device heads are still required.',
            'Device exclusion at the head/module stage does not establish unseen-device pretraining.',
            'Capture/environment holdout is unestablished when the reported outer/train capture overlap is nonzero.',
            'All six source devices are from the existing source domain; B-like domain coverage is unproven.',
            'No training recipe, hard-example set, model, threshold or target evaluation was produced.',
            'Existing input seals are referenced; this metadata audit does not reverify multi-GB payload hashes.'
        ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'query_rows', 'role_rows',
        'reference_rows', 'fit_cal_dependency_overlap', 'fit_cal_component_overlap',
        'proposed_split')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
