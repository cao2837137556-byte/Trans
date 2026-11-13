"""D runs with the real-slice gate. The later job evaluates M, C0 and conditionally C1."""
import argparse
import gc
import math
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic
import traceback

import numpy as np

from common_round1 import (HERE, NUMPY_RUNTIME, PYTHON, ROOT, TOL, Inputs, Progress,
                           config_at, dump, load, require, sha, uid_sha, verify_package,
                           verify_runtime_paths)
from evaluation import (baseline, compare_candidate, correction, diagnosis,
                        load_queries, parity, subset)
from reference_inputs import (cardinality, deduplicate, groups_for_c1, load_references,
                              normalized_context, read_candidate, seal, select_m)
from replay_geometry import choose_representatives, plan_queries, radii, replay
from vendor import constrained_onboarding_core_v3 as core, fast_geometry, geometry_frozen

REF_ROLES = ('reference',)
EVAL_ROLES = ('reference', 'query')
def stores(project, roles, progress=None):
    return Inputs(project, load(HERE / 'INPUT_PINS.json'), roles, progress=progress)


def check_assets(store, out, phase, names=None):
    result = store.verify(names)
    dump(out / ('INPUT_VERIFICATION_' + phase + '.json'), result)
    require(result['status'] == 'PASS', 'MISSING_OR_DIFFERENT_PINNED_ASSET:' + ','.join(result['failures']))
    return result


def selection_fence(project, out, store, phase):
    """Reject even an accidental direct query open in a selector process."""
    project = project.resolve()
    allowed = {path.resolve() for path in store.allowed_paths()}
    allowed.update((HERE / name).resolve() for name in
                   ('CONFIG.json', 'INPUT_PINS.json', 'PACKAGE_MANIFEST.json', 'LOCAL_REFERENCE_AUDIT.json'))
    candidate_receipts = {
        'select-m-c0': ('M_UIDS.jsonl.gz', 'C0_UIDS.jsonl.gz', 'C0_REPRESENTATIVES.jsonl.gz'),
        'select-c1': ('C0_SEAL.json', 'C0_UIDS.jsonl.gz', 'C0_REPRESENTATIVES.jsonl.gz', 'C0_RELEASE.json',
                      'C1_CARDINALITY.json', 'C1_UIDS.jsonl.gz', 'C1_REPRESENTATIVES.jsonl.gz'),
    }
    allowed.update((out / name).resolve() for name in candidate_receipts[phase])

    def check(event, args):
        if event != 'open' or isinstance(args[0], int):
            return
        lexical = Path(os.path.abspath(os.fsdecode(args[0])))
        path = lexical.resolve()
        if path in allowed or (not lexical.is_relative_to(project) and not path.is_relative_to(project)):
            return
        if path.parent == out and (args[2] & (os.O_WRONLY | os.O_RDWR)):
            return
        if path.suffix in ('.py', '.pyc') and (
            path.is_relative_to(HERE) or path.is_relative_to((project / NUMPY_RUNTIME).resolve())
        ):
            return
        raise PermissionError('SELECTOR_INPUT_ROLE_DENIED:' + path.name)

    sys.addaudithook(check)


def selection(project, out, phase, config, package_sha, progress):
    store = stores(project, REF_ROLES, progress)
    selection_fence(project, out, store, phase)
    verified = check_assets(store, out, phase)
    assets = progress.stage('LOAD_REFERENCE_ONLY', lambda: load_references(store, config))
    if phase == 'select-m-c0':
        indices, quotas = select_m(assets.rows, assets.dense_count, config)
        m_sha = uid_sha([assets.rows[i]['uid'] for i in indices])
        require(m_sha == load(HERE / 'LOCAL_REFERENCE_AUDIT.json')['m_reference_uid_sha256'],
                'M_REFERENCE_ONLY_LOCAL_HPC_IDENTITY')
        seal(out, 'M', assets, indices, None, verified, package_sha, dict(
            quotas=quotas, salt=config['m']['salt'], source_counts=dict(dense=10011, history=3236)))
        try:
            kept, parent = progress.stage('C0_EXACT_GROUPS', lambda: deduplicate(assets))
            count = len(kept)
            require(count == config['c0']['rows'],
                    f'C0_STRICT_EQUIVALENCE_COUNT_MISMATCH:{count}:{config["c0"]["rows"]}')
            require(np.array_equal(kept[:assets.dense_count], np.arange(assets.dense_count)),
                    'C0_DENSE_RETENTION')
            mapping = {i: int(rep) for i, rep in enumerate(parent)}
            seal(out, 'C0', assets, kept, mapping, verified, package_sha, dict(
                exact_raw_feature_dtype_and_value=True, eligibility_proof='static per-member signature',
                full_dense_rows_retained=assets.dense_count, history_rows=count - assets.dense_count))
        except Exception as exc:
            dump(out / 'C0_CONSTRUCTION_STOP.json',
                 dict(status='FAIL', expected=config['c0']['rows'], reason=str(exc),
                      traceback=traceback.format_exc()))
    else:
        released = load(out / 'C0_RELEASE.json')
        require(released == {'status': 'PASS', 'c0_seal_sha256': sha(out / 'C0_SEAL.json')},
                'C1_NEEDS_C0_RELEASE')
        ix, _ = read_candidate(out, 'C0', assets, package_sha)
        groups = groups_for_c1(assets, ix)
        counts = cardinality(assets, groups)
        dump(out / 'C1_CARDINALITY.json', counts)
        print('C1_EXACT_ROWS', counts['total'], 'HISTORY', counts['history'],
              'GROUPS', counts['groups'], 'ODD', counts['odd_groups'], flush=True)
        require(config['c1']['expected_low'] <= counts['total'] <= config['c1']['expected_high'],
                'C1_CONDITIONAL_SIZE_RANGE')
        normalized = normalized_context(assets.raw_context, assets.context_norm)
        selected, mapping, pair_count = progress.stage('C1_FARTHEST_FIRST', lambda:
            choose_representatives(assets, groups, normalized, config, progress))
        require(len(selected) == counts['total'] and set(mapping) == set(ix) and
                pair_count <= counts['max_pair_computations'], 'C1_GROUP_QUOTA_OR_MAPPING')
        seal(out, 'C1', assets, selected, mapping, verified, package_sha, dict(
            cardinality_sha256=sha(out / 'C1_CARDINALITY.json'), reference_pairs=pair_count,
            full_dense_rows_retained=assets.dense_count, c0_seal_sha256=released['c0_seal_sha256']))


def selector_subprocess(project, out, phase):
    subprocess.run([sys.executable, '-X', 'utf8', '-B', str(HERE / 'worker.py'), phase,
                    '--project', str(project), '--out', str(out)], check=True)


def select_probe(d, full_bank, config):
    plans, flags = plan_queries(full_bank, d['rows'], config)
    selected = set()
    for patterns in plans.values():
        for query_ix in patterns.values():
            ordered = sorted(query_ix, key=lambda i: d['ids'][i])
            # Selection uses the reference policy and fixed UID order only.
            count = min(len(ordered), config['resource']['sample_per_pattern'])
            selected.update(ordered[i] for i in np.linspace(0, len(ordered) - 1, count, dtype=int))
    closed = np.flatnonzero(flags['opening'] != '')
    selected.update(int(i) for i in closed[:24])
    require(len(selected) >= 100 and len(closed) > 0, 'REAL_SLICE_COVERAGE')
    return np.asarray(sorted(selected)), plans


def geometry_parity(actual, saved, d, method, name):
    results = {k: parity(actual[k], saved[k], d['ids']) for k in ('support2', 'support3')}
    require(all(v['nonfinite_left'] == v['nonfinite_right'] == v['above_tolerance_values'] == 0
                for v in results.values()), 'SAVED_SUPPORT_PARITY:' + name)
    reconstructed = correction(d, actual['support3'], method)
    a = parity(reconstructed, d['scores'][name], d['ids'])
    flips = int(np.count_nonzero((reconstructed > method['cuts']) != (d['scores'][name] > method['cuts'])))
    require(a['above_tolerance_values'] == flips == 0, 'DISTANCE_SCORE_DECISION_PARITY:' + name)
    return dict(support=results, scores=a, decision_differences=flips)


def real_probe(d, assets, ref_context, config, progress, out):
    indices, plans = select_probe(d, assets.full_bank, config)
    tiny = subset(d, indices)
    baseline_result = baseline(tiny, (), (), config, real_slice=True)
    observed = {}
    actual_geo = {}
    for label, bank, rc in [('P4_MAIN', assets.full_bank, ref_context),
                            ('P4_COMMISSION_3D', assets.dense_bank, ref_context[:assets.dense_count])]:
        frozen = fast_geometry.evaluate(tiny, bank.rows, assets.z[:len(bank.rows)], assets.q[:len(bank.rows)],
                                        rc, assets.norm, config['geometry'], config['context_radii'],
                                        core, progress)
        # Both legacy evaluators see the same ordered subset. Comparing donor UIDs
        # against a different GEMM batch shape would confuse numerical ties with drift.
        with_oracle = dict(tiny, support=frozen[0]['support'])
        oracle = geometry_frozen.evaluate(with_oracle, bank.rows, assets.z[:len(bank.rows)],
                                         assets.q[:len(bank.rows)], rc, assets.norm,
                                         config['geometry'], config['context_radii'], core, progress)
        audited = fast_geometry.compare(oracle, frozen)
        current = replay(tiny, bank, rc, config, progress, 'REAL_REPLAY_' + label, auxiliary=True)
        actual_geo[label] = current
        require(np.array_equal(current['legal_component_count'], frozen[0]['legal_component_count']),
                'REAL_COMPONENT_QUALIFICATION_PARITY')
        observed[label] = dict(timing=current['timing'], frozen_oracle=audited,
            current_to_production=geometry_parity(current, dict(support2=frozen[0]['support'], support3=frozen[1]),
                                                 tiny, config['method'], label),
            current_to_archived=geometry_parity(current, tiny['saved'][label], tiny, config['method'], label))
        del current, oracle, frozen, with_oracle
    # Exercise the D single-component implementation on the real slice independently.
    current = actual_geo['P4_COMMISSION_3D']
    one = (current['legal_component_count'] == 1) & current['geometry_ready']
    require(one.any(), 'REAL_SINGLE_COMPONENT_COVERAGE')
    checked = replay(tiny, assets.dense_bank, ref_context[:assets.dense_count], config,
                     progress, 'REAL_SINGLE_COMPONENT', single_mask=one)
    one_indices = np.flatnonzero(one)
    probe_one = one_indices[np.linspace(0, len(one_indices) - 1, min(12, len(one_indices)), dtype=int)]
    for i in probe_one:
        row = tiny['rows'][i]
        k = row['partition'], row['device'], row['protocol']
        ri = [j for j in assets.dense_bank.groups[k]
              if assets.dense_bank.rows[j]['capture_id'] != row['capture_id'] or
              assets.dense_bank.rows[j]['frame'] < row['frame']]
        zq, rho = radii(config, k[-1])
        query_z = core._unit(tiny['z'][i:i + 1], assets.norm)[0]
        dz = np.clip(1. - assets.dense_bank.z[ri] @ query_z, 0., 2.)
        dq = geometry_frozen.rms(tiny['q'][i:i + 1], assets.dense_bank.q14[ri])[0]
        dc = geometry_frozen.rms(tiny['context'][i:i + 1], ref_context[ri])[0]
        expected = np.clip(1. - np.maximum.reduce((core._ratio(dz, zq[0]), core._ratio(dq, zq[1]),
                                                   core._ratio(dc, rho))).min(), 0., 1.)
        require(abs(expected - checked['single'][i]) <= TOL, 'REAL_SINGLE_COMPONENT_ORACLE')
    groups = observed['P4_MAIN']['timing']['groups']
    sampled = {tuple(r['key']): r for r in groups}
    estimates = []
    for k, patterns in plans.items():
        work = sum(len(legal) * len(ii) for legal, ii in patterns.items()
                   if len({assets.full_bank.rows[j]['component_id'] for j in legal}) >= 2)
        item = sampled[k]
        require(work == 0 or item['pairs'] > 0, 'REAL_FORECAST_GROUP_COVERAGE')
        projected = item['seconds'] * max(1., work / max(1, item['pairs']))
        estimates.append(dict(key=list(k), full_pairs=work, sample_pairs=item['pairs'],
                              sample_seconds=item['seconds'], projected_seconds=projected))
    status = dict(status='PASS', actual_compute_node=os.environ.get('SLURMD_NODENAME'),
                  slurm_job_id=os.environ.get('SLURM_JOB_ID'), rows=len(indices),
                  uid_sha256=uid_sha(tiny['ids'].tolist()),
                  input='frozen cached arrays; real UID/feature/geometry/p4/decision/metric/receipt',
                  baseline=baseline_result, geometry=observed,
                  single_component_oracle_rows=len(probe_one),
                  forecast_groups=estimates,
                  memory_kib=progress.sample())
    dump(out / 'REAL_PREFLIGHT.json', status)
    require(load(out / 'REAL_PREFLIGHT.json') == status, 'REAL_PREFLIGHT_RECEIPT_READBACK')
    return status


def sizing(probe, full_dense, config, progress, elapsed_first):
    resource = config['resource']
    estimate = probe['geometry']['P4_MAIN']['timing']['setup_seconds'] + sum(
        x['projected_seconds'] for x in probe['forecast_groups'])
    # Each candidate's pair set is bounded by the full bank. The extra margin
    # includes reference-only C1 selection, output writing, and hashing.
    full_dense_seconds = sum(g['seconds'] for g in full_dense['timing']['groups'])
    per_candidate_seconds = max(estimate, full_dense_seconds)
    # The pre-deduplication group count bounds the eventual C1 selection work.
    # Use the slowest measured real group per pair, then add startup and I/O headroom.
    pair_seconds = max(g['sample_seconds'] / g['sample_pairs']
                       for g in probe['forecast_groups'] if g['sample_pairs'] > 0)
    selection_seconds = pair_seconds * resource['history_pair_upper_bound']
    forecast = 1.75 * (3 * per_candidate_seconds + selection_seconds) + 420
    seconds = max(1200, 300 * math.ceil((forecast / resource['forecast_margin_fraction']) / 300))
    memory_mib = max(4096, 1024 * math.ceil((1.6 * progress.sample() / 1024 + 768) / 1024))
    result = dict(status='PASS' if seconds <= resource['eval_max_wall_seconds'] and
                  memory_mib <= resource['eval_max_memory_mib'] else 'STOP',
                  first_elapsed_seconds=elapsed_first, first_peak_rss_kib=progress.sample(),
                  dense_measured_distance_seconds=full_dense_seconds,
                  projected_one_full_bank_seconds=estimate,
                  c1_selection_pair_upper_bound=resource['history_pair_upper_bound'],
                  c1_projected_pair_seconds=selection_seconds,
                  conservative_eval_seconds=forecast, eval_wall_seconds=seconds, eval_memory_mib=memory_mib,
                  partition=resource['partition'], cpus=1, distance_chunk_pairs=core.PAIR_BUDGET,
                  memory_formula='ceil GiB of max(4 GiB, 1.6 x measured peak + 768 MiB)',
                  time_formula='3 full-bank upper budgets and C1 selection projection, 1.75x plus 420s; 68% allocation gate')
    return result


def first_phase(project, out, config, package_sha, progress):
    selector_subprocess(project, out, 'select-m-c0')
    store = stores(project, EVAL_ROLES, progress)
    check_assets(store, out, 'first')
    assets = progress.stage('LOAD_REFERENCES', lambda: load_references(store, config))
    require(read_candidate(out, 'M', assets, package_sha)[1]['rows'] == 13247,
            'M_SEAL_BEFORE_QUERY')
    require((out / 'C0_SEAL.json').is_file() or (out / 'C0_CONSTRUCTION_STOP.json').is_file(),
            'C0_SELECTION_NOT_RECORDED')
    d = progress.stage('LOAD_QUERIES', lambda: load_queries(store, config, assets))
    rc = normalized_context(assets.raw_context, assets.context_norm)
    expected = load(HERE / 'evidence' / 'BASELINE_EXPECTED.json')
    probe = progress.stage('REAL_INPUT_PREFLIGHT', lambda: real_probe(d, assets, rc, config, progress, out))
    base = progress.stage('FULL_CACHED_BASELINE', lambda:
        baseline(d, expected['metrics'], expected['pairs'], config, output=out))
    cuts = config['method']['cuts']
    single_mask = ((d['scores']['P4_COMMISSION_3D'] > cuts).any(axis=1) & (d['labels'] == 0))
    dense = progress.stage('D_DENSE_REPLAY', lambda:
        replay(d, assets.dense_bank, rc[:assets.dense_count], config, progress,
               'D_DENSE_DISTANCE', single_mask=single_mask, auxiliary=True))
    base.update(dict(reference_identity=assets.identity, query_identity=config['query_identity'],
                     frozen_windows_exact=True, live_support_witness=geometry_parity(
                        dense, d['saved']['P4_COMMISSION_3D'], d, config['method'], 'P4_COMMISSION_3D'),
                     real_slice_full_geometry_verified=True))
    dump(out / 'BASELINE_PARITY.json', base)
    progress.stage('D_DIAGNOSIS', lambda: diagnosis(d, dense, config, out))
    plan = sizing(probe, dense, config, progress, monotonic() - progress.started)
    dump(out / 'RESOURCE_PLAN.json', plan)
    dump(out / 'FIRST_COMPLETE.json', dict(status='PASS', phase='D', package_manifest_sha256=package_sha,
                                          d_diagnosis_sha256=sha(out / 'D_DIAGNOSIS.json'),
                                          real_gate_sha256=sha(out / 'REAL_PREFLIGHT.json'),
                                          baseline_sha256=sha(out / 'BASELINE_PARITY.json'),
                                          c0_sealed=(out / 'C0_SEAL.json').is_file(),
                                          resource_plan_status=plan['status'],
                                          slurm_job_id=os.environ['SLURM_JOB_ID']))
    progress('D_COMPLETE', 1, 1, force=True)


def candidate_slice(d, bank, rc, config, stage, progress):
    """Compare the actual candidate to a direct production-based oracle before full replay."""
    plans, flags = plan_queries(bank, d['rows'], config)
    selected = set(np.flatnonzero(flags['opening'] != '')[:8].tolist())
    for patterns in plans.values():
        for ix in patterns.values():
            selected.update(ix[j] for j in np.linspace(0, len(ix) - 1, min(len(ix), 12), dtype=int))
    tiny = subset(d, np.asarray(sorted(selected)))
    geo = replay(tiny, bank, rc, config, progress, stage + '_REAL_SLICE')
    ids = tiny['ids'].tolist()
    expected = bank.own(tiny['rows'], tiny['z'], tiny['q'], config['geometry'],
                        feature_uids=ids, q_uids=ids)
    require(np.array_equal(expected['legal_component_count'], geo['legal_component_count']),
            'CANDIDATE_REAL_SLICE_ELIGIBILITY:' + stage)
    p2 = parity(geo['support2'], expected['support'], tiny['ids'])
    require(p2['above_tolerance_values'] == 0, 'CANDIDATE_REAL_SLICE_SUPPORT2:' + stage)
    p3 = np.zeros(len(ids))
    for i, r in enumerate(tiny['rows']):
        zq, rho = radii(config, r['protocol'])
        if not expected['eligible'][i] or expected['support'][i] == 0 or rho is None:
            continue
        ri = np.asarray([j for j in bank.groups[(r['partition'], r['device'], r['protocol'])]
                         if bank.rows[j]['capture_id'] != r['capture_id'] or bank.rows[j]['frame'] < r['frame']])
        z = core._unit(tiny['z'][i:i + 1], bank.normalizer)[0]
        dz = np.clip(1. - z @ bank.z[ri].T, 0., 2.)
        dq = geometry_frozen.rms(tiny['q'][i:i + 1], bank.q14[ri])[0]
        dc = geometry_frozen.rms(tiny['context'][i:i + 1], rc[ri])[0]
        joint = np.maximum.reduce((core._ratio(dz, zq[0]), core._ratio(dq, zq[1]), core._ratio(dc, rho)))
        comp = [bank.rows[j]['component_id'] for j in ri]
        second, _ = core._second_distinct(joint[None, :], comp)
        p3[i] = np.clip(1. - second[0], 0., 1.)
    p3_error = parity(geo['support3'], p3, tiny['ids'])
    cuts = config['method']['cuts']
    score = correction(tiny, geo['support3'], config['method'])
    expected_scores = correction(tiny, p3, config['method'])
    score_error = parity(score, expected_scores, tiny['ids'])
    flips = int(np.count_nonzero((score > cuts) != (expected_scores > cuts)))
    require(p3_error['above_tolerance_values'] == score_error['above_tolerance_values'] == flips == 0,
            'CANDIDATE_REAL_SLICE_SUPPORT3_OR_SCORE:' + stage)
    return dict(status='PASS', rows=len(ids), support2=p2, support3=p3_error, scores=score_error, flips=flips)


def evaluation_phase(project, out, config, package_sha, progress):
    first = load(out / 'FIRST_COMPLETE.json')
    require(first['status'] == 'PASS' and first['package_manifest_sha256'] == package_sha and
            first['baseline_sha256'] == sha(out / 'BASELINE_PARITY.json') and
            first['real_gate_sha256'] == sha(out / 'REAL_PREFLIGHT.json') and
            first['d_diagnosis_sha256'] == sha(out / 'D_DIAGNOSIS.json'), 'PRIOR_STAGE_IDENTITY')
    require(load(out / 'RESOURCE_PLAN.json')['status'] == 'PASS', 'RESOURCE_PLAN_REQUIRED')
    store = stores(project, EVAL_ROLES, progress)
    check_assets(store, out, 'eval')
    assets = progress.stage('EVAL_LOAD_REFERENCES', lambda: load_references(store, config))
    m, m_seal = read_candidate(out, 'M', assets, package_sha)
    c0 = None
    if first['c0_sealed']:
        try:
            c0, c0_seal = read_candidate(out, 'C0', assets, package_sha)
        except Exception as exc:
            dump(out / 'C0_EVALUATION_STOP.json', dict(status='FAIL', reason=str(exc),
                                                      traceback=traceback.format_exc()))
    rc = normalized_context(assets.raw_context, assets.context_norm)
    d = progress.stage('EVAL_LOAD_QUERIES', lambda: load_queries(store, config, assets))
    dense_flags = plan_queries(assets.dense_bank, d['rows'], config)[1]
    full_flags = plan_queries(assets.full_bank, d['rows'], config)[1]
    result = {}

    def evaluate_one(name, ids, seal_info):
        bank = assets.bank(ids, retain_omitted_capture_cutoffs=name == 'M')
        require((name == 'M' or set(bank.groups) == set(assets.full_bank.groups)) and
                seal_info['ends'] == [list(k) + [v] for k, v in sorted(bank.ends.items())] and
                seal_info['frame_ends'] == [list(k) + [v] for k, v in sorted(bank.frame_ends.items())],
                'SEALED_BANK_FRAME_MAPPING:' + name)
        context = rc[ids]
        dump(out / (name + '_REAL_SLICE.json'),
             progress.stage(name + '_REAL_SLICE', lambda: candidate_slice(d, bank, context, config, name, progress)))
        geo = progress.stage(name + '_FULL_REPLAY', lambda:
            replay(d, bank, context, config, progress, name + '_DISTANCE'))
        common = None
        if name == 'M':
            dense_two = dense_flags['legal_component_count'] >= 2
            m_two = geo['legal_component_count'] >= 2
            common = {'BOTH_DOUBLE_COMPONENT': dense_two & m_two,
                      'M_NEW_DOUBLE_COMPONENT': ~dense_two & m_two}
        else:
            require(np.array_equal(geo['opening'], full_flags['opening']) and
                    np.array_equal(geo['legal_component_count'], full_flags['legal_component_count']),
                    'C0_QUERY_ELIGIBILITY')
        return progress.stage(name + '_REPORT', lambda:
            compare_candidate(d, geo, config, out, name, common=common))

    result['M'] = evaluate_one('M', m, m_seal)
    require(result['M']['status'] == 'PASS', 'M_INVARIANTS')
    if c0 is not None:
        try:
            result['C0'] = evaluate_one('C0', c0, c0_seal)
        except Exception as exc:
            dump(out / 'C0_EVALUATION_STOP.json', dict(status='FAIL', reason=str(exc),
                                                      traceback=traceback.format_exc()))
    gc.collect()
    if result.get('C0', {}).get('status') == 'PASS':
        dump(out / 'C0_RELEASE.json', dict(status='PASS', c0_seal_sha256=sha(out / 'C0_SEAL.json')))
        # The selector process receives only a release bit and reference inputs.
        del d, assets, rc
        gc.collect()
        progress.stage('C1_REFERENCE_ONLY', lambda: selector_subprocess(project, out, 'select-c1'))
        assets = progress.stage('C1_RELOAD_REFERENCES', lambda: load_references(store, config))
        rc = normalized_context(assets.raw_context, assets.context_norm)
        d = progress.stage('C1_RELOAD_QUERIES', lambda: load_queries(store, config, assets))
        ids, seal_info = read_candidate(out, 'C1', assets, package_sha)
        bank = assets.bank(ids)
        require(set(bank.groups) == set(assets.full_bank.groups) and set(ids) <= set(c0) and
                seal_info['ends'] == [list(k) + [v] for k, v in sorted(bank.ends.items())] and
                seal_info['frame_ends'] == [list(k) + [v] for k, v in sorted(bank.frame_ends.items())],
                'C1_SUBSET_OR_POLICY')
        dump(out / 'C1_REAL_SLICE.json', progress.stage('C1_REAL_SLICE', lambda:
            candidate_slice(d, bank, rc[ids], config, 'C1', progress)))
        geo = progress.stage('C1_FULL_REPLAY', lambda:
            replay(d, bank, rc[ids], config, progress, 'C1_DISTANCE'))
        require(np.array_equal(geo['opening'], full_flags['opening']) and
                np.array_equal(geo['legal_component_count'], full_flags['legal_component_count']),
                'C1_QUERY_ELIGIBILITY')
        result['C1'] = progress.stage('C1_REPORT', lambda: compare_candidate(d, geo, config, out, 'C1'))
        require(result['C1']['status'] == 'PASS', 'C1_ENGINEERING_INVARIANTS')
    else:
        dump(out / 'C1_BLOCKED.json', dict(status='BLOCKED', reason='C0_EQUIVALENCE_GATE_NOT_PASSED'))
    dump(out / 'EVAL_COMPLETE.json', dict(status='PASS' if 'C1' in result else 'PARTIAL_C0_FAILED',
        package_manifest_sha256=package_sha, slurm_job_id=os.environ['SLURM_JOB_ID'],
        comparisons={name: dict(status=r['status'], outcome=r['outcome'],
                               numeric_comparison=r['numeric_comparison']) for name, r in result.items()}))
    progress('EVALUATION_COMPLETE', 1, 1, force=True)


def runtime_gate(out, phase, project):
    require(sys.platform.startswith('linux') and os.environ.get('SLURM_JOB_ID', '').isdigit(),
            'ACTUAL_SLURM_COMPUTE_CONTEXT_REQUIRED')
    require(sys.version_info[:2] == (3, 11) and np.__version__ == '2.0.1' and not sys.flags.optimize,
            'FROZEN_LINUX_PYTHON_NUMPY')
    require(Path(sys.executable).resolve() == PYTHON.resolve() and
            Path(np.__file__).resolve().is_relative_to((project / NUMPY_RUNTIME).resolve()),
            'FROZEN_RUNTIME_MODULE_IDENTITY')
    require(np.isfinite(np.array([[1., 2.]]) @ np.array([[3.], [4.]])).all(), 'BLAS_RUNTIME')
    dump(out / ('RUNTIME_' + phase + '.json'), dict(status='PASS', python=sys.version,
        executable=sys.executable, numpy_version=np.__version__, numpy_path=np.__file__,
        node=os.environ.get('SLURMD_NODENAME'), slurm_job_id=os.environ['SLURM_JOB_ID'],
        omp_threads=os.environ.get('OMP_NUM_THREADS'), package_manifest_sha256=sha(HERE / 'PACKAGE_MANIFEST.json'),
        runtime_source_hashes=verify_runtime_paths(project)))


def main():
    args = argparse.ArgumentParser()
    args.add_argument('phase', choices=('first', 'eval', 'select-m-c0', 'select-c1'))
    args.add_argument('--project', type=Path, default=ROOT)
    args.add_argument('--out', type=Path, required=True)
    a = args.parse_args()
    out = a.out.resolve()
    phase = a.phase
    config = config_at()
    limit = int(os.environ.get('ROUND1_MEMORY_MIB', '8192'))
    progress = Progress(out, phase, rss_limit_mib=limit - 384)
    try:
        if phase.startswith('select-'):
            selection(a.project, out, phase, config, sha(HERE / 'PACKAGE_MANIFEST.json'), progress)
        else:
            verify_package(HERE)
            runtime_gate(out, phase, a.project)
            fn = first_phase if phase == 'first' else evaluation_phase
            fn(a.project, out, config, sha(HERE / 'PACKAGE_MANIFEST.json'), progress)
        progress.finish()
    except Exception as exc:
        dump(out / ('STOP_' + phase + '.json'), dict(status='FAIL', phase=phase,
             stage=getattr(progress, 'current', 'STARTUP'), error=str(exc), traceback=traceback.format_exc()))
        raise


if __name__ == '__main__':
    main()
