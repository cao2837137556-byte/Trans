"""Verify immutable terminal evidence; improve only the local status mirror."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEPLOY = ROOT/'runs/edge_formal_gate_deployment_v3_20261104'
sys.path.insert(0, str(ROOT/'runs/edge_formal_execution_v3r1_20261104'))
from checkpoint import atomic_json, require, sha
from runtime_control import current_status


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    final = read(DEPLOY/'FINAL_ACCEPTANCE.json')
    require(final['job_id'] == '181699' and final['status'] == 'STOP', 'FINAL_IDENTITY')
    archive = DEPLOY/'.private/results.tar'
    require(archive.stat().st_size == final['result_archive']['bytes']
            and sha(archive) == final['result_archive']['sha256'], 'ARCHIVE_IDENTITY')
    retrieved = DEPLOY/'retrieved'
    manifest = read(retrieved/'RESULT_MANIFEST.json')
    for name, pin in manifest['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'MEMBER_PATH')
        path = retrieved/relative
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(retrieved.resolve())
                and path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256'], 'MEMBER_IDENTITY:'+name)
    output = retrieved/'outputs/gate_181699'
    current = current_status(output, card_sha256=final['card_sha256'])
    require(current['status'] == 'STOP' and current['scratch_cleanup']['complete'] is True, 'STOP_AND_CLEANUP')
    child_path = output/'engineering_attempts'/current['attempt_id']/'CHILD_STOP_main.json'
    child = read(child_path)
    require(child['attempt_id'] == current['attempt_id'] and child['card_sha256'] == final['card_sha256']
            and child['reason'] == 'TimeoutError:EDGE_REPLAY_DEADLINE', 'ROOT_CAUSE_BINDING')
    rows = [s.split('|') for s in final['scheduler']['stdout'].splitlines()]
    primary = [r for r in rows if r[0] == '181699']
    require(len(primary) == 1 and primary[0][1:4] == ['FAILED', '1:0', '01:57:37']
            and primary[0][5:8] == ['1', '8G', '02:00:00'], 'SCHEDULER_TERMINAL')
    require(current['resources']['max_tree_rss_bytes'] < 8*1024**3, 'OBSERVED_RSS_WITHIN_LIMIT')
    # Revalidate the real preflight independently of the full gate's STOP.
    sys.path.insert(0, str(DEPLOY))
    from preflight_acceptance import inspect
    pre = read(retrieved/'PREFLIGHT_ACCEPTANCE.json')
    for name, digest in pre['files'].items():
        require(sha(retrieved/name) == digest, 'PREFLIGHT_PIN')
    job = dict(pre['job'], output_directory=str(retrieved/'outputs/preflight_181696'))
    inspect(retrieved, DEPLOY/'ENGINEERING_CARD.json', job, pre['scheduler'])
    original = HERE/'PROGRESS_BEFORE_DIAGNOSIS.json'
    if not original.exists():
        original.write_bytes((DEPLOY/'PROGRESS.json').read_bytes())
    receipt = dict(status='VERIFIED_REPLAY_BUDGET_STOP_NOT_ENGINEERING_PASS', job_id='181699',
        root_cause=child['reason'], scheduler_state='FAILED', scheduler_elapsed='01:57:37',
        max_tree_rss_bytes=current['resources']['max_tree_rss_bytes'], cleanup_complete=True,
        verified_result_members=len(manifest['files']), archive=final['result_archive'],
        preflight=dict(job_id='181696', status='PASS_REVALIDATED', elapsed='00:06:53'),
        failure_phase='prepare_inputs / original causal raw replay / decoder deadline check',
        full_gate_encoder_and_recovery_reached=False,
        last_exact_frame=None, last_frame_status='NOT_EXPORTED_IN_TERMINAL_SMALL_RECEIPTS',
        complete_role_payload_audit='PENDING_REMOTE_READ_ONLY_AUDIT',
        complete_roles_preserved_per_supervisor=True, partial_role_reusable=False,
        current_bottleneck='NOT_ESTABLISHED_BY_TIMEOUT_ALONE',
        progress_io_full_run_speedup='NOT_QUANTIFIED_FROM_AVAILABLE_TERMINAL_EVIDENCE',
        scientific_quality_computed=False, new_jobs_submitted=0,
        cpu_time_effective_vs_overhead='UNKNOWN_DO_NOT_INVENT',
        remote_status_channel='UNREACHABLE_AT_INCIDENT_CHECK; SSH_AUTH_NOT_ATTEMPTED',
        evidence={p.relative_to(ROOT).as_posix(): sha(p) for p in (
            DEPLOY/'FINAL_ACCEPTANCE.json', retrieved/'RESULT_MANIFEST.json', child_path,
            retrieved/'PREFLIGHT_ACCEPTANCE.json')})
    observed_path = HERE/'REMOTE_TERMINAL_OBSERVATION.json'
    if observed_path.exists():
        observed = read(observed_path)
        require(observed['job_id'] == '181699' and observed['heartbeat']['reason'] == child['reason'],
                'REMOTE_OBSERVATION_JOB_REASON')
        heartbeat = observed['heartbeat']
        receipt.update(last_observed_frame=heartbeat['frame'], udp_total_frames=3215732,
            last_frame_status='REMOTE_FINAL_STOP_HEARTBEAT_NOT_INDEPENDENTLY_AUDITED_EXACT_LAST_FRAME',
            last_observed_selected_persisted=heartbeat['selected_persisted'],
            udp_phase_seconds=heartbeat['role_elapsed_seconds'],
            numerical_append_seconds=heartbeat['append_seconds'],
            decoder_next_seconds=heartbeat['decoder_next_seconds'],
            complete_role_metadata=observed['roles'],
            current_bottleneck='NUMERICAL_CONTEXT_APPEND_DOMINATES_RECORDED_WALL_TIMINGS; INTERNAL_SPLIT_UNMEASURED',
            remote_status_channel='HTTP_RECEIVER_UNREACHABLE; EXISTING_USER_SSH_REUSED_FOR_READ_ONLY_STDOUT',
            remote_observation=dict(path=observed_path.relative_to(ROOT).as_posix(), sha256=sha(observed_path),
                provenance='Selected stdout fields visually transcribed from existing remote terminal; not a downloaded raw receipt'))
    atomic_json(HERE/'CLOSURE.json', receipt)
    progress = read(original)
    progress.update(stage='STOP', scheduler_state='FAILED', error=child['reason'],
        diagnosis='完整重放未能在两小时预算内完成；预留清理时间后触发时间守卫。',
        message='181699已停止：1小时57分37秒触发原包重放时间守卫。峰值RSS约5.99GiB，临时目录清理成功；预检181696已通过，完整工程门未通过。未重投；下一步只读核验最后重放位置和保留产物。',
        worker={}, engineering_current=current, attempt_receipt=current,
        updated_utc=datetime.now(timezone.utc).isoformat(), terminal_diagnosis=receipt,
        preflight_status='PASS', preflight_job_id='181696')
    progress.pop('remote_prepare', None)
    if observed_path.exists():
        progress['message'] = ('181699已按重放时间守卫停止（1小时57分37秒），非内存超限。'
            'UDP最后STOP心跳3170387/3215732帧（98.59%），剩约4.5万帧；NORMAL/HTTP完整标记已见，载荷完整性待核验。'
            '数值上下文更新累计约87.6分钟，是下一步拆查重点。预检通过，完整工程门未通过；未重投。')
        progress['worker'] = dict(stage='STOP_LAST_HEARTBEAT', role='UDP', frame=heartbeat['frame'],
            selected_persisted=heartbeat['selected_persisted'], max_tree_rss_bytes=current['resources']['max_tree_rss_bytes'])
    atomic_json(DEPLOY/'PROGRESS.json', progress)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
