"""Verify small retrieved receipts and derive auditable diagnostic conclusions."""
import hashlib,json,math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def main():
    completion=read(HERE/'DIAGNOSIS_COMPLETION.json');assert completion['status']=='PASS'
    for n,h in completion['receipt_sha256'].items():assert sha(HERE/n)==h,n
    for n,h in read(HERE/'ARTIFACT_SHA256.json').items():assert sha(HERE/n)==h,n
    for n,h in read(HERE/'INPUT_PINS.json').items():assert sha(ROOT/n)==h,n
    resources={};results={}
    for phase in ['PREFLIGHT','CONTRIBUTION','GRADIENT']:
        r=read(HERE/(phase+'_RESULT.json'));results[phase]=r
        assert r['status']=='PASS' and r['optimizer_updates']==0
        assert all(r[k] is False for k in ['training','threshold_fitting','model_selection'])
        job=read(HERE/(phase+'_JOB.json'));scheduler=read(HERE/(phase+'_SCHEDULER.json'))
        assert scheduler['returncode']==0 and job['cpu']==1 and job['memory_gib']==8
        rows=[line.split('|') for line in scheduler['stdout'].splitlines()]
        main=next(x for x in rows if x[0]==job['job_id']);batch=next(x for x in rows if x[0]==job['job_id']+'.batch')
        assert main[1:3]==batch[1:3]==['COMPLETED','0:0']
        h,m,s=map(int,main[3].split(':'));assert batch[4].endswith('K')
        resources[phase]=dict(job_id=job['job_id'],elapsed_seconds=h*3600+m*60+s,scheduler_maxrss_kib=int(batch[4][:-1]),worker_sampled_rss_peak_bytes=r['rss_peak_bytes'])
    pre=results['PREFLIGHT']['real_encoder_distance']
    assert pre['status']=='PASS' and pre['encoded_rows']==112
    assert all(pre[k]==0 for k in ['e3_max_abs_error','cached_support_error','fresh_support_error'])
    c=results['CONTRIBUTION']['diagnosis'];g=results['GRADIENT']['diagnosis']
    assert set(c)=={'CIC_DEV','UNSW_DEV','EDGE'} and len(g['snapshots'])==21
    assert g['query_sample']['rows']==16384 and g['query_sample']['normal_rows']+g['query_sample']['attack_rows']==16384
    compact={};checked=0
    for pool,d in c.items():
        compact[pool]={}
        assert len(d['mapping'])==2 and all(v['singletons']==0 for v in d['mapping'].values())
        for arm,a in d['arms'].items():
            assert a['score_parity_max_error']==0
            for j,seed in enumerate([27,127,227]):
                assert a['model_fingerprint'][j]==g['snapshots'][f'{arm}_{seed}_epoch40']['model_fingerprint']
            compact[pool][arm]={}
            base=a['variants']['ACTUAL']
            assert set(a['variants'])=={'ACTUAL','ZERO','SHUFFLE_20261105','SHUFFLE_20261106'}
            for variant,groups in a['variants'].items():
                assert set(groups)==set(base)
                compact[pool][arm][variant]={}
                for group,heads in groups.items():
                    assert set(heads)=={'27','127','227','ensemble'}
                    for h,v in heads.items():
                        b=base[group][h]
                        assert v['rows']==b['rows']
                        assert v['alarm_count']==b['alarm_count']+v['added_alarms']-v['removed_alarms']
                        assert 0<=v['alarm_count']<=v['rows']
                        for name in ['margin','score_delta_from_actual']:
                            values=list(v[name].values());assert all(math.isfinite(x) for x in values) and values==sorted(values)
                        checked+=1
                    if group in ['label:0','label:1','source_role:HTTP','source_role:UDP']:
                        compact[pool][arm][variant][group]=heads
    gradient=[]
    for key,v in g['snapshots'].items():
        assert v['epoch'] in ([40] if v['arm']=='FUSION790' else [0,1,5,10,20,40])
        assert all(math.isfinite(x) and x>=0 for x in v['loss_means'].values())
        assert len(v['mean_gradient'])==5
        for block,b in v['batch_relations'].items():
            assert b['total_batches']==64 and 0<=b['negative_dot_batches']<=b['interpretable_batches']<=64
            r=v['mean_gradient'][block]['classification_vs_anchor']
            if r['cosine'] is not None:
                assert -1-1e-12<=r['cosine']<=1+1e-12
                assert math.isclose(r['dot'],r['classification_norm']*r['anchor_norm']*r['cosine'],rel_tol=1e-12,abs_tol=1e-30)
            gradient.append(dict(snapshot=key,block=block,**r,batch_negative=b['negative_dot_batches'],batch_interpretable=b['interpretable_batches']))
    for seed in ['27','127','227']:
        trajectory=g['recorded_objective_trajectory'][seed];assert [v['epoch'] for v in trajectory]==list(range(1,41))
        for v in trajectory:
            m=v['mean'];assert math.isclose(m['BCE']+m['TAIL']+m['ANCHOR'],m['TOTAL'],rel_tol=1e-6,abs_tol=1e-10)
    summary=dict(contribution=compact,gradient=gradient,query_sample=g['query_sample'],recorded_objective_trajectory=g['recorded_objective_trajectory'])
    write('DIAGNOSTIC_SUMMARY.json',summary)
    evidence=dict()
    for arm in ['FUSION790','ANCHOR790']:
        a=c['EDGE']['arms'][arm]['variants'];v=a['ACTUAL']['source_role:UDP']['ensemble'];z=a['ZERO']['source_role:UDP']['ensemble']
        evidence[arm]=dict(actual_alarm_count=v['alarm_count'],zero_alarm_count=z['alarm_count'],actual_margin_median=v['margin']['p50'],zero_margin_median=z['margin']['p50'],context_uplift_median=-z['score_delta_from_actual']['p50'])
    audit=dict(result='PASS',scope='DIAGNOSTIC_ENGINEERING_AND_EVIDENCE_ACCEPTANCE_NOT_MODEL_REPAIR',model_repair_status='UNRESOLVED_PRIOR_ANCHOR790_SCIENTIFIC_FAIL_RETAINED',
               resources=resources,total_scheduler_seconds=sum(v['elapsed_seconds'] for v in resources.values()),
               max_worker_sampled_rss_gib=max(v['worker_sampled_rss_peak_bytes'] for v in resources.values())/2**30,
               max_scheduler_rss_gib=max(v['scheduler_maxrss_kib'] for v in resources.values())/2**20,
               receipt_sha256=completion['receipt_sha256'],summary_sha256=sha(HERE/'DIAGNOSTIC_SUMMARY.json'),checked_intervention_cohort_heads=checked,
               endpoint_score_parity='exact on all three datasets for both arms; all seeds and ensemble',
               source_and_external_head_fingerprints_match=True,source_snapshot_count=21,source_probe_batches_per_snapshot=64,
               edge_udp=evidence,
               supported=['Context8 is read and has nonzero functional effects; original fusion UDP alarms disappear under zero intervention',
                          'Anchored UDP context uplift shrinks and zero-context baseline margin moves far below threshold',
                          'At epoch1 all seeds show opposing average classification-vs-anchor gradients at ALL and CONTEXT8 blocks',
                          'Late source classification gradients are saturated while anchor data gradients dominate in magnitude; conflict signs are not universal'],
               not_proven=['Complete causal reconstruction of historical Adam updates or weight decay effects',
                           'External epoch of UDP gain loss; intermediate checkpoints were source-only',
                           'Specific replacement objective effectiveness or source-domain hard-negative coverage',
                           'All-future/all-protocol feature extraction correctness or independent external generalization'],
               next_direction='Preserve context-enabled fusion discrimination; abandon full-logit imitation of weak 782 teacher. Specify source-only normal-risk and attack-margin protections before a new small trial; no new training authorized or started by this audit.',
               remote_artifacts={pool:d['arrays'] for pool,d in c.items()},
               remote_batch_summary_sha256={key+'_BATCH_GRADIENTS.json':v['batch_receipt_sha256'] for key,v in g['snapshots'].items()})
    write('FINAL_DIAGNOSIS_ACCEPTANCE.json',audit)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),constrained_layout=True)
    for j,arm in enumerate(['FUSION790','ANCHOR790']):
        e=evidence[arm]
        axes[0].bar(j-.17,e['zero_margin_median'],width=.32,color='#999999',label='Zero context' if j==0 else None)
        axes[0].bar(j+.17,e['actual_margin_median'],width=.32,color=['#148b9a','#b84444'][j],label='Actual context' if j==0 else None)
        for x,key in [(j-.17,'zero_margin_median'),(j+.17,'actual_margin_median')]:axes[0].annotate(f'{e[key]:.2f}',(x,e[key]),xytext=(0,4 if e[key]>0 else -12),textcoords='offset points',ha='center',fontsize=9)
    axes[0].axhline(0,color='black',lw=1);axes[0].set(ylim=(-21,7),xticks=[0,1],xticklabels=['Fusion790','Anchor790'],ylabel='RAW score minus fixed threshold',title='Edge UDP: ensemble median margin');axes[0].legend(fontsize=8)
    for seed,color in zip([27,127,227],['#148b9a','#be7d00','#b84444']):
        epochs=[1,5,10,20,40]
        ratios=[g['snapshots'][f'ANCHOR790_{seed}_epoch{e}']['mean_gradient']['CONTEXT8']['classification_vs_anchor']['anchor_to_classification_norm'] for e in epochs]
        axes[1].plot(epochs,ratios,'o-',color=color,label=str(seed))
    axes[1].axhline(1,color='black',lw=1,ls='--');axes[1].set(yscale='log',xlabel='Saved source-only checkpoint epoch',ylabel='Anchor / classification gradient norm',title='Context8 parameter block (sampled FIT)');axes[1].legend(title='Seed',fontsize=8)
    fig.suptitle('Frozen diagnostic evidence; not a repaired-model evaluation',fontsize=12)
    fig.savefig(HERE/'DIAGNOSIS_EVIDENCE.png',dpi=170);plt.close(fig)
    print(json.dumps(dict(result=audit['result'],checks=checked,seconds=audit['total_scheduler_seconds'],peak_gib=audit['max_worker_sampled_rss_gib'],udp=evidence)))

if __name__=='__main__':main()
