"""Metadata-only source reference feasibility audit; no model, scores or raw decode.

Reads the consumed Job177891 manifests and original source-role metadata.
Writes only this new directory. Existing roles, references and packages are unchanged.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PREP = ROOT / 'runs/legacy_reference_sample_preparation_v1_20260917'
PULL = ROOT / 'runs/legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891'
INPUT = PULL / 'runs/real_repair/inputs'
SALT = 'q-normal-verifier-component-cal-v1-20260922'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec='microseconds')


def main():
    paths = [INPUT/'SOURCE_REFS.jsonl.gz', INPUT/'LEARN.jsonl.gz',
             PREP/'finalized/references.jsonl.gz', PREP/'finalized/reference_costs.json',
             PREP/'capture_catalog.json', PREP/'devices.json',
             ROOT/'repo/ood/continuous_model_v3.py', ROOT/'repo/ood/legacy_qref_data_v1.py']
    export = read(PULL/'export_manifest.json')
    for p in paths[:2]:
        assert sha(p) == export['included'][p.relative_to(PULL).as_posix()]['sha256']
    refs = [r for r in rows(paths[0]) if r['partition'] == 'LEARN']
    original = [r for r in rows(paths[2]) if r['partition'] == 'LEARN']
    assert len(refs) == len(original) == 104
    assert {r['uid']: r for r in refs} == {r['uid']: r for r in original}
    assert len({r['component_id'] for r in refs}) == 104
    by_device = defaultdict(list)
    banks = defaultdict(list)
    for r in refs:
        assert r['use'] == 'REFERENCE' and r['label'] == 0
        assert r['timestamp'] <= r['reference_end']
        by_device[r['device']].append(r)
        banks[(r['device'], r['protocol'])].append(r)
    devices = sorted(by_device)
    ends = {d: by_device[d][0]['reference_end'] for d in devices}
    assert all(r['reference_end'] == ends[r['device']] for r in refs)
    ref_components = {r['component_id'] for r in refs}
    ref_uids = {r['uid'] for r in refs}
    catalog = read(PREP/'capture_catalog.json')
    costs = {d['device']: d for d in read(PREP/'finalized/reference_costs.json') if d['partition'] == 'LEARN'}
    dedicated = [c for c in catalog if c.get('device') in devices and c['use'] == 'REFERENCE']
    assert len(dedicated) == 18 and all(c['provenance'] == 'normal' for c in dedicated)
    candidate = {}
    for c in dedicated:
        p = PREP/'captures'/(c['capture_id']+'_targets.jsonl.gz')
        paths.append(p)
        for r in rows(p):
            assert r['use'] == 'REFERENCE' and r['label'] == 0
            key = (r['device'], r['component_id'])
            order = (r['timestamp'], r['capture_id'], r['frame'], r['uid'])
            old = candidate.get(key)
            if old is None or order > (old['timestamp'], old['capture_id'], old['frame'], old['uid']):
                candidate[key] = r
    t0 = {d: min(c['first'] for c in dedicated if c['device'] == d) for d in devices}
    counts = Counter()
    fit_normal = Counter()
    fit_normal_eligible = Counter()
    fit_normal_components = defaultdict(set)
    cal_attack = Counter()
    cal_attack_own = Counter()
    cal_pair_counts = Counter()
    cal_cross_pair_counts = Counter()
    cal_any = Counter()
    cal_cross_any = Counter()
    query_component_roles = defaultdict(set)
    candidate_role_overlap = defaultdict(set)
    source_windows = Counter()
    time_ranges = {}
    role_uid_digest = {'FIT': hashlib.sha256(), 'CAL': hashlib.sha256()}
    for r in rows(INPUT/'LEARN.jsonl.gz'):
        d, p, role, y = r['device'], r['protocol'], r['fit_role'], r['label']
        assert d in by_device and role in ('FIT', 'CAL') and r['use'] != 'REFERENCE'
        assert r['uid'] not in ref_uids and ends[d] < r['timestamp']
        expected_cal = r['component_id'] not in ref_components and int(hashlib.sha256((SALT+'|'+d+'|'+r['component_id']).encode()).hexdigest(), 16) % 5 == 0
        assert role == ('CAL' if expected_cal else 'FIT')
        query_component_roles[r['component_id']].add(role)
        if (d, r['component_id']) in candidate:
            candidate_role_overlap[(d, r['component_id'])].add(role)
        counts[(role, y)] += 1
        role_uid_digest[role].update((r['uid']+'\n').encode())
        key = (d, role, y, p)
        time_ranges.setdefault(key, [r['timestamp'], r['timestamp']])
        time_ranges[key][0] = min(time_ranges[key][0], r['timestamp'])
        time_ranges[key][1] = max(time_ranges[key][1], r['timestamp'])
        if y == 0:
            for hours in (1, 2):
                if t0[d] <= r['timestamp'] <= t0[d] + hours * 3600:
                    source_windows[(d, hours, role)] += 1
        if role == 'FIT' and y == 0:
            fit_normal[(d, p)] += 1
            fit_normal_components[(d, p)].add(r['component_id'])
            if len(banks[(d, p)]) >= 2:
                fit_normal_eligible[(d, p)] += 1
        if role == 'CAL' and y == 1:
            cal_attack[(d, p)] += 1
            legal = [(bd, bp) for (bd, bp), bank in banks.items()
                     if bp == p and len(bank) >= 2 and ends[bd] < r['timestamp']]
            if (d, p) in legal:
                cal_attack_own[(d, p)] += 1
            if legal:
                cal_any[(d, p)] += 1
            cross = [k for k in legal if k[0] != d]
            if cross:
                cal_cross_any[(d, p)] += 1
            for bd, bp in legal:
                cal_pair_counts[(d, p, bd)] += 1
            for bd, bp in cross:
                cal_cross_pair_counts[(d, p, bd)] += 1
    assert all(len(v) == 1 for v in query_component_roles.values())
    assert counts == Counter({('FIT', 0): 134493, ('FIT', 1): 483415, ('CAL', 0): 33147, ('CAL', 1): 115672})
    assert sum(cal_pair_counts.values()) == 359875
    result = dict(date='2026-10-15', scope='METADATA_ONLY_SOURCE_REFERENCE_AND_ROLE_FEASIBILITY',
                  model_forward=False, raw_decode=False, score_access=False, calibration=False,
                  original_references_match_consumed_job177891=True,
                  original_source_reference_rows=104,
                  counts={f'{k[0]}_{k[1]}': v for k, v in sorted(counts.items())},
                  consumed_role_uid_order_sha256={k: h.hexdigest() for k, h in role_uid_digest.items()},
                  source_bank_rule='same protocol; >=2 distinct components; full donor device reference_end < query timestamp; all source refs trusted dedicated normal role',
                  radius_material_scope='FIT normal own-bank eligibility only; no radius or feature calculation',
                  cal_attack_rows=sum(cal_attack.values()),
                  cal_attack_rows_any_legal_source_bank=sum(cal_any.values()),
                  cal_attack_rows_any_cross_device_source_bank=sum(cal_cross_any.values()),
                  cal_attack_source_bank_pairs=sum(cal_pair_counts.values()),
                  cal_attack_cross_device_bank_pairs=sum(cal_cross_pair_counts.values()),
                  source_candidate_dedicated_component_count=len(candidate),
                  devices=[], input_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in paths})
    for d in devices:
        own = by_device[d]
        dc = [c for c in dedicated if c['device'] == d]
        existing = [r for (rd, _), r in candidate.items() if rd == d]
        new = [r for r in existing if r['uid'] not in ref_uids]
        entry = dict(device=d, old_reference_count=len(own),
                     reference_timestamp_first=min(r['timestamp'] for r in own),
                     reference_timestamp_last=max(r['timestamp'] for r in own),
                     reference_start_utc=utc(min(r['timestamp'] for r in own)),
                     reference_end=ends[d], reference_cutoff_utc=utc(ends[d]),
                     archival_t0=t0[d], archival_t0_utc=utc(t0[d]),
                     dedicated_capture_ids=[c['capture_id'] for c in dc],
                     dedicated_capture_wall_span_seconds=max(c['last'] for c in dc)-t0[d],
                     dedicated_recorded_seconds_sum=sum(c['last']-c['first'] for c in dc),
                     dedicated_activities=sorted({c['mode'] for c in dc}),
                     dedicated_raw_paths=[dict(capture_id=c['capture_id'], path=c['path'],
                                              exists=Path(c['path']).is_file(),
                                              expected_bytes=c['bytes'],
                                              size_matches=Path(c['path']).is_file() and Path(c['path']).stat().st_size==c['bytes']) for c in dc],
                     original_selected_activities=costs[d]['selected_activities'],
                     original_endpoint_candidate_components=len(existing),
                     extra_dedicated_components=len(new),
                     extra_dedicated_components_intersect_fit=sum('FIT' in candidate_role_overlap[(d,r['component_id'])] for r in new),
                     extra_dedicated_components_intersect_cal=sum('CAL' in candidate_role_overlap[(d,r['component_id'])] for r in new),
                     protocols=[], proposed_windows=[])
        for p in (6, 17):
            bank = banks[(d, p)]
            protocol = dict(protocol=p, name='TCP' if p==6 else 'UDP',
                            old_reference_components=len(bank),
                            old_reference_uids=sorted(r['uid'] for r in bank),
                            radius_fit_normal_rows=fit_normal[(d,p)],
                            radius_fit_normal_distinct_components=len(fit_normal_components[(d,p)]),
                            radius_eligible_fit_normal_rows=fit_normal_eligible[(d,p)],
                            radius_material_available=bool(fit_normal_eligible[(d,p)]),
                            cal_attack_rows=cal_attack[(d,p)],
                            cal_attack_own_eligible_rows=cal_attack_own[(d,p)],
                            cal_attack_legal_donors=[dict(donor=bd, same_device=(bd==d), query_pairs=n)
                                                   for (qd,qp,bd),n in sorted(cal_pair_counts.items()) if qd==d and qp==p],
                            cal_attack_time_bounds=time_ranges.get((d,'CAL',1,p)))
            entry['protocols'].append(protocol)
        for hours in (1, 2):
            end = t0[d] + hours * 3600
            available = [r for r in existing if t0[d] <= r['timestamp'] <= end]
            within = [c for c in catalog if c.get('device') == d and c['provenance']=='normal' and c['first'] <= end and c['last'] >= t0[d]]
            entry['proposed_windows'].append(dict(hours=hours, cutoff=end, cutoff_utc=utc(end),
                existing_dedicated_candidate_components_by_protocol={str(p):sum(r['protocol']==p for r in available) for p in (6,17)},
                original_reference_rows_in_window=sum(r['timestamp'] <= end for r in own),
                frozen_fit_normal_queries_inside_window=source_windows[(d,hours,'FIT')],
                frozen_cal_normal_queries_inside_window=source_windows[(d,hours,'CAL')],
                overlapping_dedicated_capture_ids=[c['capture_id'] for c in within if c['use']=='REFERENCE'],
                overlapping_query_role_capture_ids=[c['capture_id'] for c in within if c['use']!='REFERENCE'],
                interpretation='Sparse archival window, not continuous observed hours. New banks cannot absorb the listed frozen query rows/captures. Dedicated-role candidates only may support a separate version; no new bank was built.'))
        result['devices'].append(entry)
    result['conclusions'] = [
        'Original 104-row banks are intact and sufficient to define source FIT normal radius eligibility and source CAL protection donor membership without refitting the split.',
        'Atomi and Globe have one reference per protocol; Amcrest TCP has one. Those own-bank cells cannot supply the proposed second-component distance.',
        'All CAL attack rows have at least one legal same-protocol cross-device source donor bank; enumerate fixed UID lists above before target scoring.',
        'Source reference captures are sparse short interaction recordings. One/two-hour archival clock windows are not one/two-hour continuous normal coverage.',
        'Do not absorb LEARN/FIT/CAL normal queries by label. A new source-bank policy must restrict itself to dedicated reference roles, preserve component assignment, and separately verify candidate identity/current-input snapshots.',
        'Dedicated metadata contains additional Amcrest candidate components, but this does not establish new feature availability, full continuous coverage, or benefit. The current work constructs no bank and computes no distance/score.'
    ]
    (OUT/'source_inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# 源侧正常参考与定参材料核查', '', '2026-10-15。仅检查已保存清单、角色和时间；没有读取模型分数、计算距离、运行前向、训练、原始包解码或改动封存对象。', '',
             '当前 104 条源参考与原始 manifest 完全相同。使用 Job177891 实际消耗的 LEARN metadata 核对 FIT/CAL，逐行角色符合原组件划分，数量为 FIT 617,908、CAL 148,819。', '',
             '| 设备 | 原 TCP / UDP 组件 | FIT 正常 TCP / UDP | 可用于二组件尺度的正常 TCP / UDP | 原库截止 UTC |', '|---|---:|---:|---:|---|']
    for d in result['devices']:
        p,q = d['protocols']
        lines.append(f"| {d['device']} | {p['old_reference_components']} / {q['old_reference_components']} | {p['radius_fit_normal_rows']} / {q['radius_fit_normal_rows']} | {p['radius_eligible_fit_normal_rows']} / {q['radius_eligible_fit_normal_rows']} | {d['reference_cutoff_utc']} |")
    lines += ['', 'Atomi、Globe 两协议以及 Amcrest 的 TCP 缺少两个参考组件，对这些设备/协议不能计算自身二近距离，也不能把重复行补成第二个组件。协议级半径仍可由其他有资格的源设备估计；这只是材料可用性，半径实际数值和跨设备有效性尚未计算。', '',
              f"源 CAL 有 {result['cal_attack_rows']:,} 条攻击，全部至少有一个合法同协议源库，也全部有跨设备供体。完整源库–攻击配对 {result['cal_attack_source_bank_pairs']:,} 对，其中跨设备 {result['cal_attack_cross_device_bank_pairs']:,} 对，与原合同的 359,875 对一致。", '',
              'TCP 合法二组件源库为 ArloQ、Philips、SimCam；UDP 为 Amcrest、ArloQ、Philips、SimCam。每个库必须整体截止早于查询；实际攻击时间已逐行检查。JSON 列出了每个设备/协议攻击的供体与配对数量，以及参考 UID，可直接用于下一版源侧保护清单登记。', '',
              '## 一小时 / 两小时新源库的边界', '',
              '| 设备 | 原专用参考实际录制秒数 | 三段捕获跨越秒数 | 专用角色候选 TCP / UDP | 1h 内已有 FIT / CAL 正常查询 | 2h 内已有 FIT / CAL 正常查询 |', '|---|---:|---:|---:|---:|---:|']
    for d in result['devices']:
        w1,w2=d['proposed_windows']
        cp=w2['existing_dedicated_candidate_components_by_protocol']
        lines.append(f"| {d['device']} | {d['dedicated_recorded_seconds_sum']:.3f} | {d['dedicated_capture_wall_span_seconds']:.3f} | {cp['6']} / {cp['17']} | {w1['frozen_fit_normal_queries_inside_window']} / {w1['frozen_cal_normal_queries_inside_window']} | {w2['frozen_fit_normal_queries_inside_window']} / {w2['frozen_cal_normal_queries_inside_window']} |")
    lines += ['', 't0 取原专用参考捕获已记录的最早原始时间，未用模型结果选时点。上述窗口是稀疏归档投影，不能称为连续观察 1/2 小时。Philips 的原三段参考跨度约 84 分钟，所以一小时截断甚至不包含原完整参考库。', '',
              '只从原专用 REFERENCE 捕获选候选，可以保持查询角色；原专用候选总计 '+str(len(candidate))+' 个组件，额外候选主要来自 Amcrest 原 64 条容量之外。其 FIT/CAL 组件交集已在 JSON 单列。延长时钟并不会自动产生新的专用正常数据，也不能把窗口内现有 FIT/CAL 正常查询按标签转入参考库。', '',
              '建议本轮源侧继续用原 104 条计算半径资格、执行 CAL 保护；新目标覆盖设置的保护外推局限单列。若另建源统一库，应另立版本，锁定专用参考角色、UID/组件隔离和新输入快照，再声称具备对应保护证据；不把它作为原库组合的阻塞项。', '',
              '## 证据与复核', '', '完整路径、SHA256、逐库 UID、时间和供体清单见同目录 `source_inventory.json`。脚本 `source_inventory_analysis.py` 只进行元数据读取和新目录输出。主要来源：', '',
              '- Job177891：`runs/legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891/runs/real_repair/inputs/{SOURCE_REFS,LEARN}.jsonl.gz`。',
              '- 原参考与成本：`runs/legacy_reference_sample_preparation_v1_20260917/finalized/{references.jsonl.gz,reference_costs.json}`。',
              '- 原角色与专用参考候选：同 preparation 目录的 `capture_catalog.json` 及 `captures/interaction-attack-*_targets.jsonl.gz`（仅 18 个源专用 REFERENCE 捕获）。',
              '- 原实现语义：`repo/ood/legacy_qref_data_v1.py` 的 split 与 `repo/ood/continuous_model_v3.py` 的 bank_metadata / Bank.matrix。', '',
              '原 PCAP 只检查路径存在和大小，未读取内容或重新哈希。旧端点清单可证明现存角色候选，不能替代新版输入的完整候选清查。']
    (OUT/'source_inventory.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('counts','cal_attack_rows','cal_attack_rows_any_legal_source_bank','cal_attack_source_bank_pairs','cal_attack_cross_device_bank_pairs','source_candidate_dedicated_component_count')},ensure_ascii=False))
    for d in result['devices']:
        print(d['device'], [(p['name'],p['radius_fit_normal_rows'],p['radius_eligible_fit_normal_rows'],p['cal_attack_rows']) for p in d['protocols']], 'extra candidate overlaps',d['extra_dedicated_components_intersect_fit'],d['extra_dedicated_components_intersect_cal'])


if __name__ == '__main__':
    main()
