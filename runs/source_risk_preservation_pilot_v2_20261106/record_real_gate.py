"""Retrieve compact real-preflight evidence once; no polling or job submission."""
import base64,hashlib,json
from pathlib import Path
import chain_client
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,text):p.write_bytes(text.encode())
def main():
    r=chain_client.request('results');state=r['state'];assert state['stage']!='STOP',state
    pins={}
    for name,info in r['files'].items():
        assert name in [p+'_'+k+'.json' for p in ['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT'] for k in ['RESULT','STOP','SCHEDULER','JOB']]
        b=base64.b64decode(info['base64']);assert hashlib.sha256(b).hexdigest()==info['sha256'];(HERE/name).write_bytes(b);pins[name]=info['sha256']
    decode=json.loads((HERE/'DECODE_PREFLIGHT_RESULT.json').read_text());train=json.loads((HERE/'TRAIN_PREFLIGHT_RESULT.json').read_text())
    assert decode['status']=='PASS' and train['status']=='PASS' and train['signal_ready']
    assert all(v['updates']==8 and v['model_changed'] and max(v['baseline_parity'].values())==0 for v in train['heads'].values())
    job=state['PILOT_JOB']['job_id'];forecast=train['forecast_seconds'];assert forecast<=3600
    receipt=dict(status='PASS',scope='REAL_ENGINEERING_AND_SOURCE_TRAINING_GATE_ONLY',
                 jobs=['182577','182578'],pilot_job=job,pilot_stage=state['stage'],receipt_sha256=pins,
                 baseline_full_FIT_CAL_exact_parity=True,real_updates=24,all_three_seeds_changed=True,
                 pilot_forecast_seconds=forecast,peak_gib=train['rss_peak_bytes']/2**30,
                 scientific_acceptance=False,full_training_or_external_evaluation=False)
    write(HERE/'REAL_GATE_ACCEPTANCE.json',json.dumps(receipt,indent=2)+'\n')
    extra=f'''\n## 真实门补充回执\n\n182577/182578均完成；真实编码/距离/评价回放和三种子各8批训练门PASS。原头全FIT/CAL分数误差精确0，实际24次更新、三个头均改变且检查点重读通过；进程采样峰值{receipt['peak_gib']:.3f}GiB。保守小试预测{forecast:.1f}秒，已自动提交PILOT作业{job}，取回时{state['stage']}。只是工程门通过，尚未验收小试效果。证据`REAL_GATE_ACCEPTANCE.json`。\n'''
    report=DOC/'collab/20261106_source_risk_preservation_pilot_launch_codex.md';report.write_bytes(report.read_bytes()+extra.encode())
    write(report.with_suffix('.md.sha256'),sha(report)+'  '+report.name+'\n')
    start=DOC/'NEW_CHAT_START_HERE.md';before=start.read_bytes();history=DOC/'START_HERE_HISTORY.md'
    history.write_bytes(history.read_bytes()+b'\n\n## 2026-11-06 before source pilot real gate acceptance\n\n'+before)
    text=before.decode();lines=text.splitlines()
    lines=[f'1. **源域小试运行中**：v2作业{job}，取回时{state["stage"]}。真实门182577/182578已PASS；1CPU/8GiB，小试保守估计{forecast/60:.1f}分钟；尚未科学验收。' if x.startswith('1. **') else x for x in lines]
    lines=[f'3. **真实门已通过**：原头全FIT/CAL分数精确复现，三种子各8批共24次真实更新，保存重读/评价/预算门PASS，峰值{receipt["peak_gib"]:.3f}GiB。自动小试运行，不自动扩展全量训练或外部评价。' if x.startswith('3. **') else x for x in lines]
    write(start,'\n'.join(lines)+'\n')
    lead=f'''## 2026-11-06：源域真实训练门PASS，小试{job}启动\n\n182577/182578通过；原融合头全FIT/CAL精确复现，三种子24次真实更新与保存重读/评价/预算门PASS。小试保守预测{forecast/60:.1f}分钟，1CPU/8GiB，进程采样峰值{receipt['peak_gib']:.3f}GiB。{job}已启动，固定三种子各320更新，不自动全量或外部评价；科学效果待验收。见[回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)。\n\n---\n\n'''
    for name in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/name;p.write_bytes(lead.encode()+p.read_bytes())
    manifest=json.loads((HERE/'ARTIFACT_SHA256.json').read_text())
    for name in list(manifest)+list(pins)+['record_real_gate.py','REAL_GATE_ACCEPTANCE.json']:manifest[name]=sha(HERE/name)
    write(HERE/'ARTIFACT_SHA256.json',json.dumps(manifest,indent=2)+'\n')
    paths=[(HERE/name).relative_to(ROOT).as_posix() for name in list(pins)+['record_real_gate.py','REAL_GATE_ACCEPTANCE.json','ARTIFACT_SHA256.json']]
    paths += [(DOC/name).relative_to(ROOT).as_posix() for name in ['NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md']]
    paths += [report.relative_to(ROOT).as_posix(),report.with_suffix('.md.sha256').relative_to(ROOT).as_posix()]
    write(HERE/'.private/REAL_GATE_STAGE_PATHS.txt','\n'.join(paths)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='receipt_sha256'}))
if __name__=='__main__':main()
