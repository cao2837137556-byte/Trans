"""Seal failed local engineering evidence and after-failure input readback."""
from pathlib import Path

from engine import read, require, sha
from run_preflight import write

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
v1 = read(HERE / 'local_attempt_v1/RESULT.json')
v2 = read(HERE / 'local_diagnostic_v2/RESULT.json')
failure = read(HERE / 'local_diagnostic_v2/CLONE_FAILURE_DIAGNOSIS.json')
inputs = {}
for role, item in v2['raw_input_pins'].items():
    path = Path(item['path'])
    require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'FAILURE_INPUT_READBACK')
    inputs[role] = dict(bytes=item['bytes'], sha256=item['sha256'], unchanged=True)
result = dict(status='ENGINEERING_IMPLEMENTED_LOCAL_E2E_FAILED_FINAL_RUNTIME_PENDING',
    complete_real_slice_e2e_pass=False, strict_clone_gate_changed=False,
    final_linux_gate_pass=False, model_evaluation_authorized=False,
    formal_external_evaluation_started=False, training=False, cloud_jobs_submitted=0,
    local_environment=v2['environment'], slice_sha256=sha(HERE / 'SLICE_CARD.json'),
    slice_logical_endpoints=65, real_decode_descriptor_pass=True,
    local_attempt_v1_seconds=v1['elapsed_seconds'], local_diagnostic_v2_seconds=v2['elapsed_seconds'],
    two_local_engineering_attempts_seconds=v1['elapsed_seconds']+v2['elapsed_seconds'],
    v1_exact_forward_counts='NOT_RECORDED_DO_NOT_INFER_FROM_V2',
    v2_completed_encoding_batches=len(failure['completed_batches']),
    v2_completed_logical_rows=sum(b['logical_rows'] for b in failure['completed_batches']),
    v2_completed_physical_rows=sum(b['physical_rows'] for b in failure['completed_batches']),
    v2_attempted_logical_rows=failure['logical_reserved'],
    v2_attempted_physical_rows=failure['physical_reserved'],
    v2_failed_shape=failure['shape'], v2_failure_maxabs=failure['max_absolute_output_difference'],
    v2_completed_forward_seconds=sum(b['seconds'] for b in failure['completed_batches']),
    v2_failed_forward_seconds=failure['seconds'],
    E3_vectors_persisted=0, reusable_encoded_outputs=0,
    external_head_scoring_started=False, external_distance_pairs=0,
    external_reporting_started=False, external_quality_results_exported=False,
    backend_changed=False, dropout_not_root_cause='Frozen e3_forward_batches calls model.eval() and torch.inference_mode()',
    exact_hardware_kernel_cause='NOT_ISOLATED; observed on nonproduction Windows/Torch2.8 runtime',
    input_readback_after_both_failures=inputs,
    source_only_parity=read(HERE / 'source_probe/RESULT.json')['result'],
    code_identity_caution='v1/v2 did not retain a pre-run code manifest. New final entrypoint now records it before execution; this improvement is not claimed executed.',
    regression_tests=dict(total=4, passed=4, real_pipeline_pass=False),
    no_more_local_forward_retries=True,
    required_next='Same fixed slice on intended Linux3.11/Torch2.5.1/NumPy2.0.1 delivery; stop on any gate failure',
    runtime_budget='NOT_FROZEN: actual encoding runtime incompatible and whole-population shape/unique-tensor census not complete')
write(HERE / 'SUMMARY.json', result)
for path in list(HERE.glob('*.py')) + list(HERE.glob('*.md')) + list(HERE.glob('*.json')) + [
        HERE/'source_probe/RESULT.json', HERE/'local_attempt_v1/RESULT.json',
        HERE/'local_diagnostic_v2/RESULT.json', HERE/'local_diagnostic_v2/CLONE_FAILURE_DIAGNOSIS.json',
        HERE/'local_diagnostic_v2/ENCODING_BATCH_LEDGER.jsonl']:
    path.with_name(path.name + '.sha256').write_text(sha(path)+'  '+path.name+'\n',encoding='utf-8')
