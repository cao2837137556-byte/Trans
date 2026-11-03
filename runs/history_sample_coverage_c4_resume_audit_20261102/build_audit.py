"""Summarize retained receipts only; never encode, evaluate or submit."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def pin(p):
    return dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def write(p, value):
    temp = p.with_name(p.name+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temp.replace(p)


def main():
    state_path = HERE.parent/'history_sample_coverage_c4_preflight_repair_20261102/STATE_RECEIPT.json'
    state = read(state_path)['STATUS.json']
    remote = read(HERE/'REMOTE_REPORT.json')
    timing = read(HERE/'TIMING_CROSSCHECK.json')
    storage = read(HERE/'LOCAL_STORAGE_AUDIT.json')
    engineering_path = HERE.parent/'history_sample_coverage_c4_batch_resume_v1_20261102/CHECKPOINT_ENGINEERING_CHECK.json'
    worker = json.loads(remote['files']['workers/NETATMO_encode.json']['text'])
    prepared = json.loads(remote['files']['workers/NETATMO_prepare.json']['text'])
    assert state['error'] == 'WALL_SECONDS_LIMIT' and state['pairs'] == 0
    assert worker['completed'] == 4658 and worker['encoded_charged'] == 4674
    assert prepared['selected_snapshots'] == 12288
    encoded_files = [i for i in remote['member_inventory'] if '/encoded/' in i['name']]
    assert len(encoded_files) == 1 and encoded_files[0]['name'].endswith('BATCH_LEDGER.jsonl')
    prior_charged = 24534
    final_charge = math.ceil(state['elapsed_seconds'])+60
    report = dict(
        status='STOPPED_BUDGET_EXHAUSTED_AWAITING_USER_AMENDMENT', job_id='180670',
        source_preserved=True, resubmitted=False, new_model_forwards=0, new_distance_pairs=0,
        inputs=[pin(state_path), pin(HERE/'REMOTE_REPORT.json'), pin(HERE/'TIMING_CROSSCHECK.json'),
                pin(HERE/'LOCAL_STORAGE_AUDIT.json'), pin(engineering_path)],
        engineering_preparation=dict(receipt=read(engineering_path), execution_ready=False,
                                     sealed_for_execution=False, uploaded=False),
        completed=dict(complete_reusable_E3_rows=20480, netatmo_prepared_snapshots=12288,
                       netatmo_selected_ref=8192, netatmo_selected_dev=4096,
                       netatmo_raw_frames=4967010, netatmo_legal_endpoints=3592947,
                       netatmo_unpersisted_completed_E3_rows=4658,
                       netatmo_reserved_inflight_rows=16, netatmo_recoverable_E3_rows=0),
        accounting=dict(original_wall_limit_seconds=28800,
                        prior_wall_seconds_charged=prior_charged,
                        job180670_elapsed_seconds=state['elapsed_seconds'],
                        job180670_conservative_charge_seconds=final_charge,
                        cumulative_conservative_charge_seconds=prior_charged+final_charge,
                        remaining_original_seconds=0,
                        peak_process_tree_rss_bytes=state['peak_process_tree_rss_bytes'],
                        peak_output_bytes=state['peak_output_bytes'],
                        parent_encoded_rows_32768_is_reservation_not_completed=True),
        offline=dict(complete_registered_C4_possible_now=False,
                     missing=['Netatmo references E3', 'Netatmo HIST_DEV E3', 'Netatmo DEV_LOGITS'],
                     partial_three_device_evaluation_changes_contract=True,
                     after_complete_encoding='Reuse all saved A/B features and scores; run HIST_DEV first, A/B once only if gate passes. Local or HPC CPU execution is feasible; hosting and same-environment pins must be finalized before execution.'),
        timing=timing['combined_estimate'],
        proposed_budget=dict(authorized=False, additional_wall_seconds=18000,
                             proposed_cumulative_wall_ceiling_seconds=prior_charged+final_charge+18000,
                             cumulative_charged_E3_row_ceiling=37442,
                             unique_candidate_encoded_rows=32768,
                             pair_limit=1000000000, static_pair_upper_bound=997017497,
                             cpu=4, rss_bytes=8*2**30, output_bytes=20*2**30,
                             automatic_retry=False, automatic_resubmit=False,
                             source_of_approval_requirement='User explicitly requires a budget request after exhaustion and prohibits automatic resubmission.'),
        storage=dict(remote_personal_project='/public/home/jiangxinwei.zr/work/paper04',
                     local_drives=storage['drives'],
                     shared_filesystem_df_observed=dict(size='511T', used='7.2T', available='503T', percent='2%'),
                     personal_lfs_quota_observed=dict(kbytes_used=91542517, files=99505,
                                                     quota=0, limit=0, using_default_quota=True),
                     personal_quota_note='Observed default quota mode with zero displayed quota/limit; shared free space is not a personal allocation guarantee.',
                     recommended_large_artifact_home='HPC personal project directory',
                     local_policy='Keep small source/docs/receipts/final scientific arrays. Do not retrieve raw PCAP, census SQLite or chronological copies. Retain existing copies until per-file replica verification and cleanup authorization are resolved.',
                     local_files_deleted=0, source_files_moved=0))
    write(HERE/'AUDIT_RESULT.json', report)
    page = HERE.parent/'history_sample_coverage_c4_deployment_20261101/PROGRESS.json'
    write(page, dict(stage='STOPPED', job_id='180670', scheduler='180670|FAILED|1:0',
          updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
          worker=dict(phase='预算耗尽：3台设备完整编码可复用；Netatmo快照完成，E3未完整落盘',
                      completed=20480, total=32768),
          error='原累计8小时预算已耗尽，未重新提交。建议追加18000秒（5小时硬上限），预计补完约2.5～3.5小时，待用户批准。大中间产物继续留在超算。',
          budget_audit=str(HERE/'AUDIT_RESULT.json')))
    print(json.dumps(dict(status=report['status'], old_charged=prior_charged+final_charge,
                          proposed_additional=18000, submitted=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
