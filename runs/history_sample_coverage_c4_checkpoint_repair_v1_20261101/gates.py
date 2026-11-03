"""Pure C4 acceptance predicates; goals and adoption are different outcomes."""
import numpy as np

NET='unsw-attack-traces-2018:70:ee:50:18:34:43'
GROUP={NET,'unsw-attack-traces-2018:00:16:6c:ab:6b:88','unsw-attack-traces-2018:50:c7:bf:00:56:39','unsw-attack-traces-2018:ec:1a:59:79:f4:89'}
HEAVY={'unsw-attack-traces-2018:00:16:6c:ab:6b:88','unsw-attack-traces-2018:ec:1a:59:79:f4:89'}

def dev_gate(rows,before,after):
    if {r['device'] for r in rows}!=GROUP or any(r['label']!=0 or r['use']=='REFERENCE' for r in rows):raise ValueError('DEV_POPULATION')
    if before.shape!=(len(rows),4) or after.shape!=(len(rows),4):raise ValueError('DEV_SHAPE')
    if before.dtype!=np.bool_ or after.dtype!=np.bool_:raise ValueError('DEV_BOOL')
    failures=[];groups=[]
    if np.any(~before & after):failures.append('ANY_HEAD_NEW_NORMAL_ALARM')
    for device in sorted(GROUP):
        ix=np.array([r['device']==device for r in rows]);old=int(before[ix,3].sum());new=int(after[ix,3].sum())
        if not 0<int(ix.sum())<=4096:raise ValueError('DEV_DEVICE_COUNT')
        if device==NET and new>=old:failures.append('NETATMO_NO_STRICT_IMPROVEMENT_VS_RAW')
        groups.append(dict(device=device,rows=int(ix.sum()),before_fp=old,after_fp=new))
    if after[:,3].sum()>=before[:,3].sum():failures.append('POOLED_NO_STRICT_IMPROVEMENT')
    heavy=np.array([r['device'] in HEAVY for r in rows])
    if after[heavy,3].sum()>=before[heavy,3].sum():failures.append('SAMSUNG_POWER_NO_STRICT_IMPROVEMENT')
    return dict(status='PASS_DEV' if not failures else 'STOP_DEV_FAIL',failures=failures,groups=groups,
        before_fp=int(before[:,3].sum()),after_fp=int(after[:,3].sum()),rows=len(rows),no_AB_loaded=True)

def final_gate(previous,pools,normal_regressions,attack_withdrawals,untouched_exact):
    failures=[]
    if normal_regressions:failures.append('NORMAL_REGRESSION')
    if attack_withdrawals:failures.append('NEW_B_ATTACK_WITHDRAWAL')
    if not untouched_exact:failures.append('UNTOUCHED_NOT_EXACT')
    for pool in pools:
        for view in pools[pool]['views']:
            old=previous[pool]['views'][view];new=pools[pool]['views'][view]
            if old['retained_uid_sha256']!=new['retained_uid_sha256'] or old['weights_sha256']!=new['weights_sha256']:raise ValueError('POPULATION_OR_WEIGHT_CHANGED')
            for suffix,report in new['reports'].items():
                if report['protection']['status']!='PASS':failures.append(pool+'/'+view+'/'+suffix+'/PROTECTION')
    a=previous['UNSW_DEV']['views']['post_window_primary']['reports']['ensemble']['corrected']['normal']
    b=pools['UNSW_DEV']['views']['post_window_primary']['reports']['ensemble']['corrected']['normal']
    if b['rows']!=a['rows'] or b['rows']!=74444:raise ValueError('B_PRIMARY_DENOMINATOR')
    if b['positive']>=a['positive']:failures.append('NO_B_SAMPLE_FPR_IMPROVEMENT')
    adopted=not failures
    return dict(status='ADOPT_C4' if adopted else 'REJECT_C4_KEEP_C3',failures=failures,
        old_fp=a['positive'],new_fp=b['positive'],normal_rows=b['rows'],old_sample_fpr=a['rate'],new_sample_fpr=b['rate'],
        target_2pct_met=b['positive']<=1488,method_frozen=True,no_further_AB_search=True,
        adoption_rule='All safety/nonregression gates plus strict B sample-FPR improvement; 2% separately reported.')
