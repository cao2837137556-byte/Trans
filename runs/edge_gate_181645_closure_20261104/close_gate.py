"""Verify retrieved terminal evidence and reconcile the local progress mirror."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEPLOY = ROOT/'runs/edge_formal_gate_deployment_v2_20261103'
sys.path.insert(0, str(ROOT/'runs/edge_formal_execution_v2_20261103'))
from checkpoint import atomic_json, sha
from runtime_control import current_status


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    final = read(DEPLOY/'FINAL_ACCEPTANCE.json')
    assert final['job_id'] == '181645' and final['status'] == 'STOP'
    archive = DEPLOY/'.private/results.tar'
    assert archive.stat().st_size == final['result_archive']['bytes']
    assert sha(archive) == final['result_archive']['sha256']
    retrieved = DEPLOY/'retrieved'
    manifest = read(retrieved/'RESULT_MANIFEST.json')
    for name, pin in manifest['files'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        path = retrieved/relative
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256']
    output = retrieved/'outputs/gate_181645'
    current = current_status(output, card_sha256=final['card_sha256'])
    assert current['status'] == 'STOP' and current['scratch_cleanup']['complete'] is True
    child = read(output/'engineering_attempts'/current['attempt_id']/'CHILD_STOP_main.json')
    assert child['reason'] == 'TimeoutError:EDGE_REPLAY_DEADLINE'
    scheduler = [line.split('|') for line in final['scheduler']['stdout'].splitlines()]
    primary = [row for row in scheduler if row[0] == '181645']
    assert len(primary) == 1 and primary[0][1:4] == ['FAILED', '1:0', '01:57:37']
    assert current['resources']['max_tree_rss_bytes'] < 8*1024**3
    original = HERE/'PROGRESS_BEFORE_TERMINAL_RECONCILE.json'
    if not original.exists():
        original.write_bytes((DEPLOY/'PROGRESS.json').read_bytes())
    snapshot = read(original)
    last = snapshot['worker']
    receipt = dict(schema='EDGE_181645_FAILURE_CLOSURE_V1',
        status='VERIFIED_BUDGET_STOP_NOT_ENGINEERING_PASS', job_id='181645',
        root_cause=child['reason'], scheduler_state='FAILED', scheduler_exit_code='1:0',
        scheduler_elapsed='01:57:37', max_tree_rss_bytes=current['resources']['max_tree_rss_bytes'],
        cleanup_complete=True, verified_result_members=len(manifest['files']),
        archive=final['result_archive'], last_observed_frame=last['frame'],
        last_observed_selected_persisted=last['selected_persisted'], udp_total_frames=3215732,
        frame_scope='Last heartbeat only; not exact final processed frame',
        full_role_spools_retained_per_supervisor=True,
        full_role_payload_audit='PENDING_REMOTE_INSPECTION_NOT_INCLUDED_IN_SMALL_RECEIPT_EXPORT',
        cross_version_reuse='NOT_APPROVED_WITHOUT_COMPATIBILITY_PROOF',
        partial_role_reusable=False, scientific_quality_computed=False,
        v3_packaging_authorized_by_user=True, new_jobs_submitted=0,
        effective_vs_overhead_cpu_accounting='NOT_MEASURED_DO_NOT_INVENT',
        evidence={str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in
                  (DEPLOY/'FINAL_ACCEPTANCE.json', retrieved/'RESULT_MANIFEST.json',
                   output/'CURRENT_ENGINEERING_ATTEMPT.json',
                   output/'engineering_attempts'/current['attempt_id']/'CHILD_STOP_main.json')})
    audit_path = HERE/'ROLE_RETENTION_AUDIT.json'
    if audit_path.exists():
        audit = read(audit_path)
        assert audit['status'] == 'V2_RETAINED_ARTIFACT_INTEGRITY_AUDITED_NOT_V3_MIGRATION'
        assert all(audit['roles'][r]['status'] == 'COMPLETE_V2_BYTES_AND_BINDING_VERIFIED'
                   for r in ('NORMAL', 'HTTP'))
        assert audit['roles']['UDP']['status'] == 'INCOMPLETE_NOT_REUSABLE'
        receipt.update(full_role_payload_audit='VERIFIED_NORMAL_HTTP_PAYLOADS_INDEXES_BINDING_AND_EOF',
                       retained_role_audit_sha256=sha(audit_path), retained_roles=audit['roles'])
    atomic_json(HERE/'CLOSURE.json', receipt)
    progress = dict(snapshot, stage='STOP', scheduler_state='FAILED',
        engineering_current=current, attempt_receipt=current,
        error=child['reason'], updated_utc=datetime.now(timezone.utc).isoformat(),
        message='181645已按重放时间守卫停止（1小时57分37秒）；验收未通过，清理成功。正在按已确认决策制作独立v3，不自动重投。')
    v3 = ROOT/'runs/edge_formal_execution_v3_20261104/LOCAL_ACCEPTANCE.json'
    if v3.exists() and read(v3)['status'] == 'PASS_LOCAL_PACKAGE_LINUX_AND_INDEPENDENT_REVIEW_PENDING':
        progress['message'] = ('181645已按重放时间守卫停止（1小时57分37秒），工程验收未通过。'
            'NORMAL/HTTP完整产物校验通过；独立v3已本地封存，待小anti复核与Linux验收，未启动新作业。')
    progress['worker'] = dict(last, stage='STOP_LAST_REPLAY_OBSERVATION')
    atomic_json(DEPLOY/'PROGRESS.json', progress)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
