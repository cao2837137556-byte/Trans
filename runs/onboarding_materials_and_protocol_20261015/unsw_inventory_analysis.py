"""Metadata-only UNSW commissioning inventory; never imports model/decoder code.

Reads the five already-used devices only. Writes planning evidence, not an
experiment package. Counts describe the frozen selected query population and
legacy qualification metadata, not a complete new-frontend census.
"""
from pathlib import Path
import collections
import datetime
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PREP = ROOT / 'runs/legacy_commissioning_unsw_evaluation_preparation_v1_20260926'
QUAL = ROOT / 'runs/legacy_commissioning_unsw_hpc_delivery_v1_20260926/pullback/verified_job176183/runs/qualification'
INPUTS = ROOT / 'runs/legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891/runs/real_repair/inputs'
OLD = ROOT / 'runs/legacy_commissioning_unsw_recovery_delivery_v2_20260927/result_review_job176975/evidence/runs/real_evaluation/manifests'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        return [json.loads(line) for line in handle]


def utc(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat()


def proto_count(rows):
    return {str(k): v for k, v in sorted(collections.Counter(r['protocol'] for r in rows).items())}


def time_range(rows):
    if not rows:
        return None
    lo, hi = min(r['timestamp'] for r in rows), max(r['timestamp'] for r in rows)
    return dict(first=lo, last=hi, first_utc=utc(lo), last_utc=utc(hi))


def main():
    roster = read_json(PREP / 'device_roster.json')
    normal = read_json(QUAL / 'unsw-benign-20180528.summary.json')
    certificate = read_json(PREP / 'normal_source_certificate.json')
    queries = read_rows(INPUTS / 'UNSW_DEV.jsonl.gz')
    references = read_rows(INPUTS / 'UNSW_REFS.jsonl.gz')
    old_queries = read_rows(OLD / 'queries.jsonl.gz')
    old_references = read_rows(OLD / 'references.jsonl.gz')
    assert queries == old_queries and references == old_references
    assert len(queries) == 148316 and len(references) == 92
    assert set(r['device'] for r in queries + references) == set(d['device_id'] for d in roster)
    assert len({r['uid'] for r in queries + references}) == len(queries) + len(references)
    devices = []
    for d in roster:
        owner = normal['owners'][d['mac']]
        q = [r for r in queries if r['device'] == d['device_id']]
        rr = [r for r in references if r['device'] == d['device_id']]
        n, a = [r for r in q if r['label'] == 0], [r for r in q if r['label'] == 1]
        t0 = d['t0']
        first_components = d['eligible_reference_components_by_protocol']
        first_positions = owner['fixed_hour']['legal_targets_by_protocol']
        second = [r for r in n if t0 + 3600 < r['timestamp'] <= t0 + 7200]
        assert len(n) == d['planned_normal_query_count'] and len(a) == d['planned_attack_query_count']
        assert proto_count(rr) == d['planned_selected_references_by_protocol']
        assert all(r['timestamp'] > t0 + 3600 for r in q)
        first_complete = len(rr) == sum(first_components.values())
        later_complete = len(n) == d['full_normal_eligible_positions']
        exact_2h_components = first_complete and later_complete
        combined = rr + second
        observed_union = {str(p): len({r['component_id'] for r in combined if r['protocol'] == p}) for p in (6, 17)}
        lower = {str(p): max(first_components.get(str(p), 0), observed_union[str(p)]) for p in (6, 17)}
        pos_lower = {str(p): first_positions.get(str(p), 0) + sum(r['protocol'] == p for r in second) for p in (6, 17)}
        after_2h_n, after_2h_a = [r for r in n if r['timestamp'] > t0 + 7200], [r for r in a if r['timestamp'] > t0 + 7200]
        devices.append(dict(
            device_id=d['device_id'], display_name=d['display_name'], mac=d['mac'],
            normal_provenance_status=certificate['status'], capture_id=certificate['source']['capture_id'],
            t0=t0, t0_utc=utc(t0), t0_rule='Fixed shared first timestamp of publisher normal capture, not per-device first packet or model outcome',
            cutoffs={'B0_B1_1h':t0+3600, 'B2_2h':t0+7200},
            observed_owner_time={'first': owner['first'], 'last': owner['last'], 'first_utc':utc(owner['first']), 'last_utc':utc(owner['last']), 'continuous_observation_claim':False},
            old_legal_normal_time={'first':owner['first_legal'], 'last':owner['last_legal'], 'first_utc':utc(owner['first_legal']), 'last_utc':utc(owner['last_legal'])},
            first_hour_old_qualification={'legal_positions_by_protocol':first_positions, 'components_by_protocol':first_components, 'status':'EXACT_OLD_QUALIFICATION_NOT_COMPLETE_NEW_FRONTEND_CENSUS'},
            original_bank={'references':len(rr), 'by_protocol':proto_count(rr), 'time_range':time_range(rr), 'all_first_hour_components_represented':first_complete, 'identity_status':'EXACT_JOB177891_AND_JOB176975_METADATA_MATCH'},
            fixed_query_metadata={'normal':len(n), 'attack':len(a), 'normal_time_range':time_range(n), 'attack_time_range':time_range(a), 'after_1h':{'normal':len(n),'attack':len(a)}, 'after_2h':{'normal':len(after_2h_n),'attack':len(after_2h_a),'normal_by_protocol':proto_count(after_2h_n),'attack_by_protocol':proto_count(after_2h_a)}, 'in_second_hour':{'normal':len(second),'attack':sum(t0+3600<r['timestamp']<=t0+7200 for r in a)}, 'full_after_1h_old_legal_normal_population':d['full_normal_eligible_positions'],'all_old_normal_population_after_1h_selected':later_complete},
            two_hour_old_metadata={'components_by_protocol':lower, 'components_status':'EXACT_OLD_LEGAL_POPULATION' if exact_2h_components else 'LOWER_BOUND_ONLY', 'observed_component_union':observed_union, 'known_legal_positions_by_protocol':pos_lower, 'positions_status':'EXACT_OLD_LEGAL_POPULATION' if later_complete else 'LOWER_BOUND_ONLY', 'latest_component_representatives_status':'RECONSTRUCTABLE_FOR_SECOND_HOUR_OBSERVED_COMPONENTS' if exact_2h_components else 'FULL_CANDIDATE_ENDPOINTS_MISSING'},
            activity_evidence={'operation_status':d['functional_status'],'reference_activity_values':sorted({r['activity'] for r in rr}),'query_activity_values':sorted({r['activity'] for r in q}),'reference_direction_field':dict(collections.Counter(r['direction'] for r in rr)),'direction_caveat':'Saved owner-relative metadata direction is not q14 window-relative direction; not an activity label.'},
            feasibility={'normal_archive_present_and_time_pairing_supported':True,'B0_B1_old_candidates':'COMPLETE_COMPONENT_REPRESENTATIVES_IN_OLD_BANK' if first_complete else 'ONLY_64_SELECTED_OF_623_FIRST_HOUR_COMPONENTS_LOCAL','B1_selection_can_change_component_set_under_old_census':not first_complete,'B2_material_status':'AVAILABLE_RAW_AND_CAUSAL_TIME_SPAN; FULL_NEW_FRONTEND_CANDIDATES_PENDING','B2_known_component_gap':'TCP remains exactly one under the old legal census; 2h does not resolve it' if d['display_name']=='WEMO Power Switch' else 'New-frontend census and feature/q14 alignment still pending','existing_recent_feature_coverage':'Only sealed selected UID identities verified here; no new reference features loaded or generated'}
        ))
    source_paths = [PREP/'device_roster.json',PREP/'normal_source_certificate.json',PREP/'evaluation_recipe.json',QUAL/'unsw-benign-20180528.summary.json',OLD/'enumeration.json',OLD/'component_counts.json',OLD/'queries.jsonl.gz',OLD/'references.jsonl.gz',INPUTS/'receipt.json',INPUTS/'UNSW_DEV.jsonl.gz',INPUTS/'UNSW_REFS.jsonl.gz',ROOT/'repo/ood/legacy_unsw_archival_data_v1.py']
    source_pins = []
    for path in source_paths:
        source_pins.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    raw = ROOT/certificate['source']['path']
    result = dict(schema='unsw-onboarding-materials-metadata-only-v1',date='2026-10-15',status='PLANNING_EVIDENCE_NO_MODEL_RUN',
        scope='Five previously used UNSW devices only; no scores, raw packet decoding, model inference, fitting, or cache reconstruction.',
        normal_source=certificate,
        raw_normal_presence={'exists':raw.exists(),'bytes':raw.stat().st_size if raw.exists() else None,'expected_bytes':certificate['source']['bytes'],'sha256_this_pass':'NOT_REHASHED','content_read_this_pass':False},
        metadata_population_limit='No population.sqlite or complete first-hour endpoint export found in the inspected UNSW preparation/recovery metadata outputs. Component-count totals do not supply timestamps. Current selected metadata retains the old qualification population; this is not full coverage under the RECENT frontend.',
        validation={'job177891_queries_equal_job176975_queries':True,'job177891_refs_equal_job176975_refs':True,'queries':len(queries),'references':len(references),'normal':sum(d['fixed_query_metadata']['normal'] for d in devices),'attack':sum(d['fixed_query_metadata']['attack'] for d in devices),'common_after_2h_normal':sum(d['fixed_query_metadata']['after_2h']['normal'] for d in devices),'common_after_2h_attack':sum(d['fixed_query_metadata']['after_2h']['attack'] for d in devices)},
        devices=devices,source_pins=source_pins,
        protocol_implications=[
            'Keep all original queries and weights in the main report; the after-2h counts define only a paired late-query supplement. Early queries use the base head.',
            'All 72553 fixed attack queries occur on 2018-06-01, after both candidate windows; extending normal observation 1h to 2h does not remove any current UNSW attack query.',
            'For four devices all old first-hour components were already selected. With one representative per component and matched quotas B1 cannot change the old candidate UID set there; Motion Sensor needs the complete 623-component first-hour candidate metadata.',
            'The official normal source makes a 2h archival projection possible. This is passive archive evidence, not verified active deployment or coverage of known functional stages.',
            'Missing new-frontend candidate metadata is PENDING_METADATA_ADAPTER, not evidence that B2 has no raw materials. Do not mark B2 successful or completely implementable from saved scores.',
            'Do not silently use selected evaluation queries as a substitute complete candidate bank. A future normal-only metadata adapter must enumerate the predeclared trusted source/time window independent of scores or error labels.',
            'Switch old TCP scarcity persists at 2h. Do not repeat its one component, borrow another device, or extend time after seeing outcomes to manufacture two-component eligibility.'
        ])
    (OUT/'unsw_inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = ['# UNSW 五设备入网材料表（仅元数据）','','2026-10-15。没有解码原始 PCAP、读取模型分数、生成特征或运行训练。只检查已经使用的五台设备。','',
        '发布方正常归档 `unsw-benign-20180528` 在本地，文件长度与既有记录一致；本轮没有重算原始文件 SHA。归档范围为 2018-05-28 00:00:01.090390 至 2018-05-29 00:00:00.567891 UTC。统一 t0 是该正常归档首包时间，1h/2h 截止分别为 01:00:01.090390 / 02:00:01.090390 UTC。它是可信发布方正常归档证据，不是现场主动操作或无污染的独立证明。原记录注明两段捕获静默和 UNKNOWN_PASSIVE。','',
        '## 组件、原库与候选可用性','','下表 TCP/UDP 计数来自旧合法目标人口及当前保存的查询元数据，不等于新 RECENT 前端下的全量新候选数。`≥` 是严格下界，不能据此冻结完整候选库。','',
        '| 设备 | 首小时 TCP/UDP（旧完整统计） | 原库 TCP/UDP | 两小时 TCP/UDP | 两小时统计依据 |','|---|---:|---:|---:|---|']
    for d in devices:
        one=d['first_hour_old_qualification']['components_by_protocol']; old=d['original_bank']['by_protocol']; two=d['two_hour_old_metadata']; mark='' if two['components_status']=='EXACT_OLD_LEGAL_POPULATION' else '≥'
        lines.append(f"| {d['display_name']} | {one.get('6',0)}/{one.get('17',0)} | {old.get('6',0)}/{old.get('17',0)} | {mark}{two['components_by_protocol']['6']}/{mark}{two['components_by_protocol']['17']} | {'旧合法人口可精确复原' if not mark else '已选记录下界；缺完整候选'} |")
    lines += ['','WEMO Power Switch 首小时与两小时均只有 1 个 TCP 组件：此次延长到两小时不能解决其旧口径 TCP 资格缺口。TP Link Plug 的旧口径 2h 组件可精确复原为 3/7。其余三个设备的已选正常查询经过抽样，不能把观察到的组件数当成全量。Motion 首小时已有完整统计 TCP=603，因此即使局部 UID 并集只有 482，也仍报告 TCP≥603。','',
        '除 Motion Sensor 外，四台设备的首小时旧候选全部已在原库中。若仍按“每组件一个最后代表、相同容量与协议名额”，B1 时间分层无法改变这四台设备的旧参考 UID 集合。Motion 的 623 个首小时组件只保存了选中的 64 条参考，本地尚无其全量截止端点，因此不能只在这 64 条里重新排序后宣称已检验 B1。','',
        '## 观测时间、活动记录与固定查询','','时间范围不代表无间断记录。所有参考和查询的活动字段都是 UNKNOWN；操作状态 UNKNOWN_PASSIVE。UNSW 清单虽有 owner 相对 inbound/outbound 字段，但它不是功能活动标签，也不是 q14 的窗口相对方向。','',
        '| 设备 | 正常设备记录首包（UTC） | 正常设备记录末包（UTC） | 原完整固定查询 正常/攻击 | 2h 后共同子集 正常/攻击 | 1h→2h 内正常查询 |','|---|---|---|---:|---:|---:|']
    for d in devices:
        q=d['fixed_query_metadata']; t=d['observed_owner_time']; after=q['after_2h']
        lines.append(f"| {d['display_name']} | {t['first_utc']} | {t['last_utc']} | {q['normal']}/{q['attack']} | {after['normal']}/{after['attack']} | {q['in_second_hour']['normal']} |")
    v=result['validation']
    lines += ['',f"总固定查询为正常 {v['normal']:,}、攻击 {v['attack']:,}；2h 后共同子集正常 {v['common_after_2h_normal']:,}、攻击 {v['common_after_2h_attack']:,}。1h→2h 有 1,319 条正常查询。**主报告保留这些早期查询与原权重，早期仍由基础头判断；共同较晚子集只是补充配对分析。** 既有攻击均来自 2018-06-01，全部晚于两个观察窗口；不存在延长此正常窗口后删掉当前 UNSW 攻击的问题。",'',
        '## 可以定下来的安排与待补项','','1. OLD_BANK 身份已具备：Job 177891 的 148,316 查询、92 参考逐行元数据与 Job 176975 完全相同。可固定旧库锚点及原查询评价口径。','2. B0/B1/B2 可固定 t0、1h/2h、每设备最多 64 组件、同协议资格、共同完整查询、较晚子集与回退规则；当前材料支持两小时正常归档投影。','3. B1 在当前 UNSW 没有可信活动标签，只能退化为 UNKNOWN×时间段分层。四个全收录设备不应重复运行相同库冒充新对照；Motion 才存在首小时选取改变空间，需完整候选端点。','4. B2 不应判作材料不存在。其正常原文件及足够时长已存在；缺的是按拟议当前前端统一生成的完整候选、代表时点 E3/q14 和 UID 对齐。Switch 的旧合法 TCP 缺口不因 2h 消失；其他设备也不预许诺改善检出或误报。','5. 后续 normal-only 元数据入口只从预定正常来源和时间窗口取候选，不能用已选查询代替全量候选，也不能按模型错误/标签反选参考。原全量 population.sqlite 未导出到本次检查到的本地元数据产物；组件总计没有时间戳，不能代替它。','',
        '本表只落实材料边界。距离半径、修正强度、源侧保护与新特征兼容均未在本轮运行。','',
        '## 可复核来源','','完整路径、长度与本轮小元数据 SHA256 在 `unsw_inventory.json` 的 `source_pins`；原始 PCAP 仅做存在性与长度检查。`unsw_inventory_analysis.py` 可重现本表，它只读 JSON/JSONL 元数据。','']
    for pin in source_pins:
        lines.append(f"- `{pin['path']}` — `{pin['sha256']}`")
    (OUT/'unsw_inventory.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(v,ensure_ascii=False))


if __name__ == '__main__':
    main()
