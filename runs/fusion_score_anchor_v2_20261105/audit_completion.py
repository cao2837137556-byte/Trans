"""Audit retrieved scheduler/results; no model fitting or external score reading."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'device_context_head_training_v2_20261105'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,allow_nan=False)+'\n').encode())
def elapsed(s):
    parts=s.split(':');assert len(parts)==3
    return int(parts[0])*3600+int(parts[1])*60+int(parts[2])
def main():
    accepted=read(HERE/'TRAINING_COMPLETION.json');assert accepted['scope']=='TRAINING_AND_SOURCE_CAL_ONLY'
    for n,h in accepted['receipt_sha256'].items():assert sha(HERE/n)==h,n
    for n,h in read(HERE/'DELIVERY.json')['pins'].items():assert sha(HERE/n)==h,n
    state=read(HERE/'CHAIN_STATE.json');assert state['stage']=='ANCHOR_TRAINING_COMPLETE' and state['completed_phases']==6
    phases=['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','TRAIN_27','TRAIN_127','TRAIN_227','CALIBRATION'];timing={};peak=0
    for phase in phases:
        job=read(HERE/(phase+'_JOB.json'));result=read(HERE/(phase+'_RESULT.json'));sched=read(HERE/(phase+'_SCHEDULER.json'))
        assert not state.get(phase+'_STOP') and result['status']=='PASS'
        lines=[line.split('|') for line in sched['stdout'].splitlines()]
        row=next(v for v in lines if v[0]==job['job_id']);assert row[1:3]==['COMPLETED','0:0']
        assert row[5]=='1' and row[6]=='8G' and job['cpu']==1 and job['memory_gib']==8
        timing[phase]=dict(job_id=job['job_id'],elapsed_seconds=elapsed(row[3]),worker_seconds=result['seconds'])
        peak=max(peak,result.get('rss_peak_bytes',0))
        for row in lines:
            rss=row[4]
            if rss:peak=max(peak,float(rss[:-1])*{'K':1024,'M':1024**2,'G':1024**3}[rss[-1]])
    assert peak<8*1024**3
    assert read(HERE/'LINUX_REGRESSION.json')['status']=='PASS' and read(HERE/'LINUX_THREAD_REGRESSION.json')['status']=='PASS'
    table={};artifacts={};heads={}
    for seed in [27,127,227]:
        new=read(HERE/f'TRAIN_{seed}_RESULT.json');old=read(PARENT/f'TRAIN_REFIT782_{seed}_RESULT.json');fusion=read(PARENT/f'TRAIN_FUSION790_{seed}_RESULT.json')
        assert new['seed']==seed and new['updates']==96560 and new['epochs']==40 and new['epoch_checkpoints']==40 and not new['runtime_gate_only']
        assert len(new['profile'])==40 and all(e['epoch']==i+1 and e['batches']==2414 for i,e in enumerate(new['profile']))
        assert not new['external_data_used_for_training']
        cal=new['calibration'];assert cal['status']=='PASS' and cal['normal_rows']==33147 and cal['checkpoint_score_readback']
        assert cal['cal_uid_sha256']==old['calibration']['cal_uid_sha256']==fusion['calibration']['cal_uid_sha256']
        assert cal['weighted_normal_fpr']<=.01+1e-14 and cal['scale']>0
        assert math.isclose(cal['scale'],cal['q90']-cal['q10'],abs_tol=1e-12)
        assert new['teacher_scale']==old['calibration']['scale']
        assert math.isclose(new['scale_ratio'],cal['scale']/new['teacher_scale'],abs_tol=1e-14)
        table[str(seed)]={name:dict(scale=r['calibration']['scale'],cut=r['calibration']['cut'],weighted_cal_normal_fpr=r['calibration']['weighted_normal_fpr'],sample_cal_normal_fpr=r['calibration']['unweighted_normal_fpr'],c5_max_deduction=.25*r['calibration']['scale']) for name,r in [('OLD782_MATCHED',old),('FUSION790',fusion),('ANCHOR790',new)]}
        table[str(seed)]['anchor_scale_change_from_teacher_percent']=100*(new['scale_ratio']-1)
        remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name+'/heads/ANCHOR790_'+str(seed)
        artifacts[str(seed)]={remote+'/train/head.npz':new['head_sha256'],remote+'/train/endpoint.json':new['endpoint_sha256'],**{remote+'/calibration/'+role+'_logits.npy':digest for role,digest in cal['logits_sha256'].items()}}
        heads[str(seed)]=dict(head_sha256=new['head_sha256'],cut=cal['cut'],scale=cal['scale'],updates=96560,epoch_checkpoints=40)
    ensemble=read(HERE/'CALIBRATION_RESULT.json')['ensemble']
    assert ensemble['seeds']==[27,127,227] and not ensemble['runtime_gate_only'] and ensemble['normal_rows']==33147 and ensemble['weighted_normal_fpr']<=.01+1e-14
    write('SOURCE_COMPARISON.json',dict(heads=table,ensemble=ensemble,interpretation='Source scale/threshold diagnostics only; CAL FPR is fitted, not external generalization evidence'))
    write('REMOTE_ARTIFACTS.json',dict(sha256=artifacts,epoch_checkpoints=120,epoch_manifest_location='Each head train/SHA256SUMS; trainer sealed and verified; epoch arrays not downloaded'))
    report=dict(status='PASS',scope='TRAINING_SOURCE_CAL_AND_RECEIPT_AUDIT',new_heads=3,epochs_per_head=40,optimizer_updates=289680,epoch_checkpoints=120,elapsed_seconds=sum(v['elapsed_seconds'] for v in timing.values()),formal_training_elapsed_seconds=sum(timing['TRAIN_'+str(seed)]['elapsed_seconds'] for seed in [27,127,227]),peak_rss_bytes=int(peak),peak_rss_gib=peak/1024**3,phases=timing,receipt_pins_verified=len(accepted['receipt_sha256']),external_evaluation_completed=False,effectiveness_unknown=True,failed_v1_elapsed_seconds_separate=187)
    write('COMPLETION_AUDIT.json',report)
    write('FINAL_TRAINING_ACCEPTANCE.json',dict(result='PASS',scope='TRAINING_AND_SOURCE_CALIBRATION_ONLY',heads=heads,ensemble=ensemble,evaluation_pending=True,receipt_sha256={**accepted['receipt_sha256'],**{n:sha(HERE/n) for n in ['COMPLETION_AUDIT.json','SOURCE_COMPARISON.json','REMOTE_ARTIFACTS.json','SPEC.json']}}))
    print(json.dumps(dict(status='PASS',elapsed_seconds=report['elapsed_seconds'],training_seconds=report['formal_training_elapsed_seconds'],peak_gib=report['peak_rss_gib'],ensemble_fpr=ensemble['weighted_normal_fpr'],scale_change_percent=[table[str(seed)]['anchor_scale_change_from_teacher_percent'] for seed in [27,127,227]])))
if __name__=='__main__':main()
