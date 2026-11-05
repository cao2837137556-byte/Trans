"""Verify returned small artifacts and derive a readout; no scientific computation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    assert sha(ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json') == 'ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7'
    delivery = read(HERE / 'DELIVERY.json')
    for name, expected in delivery['pins'].items():
        assert sha(HERE / name) == expected, name
    remote = read(HERE / 'REMOTE_STATE.json')
    retrieval = read(HERE / 'REMOTE_RETRIEVAL.json')
    assert remote['stage'] == 'PASS' and remote['stop'] is None
    assert '182245|COMPLETED|0:0|00:03:19||1|8G' in remote['scheduler']['stdout']
    for name, item in retrieval['files'].items():
        assert sha(HERE / 'local' / name) == item['sha256'], name
    for name in ('AB_COMPLETE.json', 'EDGE_COMPLETE.json', 'PREFLIGHT_COMPLETE.json'):
        complete = read(HERE / 'local' / name)
        assert complete['status'] == 'PASS'
        for file, expected in complete['files'].items():
            assert sha(HERE / 'local' / file) == expected, file
    ab_slice = read(HERE / 'AB_SNAPSHOT_DIAGNOSIS.json')
    assert all(v['q14_replay_exact'] for v in ab_slice.values())
    probe = read(HERE / 'INPUT_PROBE_RESULT.json')
    assert probe['status'] == 'PASS' and probe['udp_rows'] == 20000
    assert probe['distinct_input_tensor_hashes'] == 1
    assert sum(probe['tensor_hash_counts'].values()) == 20000
    assert probe['sample_packets'] == probe['sample_bursts'] == {'1': 128}
    assert probe['sample_reset_reasons'] == {'FIRST_KEY': 128}
    data = {name: read(HERE / 'local' / (name + '_DIAGNOSIS.json')) for name in ('CIC_DEV', 'UNSW_DEV', 'EDGE')}
    table = []
    for name, d in data.items():
        assert d['all_full_decisions_exact'] and d['q14_protocol_consistent']
        for group, g in d['groups'].items():
            if not group.endswith('/ALL'):
                continue
            h = g['heads']['ensemble']
            assert h['raw_alarm_count'] - h['p3_alarm_count'] == h['p3_withdrawn']
            table.append(dict(dataset=name, group=group, rows=g['rows'], **{k: h[k] for k in (
                'raw_alarm_count', 'p1_alarm_count', 'p3_alarm_count', 'raw_rate', 'p1_rate', 'p3_rate',
                'p3_withdrawn', 'auc_vs_same_protocol_normal')}))
    edge = data['EDGE']['groups']
    udp = edge['UDP/ALL']; http = edge['HTTP/ALL']; psh = edge['HTTP/PSH_ACK']
    a_udp = data['CIC_DEV']['groups']['ATTACK/UDP']
    a_psh = data['CIC_DEV']['groups']['ATTACK/PSH_ACK']
    b_attack = data['UNSW_DEV']['groups']['ATTACK/ALL']
    assert udp['support_zero_rows'] == udp['component_count'] == 20000
    assert udp['heads']['ensemble']['p3_score_drop']['max'] == 0
    assert edge['HTTP/SYN_NO_ACK']['heads']['ensemble']['p3_withdrawn'] == 0
    assert 'ATTACK/UDP' not in data['UNSW_DEV']['groups']
    assert data['UNSW_DEV']['groups']['ATTACK/SYN_NO_ACK']['rows'] == b_attack['rows']
    sample = ab_slice['CIC_DEV/1/17']
    readout = dict(
        result='COMPLETED_EXISTING_ARTIFACT_DIAGNOSIS',
        impact='Evidence supports an input-representation blind spot, weak external RAW discrimination, and additional C5 HTTP alarm suppression; no checked artifact/alignment/decision error found.',
        next='Before changing the method, independently spot-check selected UDP raw packets against saved snapshots; any subsequent method development needs a separate version and fresh external confirmation.',
        scope='Read-only existing A/B and Edge results. No training, encoding, model forward, distance recomputation or threshold search.',
        dataset_roles={'A': 'CICIoT2022 / CIC_DEV, CONSUMED_DEVELOPMENT_ONLY',
                       'B': 'UNSW2018 / UNSW_DEV, CONSUMED_DEVELOPMENT_ONLY (not UNSW-NB15)',
                       'Edge': 'POST_FREEZE_EXTERNAL; now inspected for diagnosis'},
        metric_scope='Unweighted fixed-query descriptive rates and AUROC; not HT population estimates, event recall, or three interchangeable independent tests.',
        aggregate_ensemble=table,
        input_chain=dict(full_rows={k:v['rows_full'] for k,v in data.items()},
                         primary_rows={k:v['rows_primary'] for k,v in data.items()},
                         edge_queries=60000, edge_encoded_batches=4046, edge_result_chunks=469,
                         edge_input_manifest=retrieval['hpc_input_manifest'],
                         saved_decision_replay={'AB': 'C5_P1_AND_C5_P3_EXACT_FOUR_HEADS; RAW computed from saved scores and frozen cuts',
                                                'Edge': 'RAW_C5_P1_C5_P3_EXACT_FOUR_HEADS'},
                         ab_snapshot_q14_replay='EXACT_FOR_SAVED_UID_ORDERED_SLICES',
                         edge_udp_input_probe=probe),
        udp=dict(a_attack_rows=a_udp['rows'], a_raw_detected=a_udp['heads']['ensemble']['raw_alarm_count'],
                 a_margin_median=a_udp['heads']['ensemble']['raw_threshold_margin']['p50'],
                 a_q14_distinct=a_udp['unique_q14_rows'],
                 a_snapshot_slice_rows=sample['rows'],
                 a_snapshot_slice_multiple_packets=sum(n for k,n in sample['packets'].items() if int(k)>1),
                 a_snapshot_slice_12_bursts=sample['bursts']['12'],
                 edge_raw_score=udp['heads']['ensemble']['raw_score'],
                 edge_margin=udp['heads']['ensemble']['raw_threshold_margin'],
                 edge_support_zero_rows=udp['support_zero_rows'],
                 edge_p3_score_drop=udp['heads']['ensemble']['p3_score_drop'],
                 interpretation='Identical recorded encoder inputs plus q14 explain nearly constant RAW scores; C5 makes no UDP correction. Flow-scoped context can omit cross-flow flood intensity. A also has one q14 vector, so q14 identity alone is not the cause.'),
        http=dict(raw_auroc_vs_normal_tcp=http['heads']['ensemble']['auc_vs_same_protocol_normal'],
                  withdrawn=http['heads']['ensemble']['p3_withdrawn'],
                  psh_ack_rows=psh['rows'], psh_raw=psh['heads']['ensemble']['raw_alarm_count'],
                  psh_p3=psh['heads']['ensemble']['p3_alarm_count'],
                  psh_withdrawn=psh['heads']['ensemble']['p3_withdrawn'],
                  psh_margin_median=psh['heads']['ensemble']['raw_threshold_margin']['p50'],
                  psh_drop_median=psh['heads']['ensemble']['p3_score_drop']['p50'],
                  psh_support_median=psh['support']['p50'],
                  a_psh_margin_median=a_psh['heads']['ensemble']['raw_threshold_margin']['p50'],
                  a_psh_withdrawn=a_psh['heads']['ensemble']['p3_withdrawn'],
                  b_attack_all_syn_no_ack=True,
                  interpretation='RAW ranking fails on selected external HTTP queries; C5 then removes 7027 existing attack-associated alarms, mostly PSH_ACK. Development attack coverage and margins differ substantially.'),
        limitations=[
            'No independent fresh raw-PCAP-to-snapshot reconstruction: upstream semantic correctness is not fully proved.',
            'No fresh encoder or classifier inference: input hashes are recorded receipts; saved outputs are analyzed.',
            'Snapshot context comparisons use 128 score-independent UID-ordered slices, not full-population estimates.',
            'No all-UDP source-IP/port census; do not claim all queries have unique source IPs or prove spoofing from this audit.',
            'A/B use commissioning plus historical references; Edge uses commissioning only. Reference modes and sampling differ.',
            'No new independent Antigravity review. Original external safety FAIL remains unchanged.'
        ])
    write('DIAGNOSIS_READOUT.json', readout)
    files = ['diagnose.py','receiver.py','dashboard.py','input_probe.py','ab_snapshot_probe.py','finalize_readout.py',
             'index.html','DELIVERY.json','LOCAL_PREFLIGHT.json','REMOTE_STATE.json','REMOTE_RETRIEVAL.json',
             'AB_SNAPSHOT_DIAGNOSIS.json','INPUT_PROBE_RESULT.json','EDGE_INPUT_SHAPES.json','DIAGNOSIS_READOUT.json']
    files += ['local/' + p.name for p in sorted((HERE/'local').glob('*.json'))]
    receipt = dict(
        result='PASS_EXISTING_ARTIFACT_DIAGNOSIS_ACCEPTANCE',
        impact='Diagnostic execution and returned summaries verified; this is not a scientific efficacy PASS.',
        next='Freeze this diagnosis, preserve source results on HPC, then address the raw-to-snapshot boundary before a new method version.',
        verified_utc=datetime.now(timezone.utc).isoformat(),
        job_id='182245',scheduler_state='COMPLETED',exit_code='0:0',elapsed='00:03:19',
        cpu=1,memory_gib=8,wall_seconds=3600,batch_max_rss_kib=466068,
        preflight_seconds=remote['preflight']['seconds'],
        full_diagnostic_seconds=remote['complete']['seconds'],
        ab_diagnostic_seconds=read(HERE/'local/AB_COMPLETE.json')['seconds'],
        supplemental_input_probe_seconds=probe['seconds'],
        supplemental_probe_execution='Read-only stdlib process on the existing remote terminal; one-CPU affinity and 120-second internal deadline, not a second Slurm job.',
        raw_replay=0,new_encoding=0,new_model_forward=0,new_distance=0,training=0,threshold_fit=0,source_writes=0,
        external_safety='FAIL_UNCHANGED_FROM_FORMAL_EVALUATION',
        hpc_source='/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_evaluation_resume_v2_20261104/outputs/gate_182089',
        hpc_input_manifest=retrieval['hpc_input_manifest'],
        files={name:dict(sha256=sha(HERE/name),bytes=(HERE/name).stat().st_size) for name in files},
        explanatory_source_pins={name:sha(ROOT/name) for name in ['repo/ood/continuous_input_v3.py','repo/ood/query_tail_core_v2.py']},
        limitations=readout['limitations'])
    write('FINAL_ACCEPTANCE.json', receipt)
    print('PASS: source-delivery pins, returned-file SHA, completion chains, diagnostic count identities, and final readout verified.')


if __name__ == '__main__':
    main()
