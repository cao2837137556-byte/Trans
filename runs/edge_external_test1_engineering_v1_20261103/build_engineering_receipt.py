"""Seal completed preparation and explicit blockers; never marks a failed E2E ready."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from execution_gate import readiness


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 2**20), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    if path.exists():
        raise RuntimeError('NO_OVERWRITE_RECEIPT:' + str(path))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')


def main():
    frozen = ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'
    expected = 'ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7'
    if sha(frozen) != expected:
        raise RuntimeError('C5_CHANGED')
    seal = read(HERE / 'adapter/population_sealed_v1/POPULATION_SEAL.json')
    pop = seal['population']
    counts = {k: v['counts']['eligible'] for k, v in pop['roles'].items()}
    all_rows = sum(counts.values())
    # Exact protocol populations from the independently raw-header checked census.
    nq_tcp, nq_udp = 1217724, 2402
    ref_tcp, ref_udp = 4096, 28
    one_pass_pairs = (nq_tcp + counts['HTTP']) * ref_tcp + (nq_udp + counts['UDP']) * ref_udp
    budget = dict(status='STATIC_COUNTS_ONLY_NOT_AN_APPROVED_RUNTIME_BUDGET',
        legal_full_query_rows=all_rows,
        legal_primary_query_rows=1220126 + counts['HTTP'] + counts['UDP'],
        reference_rows=4124, reference_UIDs_already_in_full_queries=True,
        extra_reference_rows_not_to_double_count=0,
        reference_rows_currently_encoded=0,
        e3_float32_bytes_without_input_dedup=all_rows * 768 * 4,
        q14_float32_bytes=all_rows * 14 * 4,
        one_full_postbank_same_protocol_distance_pass_upper=one_pass_pairs,
        C5_plus_KNN_distance_pair_upper=2 * one_pass_pairs,
        p1_p3_share_support=True, full_primary_share_predictions=True,
        before_bank_uses_RAW_without_reference_distances=True,
        token_input_dedup='NOT_ENABLED_OR_QUALIFIED',
        snapshot_or_query_subsampling='NONE_SELECTED',
        formal_location='Remote personal/project storage; do not materialize full E3 on nearly full local D drive',
        cpu=None, rss_bytes=None, disk_bytes=None, wall_seconds=None,
        automatic_extension=False, automatic_resubmit=False,
        remaining='Need compatible-runtime complete preflight and full streaming/checkpoint worker before fixing defensible resources/ETA.')
    write(HERE / 'RESOURCE_FEASIBILITY.json', budget)
    metrics = dict(status='FIXED_BEFORE_FORMAL_EXTERNAL_SCORES',
        methods=['RAW', 'SAME_BANK_P1_MECHANISM_ABLATION', 'FROZEN_C5_P3', 'STANDARD_KNN5'],
        C5_head_order=['27', '127', '227', 'ensemble'],
        KNN='One distance score, four source-matched operating points; independent detector can add RAW-negative alarms.',
        independent_method_uses_C5_suppression_only_gate=False,
        required_ordered_UID_joins=True,
        views=['full', 'post_window_primary'],
        primary='Same-population per-packet ensemble FPR/attack-associated recall, FP/FN/counts.',
        normal_weight_fields=['device', 'capture_id', 'component_id'],
        attack_weight_fields=['device', 'scenario', 'component_id'],
        allocation='Each present class has unit mass; equal nonempty child mass, rebuild per view, condition for groups.',
        scenario='HTTP/UDP capture groups, not invented independent events.',
        unavailable_event_gate='NOT_EVALUABLE',
        safety='Cumulative RAW TP withdrawal device<=1pp, observed scenario<=5pp; low RAW weighted recall<99% requires zero withdrawal. Four C5 heads/two views reported. No retuning after failure.',
        descriptive_targets=dict(packet_FPR_max=.02, packet_recall_min=.99),
        required_strata=['normal segment/day/protocol', 'HTTP SYN guard', 'HTTP ACK_no_SYN', 'HTTP ACK_only', 'HTTP PSH_ACK', 'HTTP GET/payload', 'UDP'],
        uncertainty='Finite captured-population descriptive rates and segment/scenario tables; no independent-packet/Wilson CI, no claim of independent millions of attacks.',
        unscored=dict(normal=296, attack=0, policy='Report separately by cause; do not count as correct negatives.'),
        fixture_metrics='Engineering schema/count checks only; no quality statistics or individual decisions exported or used to choose method/dataset.')
    write(HERE / 'METRICS_CONTRACT.json', metrics)
    pins = {}
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.md', '.json') and path.name not in ('PROGRESS.md', 'STATUS.json', 'PROGRESS.json', 'SOURCE_PROGRESS.json'):
            pins[path.relative_to(ROOT).as_posix()] = sha(path)
    pins[frozen.relative_to(ROOT).as_posix()] = expected
    # A freeze document's unchanged SHA alone is not a recheck of its inputs.
    # Verify all already-pinned immutable assets, including the numeric core.
    for relative, binding in read(frozen)['immutable_asset_pins'].items():
        actual = sha(ROOT / relative)
        if actual != binding['sha256']:
            raise RuntimeError('IMMUTABLE_ASSET_CHANGED:' + relative)
        pins[relative] = actual
    card = dict(schema='EDGE_TEST1_ENGINEERING_CARD_V1',
        status='ENGINEERING_PARTIAL_COMPATIBLE_RUNTIME_AND_FULL_WORKER_PENDING',
        created_utc=datetime.now(timezone.utc).isoformat(),
        execution_card_frozen=False, execution_ready=False,
        formal_external_evaluation_authorized=False, training_authorized=False,
        current_user_scope='Adapter, baselines, budget, bounded real-slice engineering preflight; ask evaluation authorization after actual readiness.',
        C5_method_freeze_sha256=expected,
        population=dict(sealed=True, counts=counts, unscored_normal=296,
            seal='adapter/population_sealed_v1/POPULATION_SEAL.json',
            sha256=sha(HERE/'adapter/population_sealed_v1/POPULATION_SEAL.json')),
        baselines=dict(source_calibrated=True, standard_knn5=True, all_paper_strong_baselines_complete=False,
            source_calibration_sha256=sha(HERE/'baselines/SOURCE_CALIBRATION.json')),
        runtime_identity=dict(system='Linux', python='3.11.11', numpy='2.0.1', torch='2.5.1', transformers='4.57.3'),
        same_runtime_preflight=dict(status='NOT_RUN_PENDING_COMPATIBLE_ACCESS', runtime_identity=None),
        budget=budget,
        full_streaming_resume_worker='NOT_IMPLEMENTED',
        blockers=['Existing Windows runtime fails strict identical-clone-output gate; keep exact frozen contract.',
                  'Existing Linux/Python3.11 runtime currently inaccessible over independent SSH.',
                  'Full streaming/checkpoint worker and its budget enforcement not yet integrated; no full external arrays or scores.',
                  'Resource ceiling/ETA must be fixed from successful compatible runtime before execution card freeze.'],
        storage='Keep full data remotely; originals remain unchanged locally.',
        artifact_pins=pins)
    write(HERE / 'ENGINEERING_CARD.json', card)
    write(HERE / 'EXECUTION_READINESS.json', readiness(card, ROOT))
    write(HERE / 'SUMMARY.json', dict(status=card['status'], card_sha256=sha(HERE/'ENGINEERING_CARD.json'),
        method_unchanged=True, full_external_evaluations=0, new_training=0, cloud_jobs=0,
        local_real_slice='Attempted; strict encoder clone equality failed; distance/evaluation stages not reached.',
        subscription_check='Built-in browser functional, not logged in; school name/actual entitlement still needed.',
        formal_evaluation_permission_requested=False))


if __name__ == '__main__':
    main()
