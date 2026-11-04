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
    pins = dict(old['artifact_pins'])
    for relative, expected in pins.items():
        require(sha(ROOT/relative) == expected, 'EXISTING_FROZEN_PIN:'+relative)
    selection = ROOT/'runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json'
    require(sha(selection) == SELECTION_SHA, 'SELECTION_SEAL')
    seal = read(selection)
    inputs = [selection, ROOT/seal['references']['source_path']]
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
    # Only direct source files, not local caches, transport or generated cards.
    source_files = [p for p in HERE.glob('*.py') if not p.name.startswith('test_')]
    for path in inputs+source_files:
        pins[path.relative_to(ROOT).as_posix()] = sha(path)
    measured = read(ROOT/'runs/edge_preflight_io_repair_v1_20261103/LINUX_RUNTIME_IDENTITY_181418.json')
    runtime = dict(system=measured['system'], python=measured['python'],
        versions=measured['versions'], tshark_first_line=measured['tshark_version'].splitlines()[0])
    # A stable common binding allows complete snapshot roles from engineering
    # preparation to be reused only with the same code, raw data and runtime.
    common_input_pins = {key: value for key, value in pins.items()
        if key.startswith('repo/ood/') or key.endswith('/edge_adapter.py') or
        key.endswith('/replay_io.py') or key.endswith('/checkpoint.py') or
        key.endswith('/streaming.py') or key.endswith('/worker.py') or
        key.startswith('runs/history_normal_reference_keyrepair_v1_20261031/') or
        key.endswith('/QUERY_SELECTION_SEAL.json') or key.endswith('_SELECTED_QUERIES.jsonl.gz') or
        key.endswith('/REFERENCE_ROWS.jsonl.gz')}
    shared = dict(schema='EDGE_FORMAL_EXECUTION_REVIEW_CARD_V1',
        C5_method_freeze_sha256=old['C5_method_freeze_sha256'], selection_seal_sha256=SELECTION_SHA,
        population=dict(sealed=True, selected_role_counts={k: s['selected_rows'] for k, s in seal['roles'].items()},
                        known_populations={k: s['population_count'] for k, s in seal['roles'].items()},
                        reference_rows=seal['references']['rows']),
        baselines=old['baselines'], runtime_identity=runtime,
        same_runtime_preflight=dict(status='REAL_SLICE_E2E_PASS', job_id='181418',
            runtime_identity=runtime, scope='OLD_TINY_FIXTURE_NOT_NEW_WORKER_RECOVERY'),
        formal_worker_linux_recovery=dict(status='PENDING'), independent_review=dict(status='PENDING_ANTIGRAVITY'),
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
    formal = dict(shared, status='DRAFT_BLOCKED_PENDING_LINUX_RECOVERY_BUDGET_AND_ANTI_REVIEW',
        execution_card_frozen=False, execution_ready=False,
        budget=dict(cpu=1, rss_bytes=None, disk_bytes=None, scratch_bytes=None, wall_seconds=None,
            encoding_rows=64124, distance_pairs=324756408,
            automatic_extension=False, automatic_resubmit=False),
        budget_evidence=dict(path='runs/edge_formal_execution_v1_20261103/MEASURED_BUDGET.json',
            sha256=sha(HERE/'MEASURED_BUDGET.json'),
            status='SCENARIOS_NOT_A_CERTIFIED_BOUND', largest_certified_K=None),
        blockers=['New worker same-runtime frozen-model kill/restart gate pending',
                  'UDP full-prefix/late RSS, full shape batch16 and large-bank throughput pending',
                  '24h budget/common K decision pending, preserve original20k seal',
                  'Independent Antigravity review and bound user formal-evaluation authorization pending'])
    engineering = dict(shared, schema='EDGE_FORMAL_WORKER_ENGINEERING_GATE_CARD_V1',
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
