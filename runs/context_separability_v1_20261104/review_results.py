"""Post-run mechanical acceptance and explicitly bounded scientific conclusion."""
import gzip,hashlib,json
from pathlib import Path
from accept_results import accept
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 accept();a=read(HERE/'FULL_ABLATION_SUMMARY.json');c=read(HERE/'FULL_CROSS_SUMMARY.json');retrieval=read(HERE/'RETRIEVAL.json')
 for n,v in read(HERE/'DELIVERY.json')['pins'].items():assert sha(HERE/('.private/'+n if n=='AB_SAMPLES.json.gz' else n))==v,n
 chosen=read(HERE/'FULL_ACTUAL_SELECTION.json')['samples'];uids=[s['uid'] for s in chosen];assert len(uids)==len(set(uids))==200
 expected={s['uid'] for s in read(HERE/'SELECTION.json')['samples']}
 base=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=read(base/'QUERY_SELECTION_SEAL.json')
 for role in ['NORMAL','UDP']:
  source=base/seal['roles'][role]['selected_file'];assert sha(source)==seal['roles'][role]['selected_sha256']
  with gzip.open(source,'rt') as f:rr=[json.loads(l) for l in f]
  rr=sorted([r for r in rr if r['protocol']==17],key=lambda r:hashlib.sha256(('context-v1|'+r['uid']).encode()).hexdigest())[:16]
  expected.update(r['uid'] for r in rr)
 assert set(uids)==expected and a['baseline_max_e3_error']==0 and a['weight_check']['all_exact'] and a['weight_check']['checked_names']==337
 alarm={}
 for key,g in a['groups'].items():
  if key.endswith('/ALL'):alarm[key]=dict(rows=g['rows'],ensemble_alarms=[x[3] for x in g['alarm_counts']])
 attack=[g for k,g in alarm.items() if k.startswith('CIC_DEV/ATTACK/')];assert sum(g['rows'] for g in attack)==64
 assert all(g['ensemble_alarms']==[32,32,32] for g in attack)
 assert alarm['EDGE/UDP/UDP/ALL']['ensemble_alarms']==[0,0,0]
 assert c['real_brute_force_queries_checked']==72
 assert all(r['queries']==20000 and r['raw_frames_read']==r['raw_total_frames'] for r in c['roles'].values())
 full=read(HERE/'FULL_RESULT.json');assert full['training']==full['threshold_fit']==full['source_writes']==0
 result=dict(result='DIAGNOSTIC_ACCEPTANCE_PASS_REPAIR_UNVALIDATED',impact='A UDP single-packet detections survive; prioritize causal cross-connection statistics as repair candidate',next='Prepare source-side 782/8/790 feature comparison and fixed-FPR validation; no new training launched',job_id='182280',scheduler=retrieval['state']['FULL_SCHEDULER'],ablation_rows=200,cross_queries=60000,original_e3_max_abs_error=a['baseline_max_e3_error'],original_head_max_abs_error=a['baseline_max_head_error'],single_packet_invariant_rows=a['single_packet_invariance_rows'],real_range_parity_checks=72,ablation_alarm_counts=alarm,comparison_scope='Fixed selected-query descriptive diagnosis, not post-repair recall or independent external confirmation',summary_sha256=retrieval['sha256'],remote_large_artifacts={role:r['arrays'] for role,r in c['roles'].items()},remote_paired_details=a['details'],review_report_sha256=sha(ROOT/'runs/mainline_docs/collab/20261105_context_separability_acceptance_codex.md'),limitations=['Finite A attack slices; no necessity of long history on these 64 rows','Header-field attribution untested','Edge one device, separate captures, 497 normal UDP queries','No new model trained, no thresholds fit, C5 withdrawal issue not repaired'])
 (HERE/'FINAL_ACCEPTANCE.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps({k:result[k] for k in ['result','job_id','ablation_rows','cross_queries','real_range_parity_checks']}))
if __name__=='__main__':main()
