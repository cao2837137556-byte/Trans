import argparse,hashlib,json,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def read(n):return json.loads((P/n).read_text(encoding='utf-8-sig'))
def run():
 receipt=read('EVALUATION_COMPLETION.json');checks=0
 for n,h in receipt['receipt_sha256'].items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h;checks+=1
 d=read('DIAGNOSE_RESULT.json');pre=read('PREFLIGHT_RESULT.json')
 for phase in ['PREFLIGHT','DIAGNOSE']:assert '|COMPLETED|0:0|' in read(phase+'_SCHEDULER.json')['stdout'];checks+=1
 assert d['status']==pre['status']=='PASS' and not d['training'] and not d['deployment_change'];checks+=1
 lines=['# 同库历史参考与三维C5：自动完成回执','','结果：工程完成、回执SHA及同库复现门通过；以下为固定对照结果。','影响：仅离线后处理，原模型/阈值/部署不变，仍非独立外部测试。','下一步：由科学验收判断A/B支持是否保留；不自动新训练。','','|数据|视图|方法|头|普通正常FPR|加权正常FPR|普通攻击检出（Edge HTTP/UDP）|加权攻击检出|','|---|---|---|---|---:|---:|---|---|']
 pct=lambda x:f'{x*100:.6f}%'
 for pool,o in d['pools'].items():
  g=o['parity_gate'];assert g['support_excluded_rows']==0 and g['support_storage_contract']['compared_rows']==o['rows'];checks+=1
  assert g['status']=='PASS' and g['support_max_abs_error']<=2e-10 and g['score_max_abs_error']<=2e-10 and g['decision_differences']==0;checks+=1
  for view,methods in o['views'].items():
   for method,heads in methods.items():
    for head,rr in heads.items():
     for role,v in rr.items():
      assert 0<=v['alarm_count']<=v['rows'] and abs(v['sample_rate']-v['alarm_count']/v['rows'])<1e-12 and 0<=v['hierarchical_rate']<=1+1e-12 and v['added_vs_RAW']==0;checks+=1
     roles=['HTTP','UDP'] if pool=='EDGE' else ['ATTACK'];v=rr['NORMAL']
     lines.append('|'+ '|'.join([pool,view,method,head,pct(v['sample_rate']),pct(v['hierarchical_rate']),'/'.join(pct(rr[r]['sample_rate']) for r in roles),'/'.join(pct(rr[r]['hierarchical_rate']) for r in roles)])+'|')
  if pool=='EDGE':assert o['edge_unchanged_gate']=='PASS';checks+=1
  else:
   primary=o['views']['full']['RAW']['ensemble']['NORMAL']['rows'];audit=o['donor_retention'];assert sum(v['rows'] for k,v in audit.items() if k.startswith('all/'))==primary;checks+=1
 lines+=['','## 历史供体支持度留存（全视图正常）','','|数据/供体|正常行|二维有支持|三维有支持|正支持归零|有两个匹配|任一dc/rho>1|两者dc/rho>1|','|---|---:|---:|---:|---:|---:|---:|---:|']
 for pool in ['CIC_DEV','UNSW_DEV']:
  for k,v in d['pools'][pool]['donor_retention'].items():
   lines.append('|'+ '|'.join([pool+'/'+k]+[str(v[n]) for n in ['rows','positive2','positive3','lost_positive','matched_pairs_with_context','either_dc_over_rho_gt1','both_dc_over_rho_gt1']])+'|')
 improved={}
 for method in ['C5_3D_FUSION','C5_3D_OLD']:
  passed=[]
  for pool in ['CIC_DEV','UNSW_DEV']:
   q=d['pools'][pool]['metrics'][method]['ensemble']
   passed.append(all(q['NORMAL'][basis]<.02 and q['ATTACK'][basis]>=.999 for basis in ['sample_rate','hierarchical_rate']))
  improved[method]=dict(AB_primary_ensemble_2pct_999_pass=all(passed),edge_unchanged=True,full_original_999_target=False)
 lines+=['','## 边界与后续','',json.dumps(improved,ensure_ascii=False),'','仅AB主视图集成的门不能替代全视图、逐设备、单种子结果。Edge维持旧轮99.79%/98.66%不满足原双99.9%，故不自动晋升或训练。完整逐设备普通/加权、Edge HT与供体分位数在DIAGNOSE_RESULT。','',f"预检{pre['seconds']:.2f}s，完整{d['seconds']:.2f}s；采样峰值{max(pre['rss_peak_bytes'],d['rss_peak_bytes'])/2**30:.3f}GiB。历史context与数组留超算。"]
 f=ROOT/'runs/mainline_docs/collab/20261106_same_bank_context_runtime_codex.md';f.write_bytes(('\n'.join(lines)+'\n').encode());Path(str(f)+'.sha256').write_text(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n')
 (P/'AUTOMATIC_ACCEPTANCE.json').write_text(json.dumps(dict(status='PASS',checks=checks,scope='SUMMARY_SHA_AND_PARITY_NOT_MANUAL_SCIENTIFIC_ACCEPTANCE',comparisons=improved,report=str(f),review_pending=True),indent=2)+'\n')
def main(watch):
 end=time.monotonic()+36*3600
 while True:
  if (P/'EVALUATION_COMPLETION.json').exists():run();return
  if (P/'CHAIN_STATE.json').exists() and read('CHAIN_STATE.json')['stage']=='STOP':return
  if not watch:raise RuntimeError('NOT_COMPLETE')
  assert time.monotonic()<end;time.sleep(10)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--watch',action='store_true');main(a.parse_args().watch)
