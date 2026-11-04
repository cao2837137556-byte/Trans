"""Generate review drafts from frozen evidence. Never authorizes or submits."""
import json
from pathlib import Path

from checkpoint import atomic_json, require, sha
from streaming import ROOT
from worker import SELECTION_SHA

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    base = ROOT/'runs/edge_external_test1_engineering_v1_20261103/ENGINEERING_CARD_R2.json'
    old = read(base)
    regression_path = HERE/'LOCAL_REGRESSION_RECEIPT.json'
    regression = read(regression_path)
    require(regression['status'] == 'PASS' and regression['tests'] >= 79, 'REPAIR_REGRESSION_REQUIRED')
    require(regression['source_sha256'] == {p.name: sha(p) for p in HERE.glob('*.py')},
            'REPAIR_TESTED_SOURCE_IDENTITY')
    pins = dict(old['artifact_pins'])
    for relative, expected in pins.items():
        require(sha(ROOT/relative) == expected, 'EXISTING_FROZEN_PIN:'+relative)
    selection = ROOT/'runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json'
    require(sha(selection) == SELECTION_SHA, 'SELECTION_SEAL')
    seal = read(selection)
    inputs = [selection, ROOT/seal['references']['source_path'], base]
    inputs += [selection.parent/spec['selected_file'] for spec in seal['roles'].values()]
    source_cal = ROOT/'runs/c5_kernel_independent_replay_codex_20261102/source_cal'
    inputs += [source_cal/name for name in ('CAL_FIXED_INPUTS.npz', 'CAL_FIXED_INPUTS.npz.sha256',
                                          'CAL_E3.npy', 'CAL_E3.npy.sha256')]
    census = HERE/'POPULATION_TEMPORAL_CENSUS.json'
    inputs.append(census)
    inputs.append(ROOT/'runs/edge_preflight_io_repair_v1_20261103/replay_io.py')
    encoder_root = ROOT/'runs/history_normal_reference_keyrepair_v1_20261031'
    inputs += [encoder_root/name for name in ('config/EXECUTION.json', 'config/ENCODER_RUNTIME_FILES.json',
                                            'hnr/encoding.py', 'hnr/common.py')]
    # The full base and exact Python inventories close transitive dependencies.
    source_files = [p for p in HERE.glob('*.py') if not p.name.startswith('test_')]
    for path in inputs+source_files:
        pins[path.relative_to(ROOT).as_posix()] = sha(path)
    measured = read(ROOT/'runs/edge_preflight_io_repair_v1_20261103/LINUX_RUNTIME_IDENTITY_181418.json')
    runtime = dict(system=measured['system'], python=measured['python'],
        versions=measured['versions'], tshark_first_line=measured['tshark_version'].splitlines()[0])
    from dependency_identity import build
    envelope, dependency_pins = build()
    for relative, digest in dependency_pins.items():
        require(relative not in pins or pins[relative] == digest, 'DEPENDENCY_PIN_CONFLICT:'+relative)
    pins.update(dependency_pins)
    # Conservative all-input envelope: v1 spools cannot be silently adopted.
    # Engineering and formal v2 cards share the same scientific binding.
    common_input_pins = dict(pins)
    pins[regression_path.relative_to(ROOT).as_posix()] = sha(regression_path)
    review_path = ROOT/'runs/edge_formal_review_experiment11_20261103/REVIEW.json'
    pins[review_path.relative_to(ROOT).as_posix()] = sha(review_path)
    shared = dict(schema='EDGE_FORMAL_EXECUTION_REVIEW_CARD_V2', dependency_envelope=envelope,
        C5_method_freeze_sha256=old['C5_method_freeze_sha256'], selection_seal_sha256=SELECTION_SHA,
        population=dict(sealed=True, selected_role_counts={k: s['selected_rows'] for k, s in seal['roles'].items()},
                        known_populations={k: s['population_count'] for k, s in seal['roles'].items()},
                        reference_rows=seal['references']['rows']),
        baselines=old['baselines'], runtime_identity=runtime,
        same_runtime_preflight=dict(status='REAL_SLICE_E2E_PASS', job_id='181418',
            runtime_identity=runtime, scope='OLD_TINY_FIXTURE_NOT_NEW_WORKER_RECOVERY'),
        formal_worker_linux_recovery=dict(status='PENDING'), independent_review=dict(status='PASS', reviewer='CODEX_EXPERIMENT11_USER_ASSIGNED',
            scope='V1 cross-chat review findings repaired and locally regression-checked by same assigned reviewer; not a second independent review of v2',
            original_review=dict(path=review_path.relative_to(ROOT).as_posix(), sha256=sha(review_path)),
            repair_regression=dict(path=regression_path.relative_to(ROOT).as_posix(), sha256=sha(regression_path)),
            previous_v1_review='CHANGES_REQUESTED_BEFORE_ENGINEERING_GATE',
            next_independent_review='ANTIGRAVITY'),
        full_streaming_resume_worker='LOCAL_SYNTHETIC_PASS_LINUX_FROZEN_RECOVERY_PENDING',
        scientific_input_artifact_pins=common_input_pins, artifact_pins=pins,
        population_census=dict(path=census.relative_to(ROOT).as_posix(), sha256=sha(census)),
        training_authorized=False, formal_external_evaluation_authorized=False,
        no_quality_based_query_or_dataset_selection=True,
        methods=['RAW', 'C5_P3', 'C5_P1', 'STANDARD_KNN5'],
        reporting=dict(selected_sample_ratio=True, normal_component_equal=True,
            known_N_HT_estimate=True, unselected='NOT_SAMPLED', NORMAL_FULL='NOT_EVALUABLE',
            HTTP_ACK_PSH_and_UDP_separate=True, temporal_block_seconds=60,
            repetitions=2000, seed=20261103, independent_event_recall='NOT_EVALUABLE'),
        storage='HPC personal/project directory; return only small receipts and summary to local disk')
    formal = dict(shared, status='DRAFT_BLOCKED_PENDING_LINUX_RECOVERY_BUDGET_AND_AUTHORIZATION',
        execution_card_frozen=False, execution_ready=False,
        budget=dict(cpu=1, rss_bytes=None, disk_bytes=None, scratch_bytes=None, wall_seconds=None,
            encoding_rows=64124, distance_pairs=324756408,
            automatic_extension=False, automatic_resubmit=False),
        budget_evidence=dict(path=(HERE/'MEASURED_BUDGET.json').relative_to(ROOT).as_posix(),
            sha256=sha(HERE/'MEASURED_BUDGET.json'),
            status='SCENARIOS_NOT_A_CERTIFIED_BOUND', largest_certified_K=None),
        blockers=['New worker same-runtime frozen-model kill/restart gate pending',
                  'UDP full-prefix/late RSS, full shape batch16 and large-bank throughput pending',
                  '24h budget/common K decision pending, preserve original20k seal',
                  'Bound user formal-evaluation authorization pending'])
    engineering = dict(shared, schema='EDGE_FORMAL_WORKER_ENGINEERING_GATE_CARD_V2',
        status='REVIEW_DRAFT_NOT_AUTHORIZED', execution_ready=False,
        scope='EDGE_FORMAL_WORKER_ENGINEERING_GATE', external_quality_allowed=False,
        model_fitting_allowed=False, external_scores_or_decisions_allowed=False,
        budget=dict(cpu=1, rss_bytes=8*1024**3, disk_bytes=24*1024**3,
            scratch_bytes=24*1024**3, scratch_reservation_bytes=32*1024**3,
            wall_seconds=7200, automatic_extension=False, automatic_resubmit=False),
        actions=['Exact sealed complete-role causal snapshot replay; persist bounded packed spools',
                 'All selected shapes: first min(16,shape_count) UID, singleton physical16 clones',
                 'Two deterministic real frozen batches: uninterrupted vs child-kill/restart byte equality',
                 'Saved source CAL16 E3/q14: cached heads vs old engine and original saved outputs',
                 'Fixed-seed synthetic reference/query large-bank distance microbenchmark',
                 'Measure stage time, actual processed raw prefixes, late RSS and scratch high water'],
        acceptance='All engineering gates pass; no external detection quality retained or used',
        stop='Preserve committed outputs; no automatic extension or resubmission')
    for name, value in (('FORMAL_EXECUTION_CARD_DRAFT.json', formal),
                        ('ENGINEERING_GATE_CARD_DRAFT.json', engineering)):
        target = HERE/name
        atomic_json(target, value)
        target.with_name(name+'.sha256').write_text(sha(target)+'  '+name+'\n', encoding='utf-8')
    print(json.dumps(dict(status='DRAFTS_GENERATED_NOT_AUTHORIZED',
        formal_card_sha256=sha(HERE/'FORMAL_EXECUTION_CARD_DRAFT.json'),
        engineering_card_sha256=sha(HERE/'ENGINEERING_GATE_CARD_DRAFT.json'),
        artifact_pins=len(pins), model_calls=0, cloud_jobs_submitted=0)))


if __name__ == '__main__':
    main()
