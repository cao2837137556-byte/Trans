"""Receipt acceptance; no claim of paper benchmark or full training reproduction."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def read(n):return json.loads((HERE/n).read_text())
def main():
 for n,h in read('RETRIEVAL.json')['sha256'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h,n
 delivery=read('DELIVERY.json')
 for n,h in delivery['pins'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h,n
 assert hashlib.sha256((HERE/'receiver.py').read_bytes()).hexdigest()==delivery['receiver_sha256']
 result=read('RESULT.json');assert result['status']=='PASS' and result['full_training_authorized'] is False
 job=read('JOB.json');assert job==dict(job_id='182719',cpu=1,memory_gib=8,wall_seconds=7200)
 scheduler=read('SCHEDULER.json');assert scheduler['returncode']==0 and '182719|COMPLETED|0:0|00:11:04|' in scheduler['stdout']
 caps=dict(PIPELINE=1800,FIDELITY=600,TabM=600,TabR=1200,SLAD=900,NCA_SCALE=1800)
 assert set(result['results'])==set(caps)
 for phase,cap in caps.items():
  r=read(phase+'_RESULT.json');assert r==result['results'][phase] and r['status']=='PASS' and r['seconds']<cap and r['rss_peak_mib']<7168
 pipeline=read('PIPELINE_RESULT.json');assert pipeline['fit_rows']==pipeline['cal_normal_rows']==1024 and pipeline['target_rows']==dict(CIC_DEV=64,UNSW_DEV=64,EDGE=32)
 enc=pipeline['encoder'];assert enc['encoded_rows']==112 and enc['encoded_batches']==7 and all(enc[k]==0 for k in ('e3_max_abs_error','cached_support_error','fresh_support_error'))
 f=read('FIDELITY_RESULT.json');assert f['official_benchmark_replication_pending'] and all(x['status']=='PASS' for x in f['checks'].values())
 assert f['checks']['TabM']['output_classes']==2 and f['checks']['TabM']['ensemble']=='mean probability'
 assert f['checks']['TabR']['faiss_vs_exhaustive_logit_error']<2e-5 and f['checks']['SLAD']['loss_formula_max_abs_error']<1e-12
 for phase in ('TabM','TabR','SLAD'):
  r=read(phase+'_RESULT.json');assert r['reload_exact'] and r['source_cal_weighted_fpr']<=.010000000001 and r['official_benchmark_replication_pending'] and r['formal_training_pending']
 n=read('NCA_SCALE_RESULT.json');assert n['full_pool_completed'] and n['all_candidates_included'] and n['source_fit_rows']==617908
 assert max(n['real_parity_errors'].values())<5e-4 and not n['training_gradient_chunking_qualified'] and n['full_training_pending']
 out=dict(status='PASS',scope='AUTHOR_SEMANTICS_AND_REAL_ENGINEERING_ONLY',job_id=job['job_id'],scheduler_elapsed_seconds=664,worker_seconds=result['seconds'],sampled_tree_peak_mib=max(r['rss_peak_mib'] for r in result['results'].values()),scheduler_maxrss_kib=6479828,conservative_peak_gib=max(6479828/1024**2,max(r['rss_peak_mib'] for r in result['results'].values())/1024),main_model_changed=False,formal_training_authorized=False,paper_benchmark_reproduction_pending=True,qualified_engineering_methods_cumulative=['TabM_corrected_v2','ModernNCA','DisentAD','TabR','SLAD'],source_fit_inference_candidates=617908,real_nca_max_log_probability_error=max(n['real_parity_errors'].values()),nca_training_scaling_pending=True,large_artifacts='HPC_ONLY',receipt_sha256=read('RETRIEVAL.json')['sha256'])
 (HERE/'ACCEPTANCE.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in out.items() if k!='receipt_sha256'}))
if __name__=='__main__':main()
