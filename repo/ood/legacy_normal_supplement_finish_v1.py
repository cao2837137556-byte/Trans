"""Low-cost local completion watcher, metadata review and sealed report; no retries."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from legacy_normal_supplement_acquire_v1 import ROOT, RUN, RESEARCH, dump
import legacy_cic2022_two_camera_semantic_probe_v1 as old

DOC=ROOT/'runs/mainline_docs/legacy_normal_supplement_result_v1_20260917.md'


def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def progress(download,audit,checked,final=None):
    text=('# 多日正常流量：自动执行状态\n\n'
          f"更新时间：{time.strftime('%Y-%m-%d %H:%M:%S')}（本地时间）\n\n"
          f"- 完整下载：{download.get('completed_files',0)} / 7\n"
          f"- 原始核验完成：{checked} / 7\n"
          f"- 累计接收：{download.get('total_received_bytes',0)/1024**3:.3f} / 8 GiB\n"
          f"- 当前下载：{download.get('current_file','')}；{download.get('status','')}\n"
          f"- 当前核验：{audit.get('file','')}；{audit.get('status','')}；{audit.get('stage','')}；已处理 {audit.get('packets',0):,} 条\n"
          f"- 自动重试：0；模型训练：未启动\n\n")
    if final:
        text+=f"最终状态：**{final['status']}**\n\n{final.get('reason','')}\n\n"
        if DOC.exists():text+=f'[查看材料核验报告]({DOC.as_posix()})\n\n'
        text+='执行完成不等于模型效果通过；本阶段没有训练或评分。\n'
    else:
        text+='程序自动继续下载、核验、汇总和封存；不需要模型定时轮询。失败或预算触顶即停止，不自动重试。\n'
    tmp=RUN/'PROGRESS.md.tmp';tmp.write_text(text,encoding='utf-8');tmp.replace(RUN/'PROGRESS.md')


def finish(download,audit):
    summaries=sorted(RUN.glob('[0-9][0-9]_summary.json'))
    stop=download.get('reason') or audit.get('reason') or ''
    if not summaries:raise RuntimeError('No completed captures to review: '+stop)
    for pin in read(RUN/'review_source_pins.json'):
        if old.sha(ROOT/pin['path'])!=pin['sha256']:raise RuntimeError('Review source pin changed')
    with (RUN/'review.stdout.log').open('w',encoding='utf-8') as out, (RUN/'review.stderr.log').open('w',encoding='utf-8') as err:
        result=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'repo/ood/legacy_normal_supplement_review_v1.py')],cwd=str(ROOT),stdout=out,stderr=err)
    if result.returncode:raise RuntimeError('Metadata review failed; see review.stderr.log; no retry')
    review=read(RUN/'review_summary.json')
    baseline=read(RESEARCH/'verification_and_sources.json')
    for pin in baseline['unrelated_files_unchanged']+baseline['sources']:
        if old.sha(ROOT/pin['path'])!=pin['sha256']:raise RuntimeError('Preservation/source check failed: '+pin['path'])
    manifest=read(RUN/'execution_manifest.json')
    for pin in manifest['scripts']:
        if old.sha(ROOT/pin['path'])!=pin['sha256']:raise RuntimeError('Execution script changed')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(ROOT),text=True).strip()!=baseline['head']:
        raise RuntimeError('HEAD changed during execution')
    if subprocess.check_output(['git','branch','--show-current'],cwd=str(ROOT),text=True).strip()!=baseline['branch']:
        raise RuntimeError('Branch changed during execution')
    for p in RUN.glob('[0-9][0-9]_receipt.json'):
        receipt=read(p)
        if old.sha(Path(receipt['local_path']))!=receipt['sha256']:raise RuntimeError('Final raw hash mismatch')
    devices=review['devices']
    candidates=sum(d['counts'].get('legacy_valid_candidates',0) for d in devices)
    shared=[d for d in devices if d['prior_new_attack_inbound_services'] and d['shared_protocol_device_port']]
    no_shared=[d['device'] for d in devices if d['prior_new_attack_inbound_services'] and not d['shared_protocol_device_port']]
    seven=[d['device'] for d in devices if d['valid_date_count']>=7]
    status='COMPLETE_RAW_REVIEW' if len(summaries)==7 else 'STOPPED_PARTIAL_REVIEW_COMPLETE'
    final=dict(status=status,reviewed_files=len(summaries),downloaded_files=download.get('completed_files',0),
        raw_received_bytes=download.get('total_received_bytes',0),qualified_file_bytes=review['source_raw_bytes'],
        received_byte_accounting=download.get('received_byte_accounting','Exact completed application body reads'),
        saved_body_bytes=download.get('saved_body_bytes',download.get('total_received_bytes',0)),
        budget_bytes=8589934592,retries=0,reason=stop,
        material_decision='COVERAGE_QUANTIFIED_CONTROL_AND_DEPENDENCE_LIMITATIONS_REMAIN_NOT_TRAINING_READY',
        capture_hours=review['capture_hours_sum'],normal_candidate_positions=candidates,
        devices_with_at_least_seven_candidate_dates=len(seven),devices_without_shared_directional_service=no_shared,
        training_started=False,features_generated=False,hpc=False,completed_epoch=time.time(),report=str(DOC))
    assert final['raw_received_bytes']<=final['budget_bytes']
    verification=dict(status='PASS',head=baseline['head'],branch=baseline['branch'],
        unrelated_files_preserved=len(baseline['unrelated_files_unchanged']),source_pins_verified=True,
        script_pins_verified=True,raw_sha256_verified=True,byte_budget_respected=True,
        independent_record_and_tshark_counts_match=True,retries=0,no_training=True,
        report_generator_sha256=old.sha(Path(__file__)))
    dump(RUN/'final_verification.json',verification)
    # Factual material decision; no fabricated independence/accuracy conclusion.
    rows=[]
    for d in devices:
        rows.append(f"| {d['device']} | {d['valid_date_count']} | {d['counts'].get('legacy_valid_candidates',0):,} | {d['candidate_streams']:,} | {d['counts'].get('retained_prefix_changed_candidates',0):,} | {d['conservative_tuple_excluded_candidate_targets']:,} |")
    file_rows=[]
    for p in summaries:
        s=read(p);rec=s['integrity']
        file_rows.append(f"| {Path(s['file']).name} | {s['bytes']:,} | {(rec['maximum_timestamp']-rec['minimum_timestamp'])/3600:.3f} | {s['counts']['packets']:,} |")
    partition_rows=[]
    for name,v in review['proposed_partition_totals'].items():
        partition_rows.append(f"| {name} | {v['devices']} | {v['candidate_targets']:,} | {v['candidate_streams']:,} | {v['conservative_tuple_excluded_candidate_targets']:,} |")
    report=f'''# 多日正常流量获取与原始核验结果

日期：2026-09-17。执行状态：{status}。用户授权：对已封存的七个 Active 文件，在 8 GiB 累计接收预算内获取并做原始核验；失败停止、零自动重试，不进入特征提取或模型训练。

## 当前结果

完整核验 {len(summaries)}/7 个文件，合计 {review['source_raw_bytes']:,} 字节（{review['source_raw_bytes']/1024**3:.3f} GiB），全网捕获时段合计约 {review['capture_hours_sum']:.2f} 小时。预算核算字节数 {final['raw_received_bytes']:,}，低于 8,589,934,592 字节上限；已保存响应体 {final['saved_body_bytes']:,} 字节。停止原因：{stop or '无执行失败'}。

若发生 IncompleteRead，预算按末次请求的完整 256 KiB 预留计算保守接收上界，不把未保存的异常内部分片遗漏为零；精确接收量及上下界说明保存在 download_status 和 download_status_at_transport_stop。失败文件保持 .partial，不解码、不当完整文件使用，第七文件未在第六文件失败后启动。

11 台候选设备共观察到 {candidates:,} 个符合旧输入门槛和因果前缀规则的正常来源候选位置；其中 {len(seven)}/11 台具有至少七个有效候选日期。这些是材料统计，**不是已训练样本数、独立样本数或准确率**。此前 219 个正常捕获合计约 60.04 分钟；本次采用多日整网捕获，单位不同，不把设备时段重复相加为更多独立证据。

实际文件大小是本次下载后测得。官网仍没有独立发布的文件大小或 SHA；本地校验核对传输 EOF、捕获结构、双解析记录/字节计数及下载后 SHA，没有假称获得官方校验值。

| 已核验文件 | 字节数 | 时段小时数 | 捕获记录数 |
| --- | ---: | ---: | ---: |
{chr(10).join(file_rows)}

## 逐设备数量与依赖

| 设备 | 有效日期数 | 有效候选位置 | 候选传输流 | 新包进入保留前缀的候选 | 排除旧参考同五元组后的候选上界 |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

传输流由 TShark 标识，不等于独立会话。最后一列是对旧拟议参考五元组的保守敏感性统计，不是新的删样本规则；相隔多天的同五元组不能自动视为同一连接或泄露。前缀保留包不再变化，也不能直接等同于模型表示完全不变，因为旧实现仍更新时长；本阶段未运行特征或模型。

| 拟议设备用途（未冻结） | 设备数 | 新增候选位置 | 候选传输流 | 排除参考同五元组后的候选上界 |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(partition_rows)}

每设备约七日、约两千分散查询仍是准备目标，不是 PASS 门槛。不能用重复相邻包凑量；长连接设备的有效行为多样性仍需按未来封存的采样与参考规则确认。Active 无逐包活动标注，不能推断七天包含七类用户活动。

## 时间、协议与泄露边界

逐文件检查真实包时间、完整性、目标 MAC、协议/端口和旧前缀可用性；详细结果见逐文件 summary、flows 和 audit_attempt。旧参考来自既有审计，未重新挑选；新增捕获是否晚于参考、早于该设备攻击，逐设备列在 review_summary。

旧前缀按捕获顺序逐步更新，不排序修复时间倒退，也不使用后续包回填较早上下文。时间倒退按原规则使受影响规范连接后续前缀无效，之前合法候选保留；实际数量见 counts。未增加 IPv6 回退或变更协议支持范围。

直接连接跨拟议角色的包数：{review['totals'].get('cross_role_direct_packets',0):,}。这项统计不能单独证明未来训练无泄露；还须按设备隔离参考、查询及上下文，检查共享规范连接。TShark 流标识、完整文件事后统计和服务审计信息只用于核验，不作为部署特征。

新文件间相同原始字节哈希组：{review['normal_fingerprints']['cross_day_byte_hash_groups']:,}；与旧新增正常审计相同字节哈希：{review['normal_fingerprints']['shared_prior_normal_byte_hashes']:,}。是否存在时间区间重叠及跨角色哈希见 review_summary.normal_fingerprints。不同日期周期性重复字节不自动判为重复观测或泄露。旧复用 18 文件没有重新解码，未声称覆盖其全部原始字节比对。

## 服务对照与材料决定

在可比的旧新增攻击方向审计中，{len(shared)} 台设备找到至少一个共享正常/攻击入站协议与设备端口组合；以下有攻击方向证据的设备仍没有：{', '.join(no_shared) or '无'}。精确组合、数量及比较范围见 review_summary。旧复用材料缺少相同口径方向字段，不混入这一比较，也不把端口重合本身当作有效机制对照。

**材料决定：正常覆盖已量化并获得补充，但尚不能直接宣告主要训练实验就绪。** 数量增多不能排除服务/来源捷径，不能补足攻击运行多样性，也不能提供独立部署复现。未出现正常端口 80 服务，不意味着每台设备本应有这种服务；不伪造正常标签、不修改前端凑对照。

下一决策应使用本次逐设备事实收敛参考/查询及服务对照，而非继续泛泛扩大正常包量。先明确哪些联合能力主张能由现有材料支持，以及仍缺哪种必要对照，再封存可执行样本和新实验规则。已取得文件保留；不会自动扩额、补日期或进入模型训练。

## 复核与产物

运行目录：runs/legacy_normal_supplement_acquisition_v1_20260917/。

- execution_manifest、逐文件 attempt/receipt/audit_attempt：授权、源身份与执行记录。
- 逐文件 summary/flows/fingerprints、review_summary、normal_fingerprint_index.sqlite：原始资格和跨文件依赖证据。
- final_verification、final_status、SHA256SUMS：最终状态和封存校验。
- PROGRESS.md：无需模型轮询的本地状态页；scripts/show_legacy_normal_supplement_status.ps1 可选 -Watch。

分支 codex/exp-mainline，HEAD 4b28747b09480471e2bac1beb3a9badf27280efb；8 个原有无关修改校验未变。没有模型评分、训练、新数据范围扩张或 HPC。

solved: 完成本授权范围内已成功获取文件的原始核验、跨文件汇总及真实数量报告。
changed_mainline: normal_supplement_material_evidence_updated；旧 R 与历史结果保留。
active_blocker: 最终独立样本及活动多样性未确认，服务/来源混杂控制仍需明确；执行缺口见最终状态。
frozen: 旧模型、分母、阈值、seed、损失及历史结果不变。
next_action: 依据本次具体覆盖和缺项作材料与实验范围决定；不自动训练。
'''
    if DOC.exists():raise RuntimeError('Refuse to overwrite result report')
    DOC.write_text(report,encoding='utf-8')
    DOC.with_suffix('.sha256').write_text(old.sha(DOC)+'  '+DOC.name+'\n',encoding='utf-8')
    progress(download,audit,len(summaries),dict(status='SEALING',reason='汇总已完成，正在封存并验证校验清单。'))
    # Only replace our own current panel. A newer task's panel is never overwritten.
    handoff=ROOT/'runs/mainline_docs/mainline_handoff.md'
    text=handoff.read_text(encoding='utf-8')
    marker='### 2026-09-17 latest: bounded normal supplement acquisition and raw review AUTHORIZED / RUNNING'
    panel=f'''### 2026-09-17 latest: bounded normal supplement {status}

User-authorized named7file acquisition and raw qualification finished with {len(summaries)}/7 audited
files, {review['source_raw_bytes']:,} completed bytes, {review['capture_hours_sum']:.2f} aggregate capture hours,
{candidates:,} target-device old-input candidates. {len(seven)}/11 devices have >=7 candidate dates.
Read `legacy_normal_supplement_result_v1_20260917.md` / SHA and matching run review_summary,
final_status/final_verification/SHA256SUMS. Service and dependency limits remain; not training-ready.
Actual received bytes {final['raw_received_bytes']:,} <=8GiB; zero retries. Stop reason: {stop or 'none'}.
No new features/scoring/training/HPC. Original R, protocols and8unrelated edits preserved.
Next make a bounded material/experiment decision from quantified device/date/service gaps;
do not equate packet volume with independent evidence or automatically download more/train.

'''
    if marker in text and text.index(marker)<text.index('### Historical 2026-09-17: targeted supplement'):
        start=text.index(marker);end=text.index('### Historical 2026-09-17: targeted supplement',start)
        tmp=handoff.with_suffix('.md.supplement.tmp');tmp.write_text(text[:start]+panel+text[end:],encoding='utf-8');tmp.replace(handoff)
    else:
        (RUN/'handoff_update_pending.md').write_text(panel,encoding='utf-8')
    expmap=ROOT/'runs/mainline_docs/mainline_experiment_map.md'
    text=expmap.read_text(encoding='utf-8');lines=text.splitlines(keepends=True)
    for i,line in enumerate(lines):
        if line.startswith('| Paper priority: original E3/P2 and joint capability') and 'RUNNING' in line and 'named7Activefile' in line:
            lines[i]=f'| Paper priority: original E3/P2 and joint capability 2026-09-17 | Retain R. Normal supplement {status}: {len(summaries)}/7 audited, {review["source_raw_bytes"]:,}bytes, {review["capture_hours_sum"]:.2f}hours, {candidates:,}candidate positions; {len(seven)}/11 devices >=7dates. Control/dependency limits remain; NOT_TRAINING_READY | `legacy_normal_supplement_result_v1_20260917.md` / SHA and run review_summary/final_status/final_verification/SHA256SUMS. <=8GiB received, zero retries. No features/scoring/training/HPC. Next bounded material/experiment decision; no automatic expansion. Historical R/rules and8unrelated files unchanged |\n'
            tmp=expmap.with_suffix('.md.supplement.tmp');tmp.write_text(''.join(lines),encoding='utf-8');tmp.replace(expmap)
            break
    # Logs remain mutable while this process is alive; exclude them from the seal.
    excluded={'SHA256SUMS','finish.stdout.log','finish.stderr.log','finish_process.json','PROGRESS.md','final_status.json'}
    paths=sorted(p for p in RUN.rglob('*') if p.is_file() and p.name not in excluded and not p.name.endswith('.tmp'))
    seals=[(old.sha(p),p.relative_to(RUN).as_posix()) for p in paths]
    (RUN/'SHA256SUMS').write_text(''.join(h+'  '+name+'\n' for h,name in seals),encoding='utf-8')
    for h,name in seals:
        if old.sha(RUN/name)!=h:raise RuntimeError('Seal verification failed: '+name)
    final['seal_verification']='PASS'
    dump(RUN/'final_status.json',final)
    with (RUN/'SHA256SUMS').open('a',encoding='utf-8') as out:
        out.write(old.sha(RUN/'final_status.json')+'  final_status.json\n')
    progress(download,audit,len(summaries),final)
    print(json.dumps(final,ensure_ascii=False))


def main():
    if (RUN/'finish_attempt.json').exists():raise RuntimeError('Completion already attempted; no retry')
    dump(RUN/'finish_attempt.json',dict(pid=os.getpid(),started_epoch=time.time(),script_sha256=old.sha(Path(__file__))))
    download={};audit={};checked=0
    try:
        while True:
            download=read(RUN/'download_status.json');audit=read(RUN/'audit_status.json')
            checked=len(list(RUN.glob('[0-9][0-9]_summary.json')))
            progress(download,audit,checked)
            if checked==7 or download.get('status')=='STOPPED_NO_RETRY' or audit.get('status')=='STOPPED_NO_RETRY':break
            time.sleep(15)
        finish(download,audit)
    except BaseException as exc:
        final=dict(status='STOPPED_COMPLETION_ERROR_NO_RETRY',reason=type(exc).__name__+': '+str(exc),training_started=False)
        dump(RUN/'final_status.json',final)
        progress(download,audit,checked,final)
        raise


if __name__=='__main__':main()
