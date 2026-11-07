"""Display targets separately from frozen scientific gates and sampling bases."""
ARMS=['FUSION790','RISK_UNIFORM','RISK_STRATIFIED','RISK_GUARDED']
HEADS=['27','127','227','ensemble']
def target(fpr,recalls):
    if fpr is None or not recalls or any(v is None for v in recalls):return 'NOT_EVALUABLE'
    return 'PASS' if fpr<.02 and all(v>=.999 for v in recalls) else 'FAIL'
def extract(report,edge=False):
    out=[]
    for arm in ARMS:
        for method in ['RAW','C5_P3']:
            for head in HEADS:
                if edge:
                    roles=report[arm]['methods'][method]['heads'][head]['roles']
                    for basis,key in [('sample','exact_selected_sample_alarm_rate'),('HT','ht_population_alarm_estimate'),('hierarchical','selected_hierarchical_alarm_rate')]:
                        f=roles['NORMAL'][key];http=roles['HTTP'][key];udp=roles['UDP'][key]
                        out.append(dict(arm=arm,method=method,head=head,basis=basis,normal=roles['NORMAL']['selected_rows'],fp=roles['NORMAL']['alarm_count'],fpr=f,http=http,udp=udp,target=target(f,[http,udp])))
                else:
                    g=report[arm][method][head]['groups']['pool'];n=g['normal'];a=g['attack']
                    for basis,key in [('sample','unweighted_rate'),('hierarchical','weighted_rate')]:
                        f=n[key];rec=a[key]
                        out.append(dict(arm=arm,method=method,head=head,basis=basis,normal=n['rows'],fp=n['alarm_count'],attack=a['rows'],tp=a['alarm_count'],fpr=f,recall=rec,target=target(f,[rec])))
    return out
