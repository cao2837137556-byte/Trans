"""Paired categorical gates; zero denominators never qualify."""
from collections import defaultdict
import math
import issue27frontend_paired_train_support_v1 as s


def compact_result(result):
    return {'status':'PAIRED_COMPARISON_COMPLETE','A_retention':result['A_retention'],
            'B_normal_increment':result['B_normal_increment']['status'],
            'B_attack_increment':result['B_attack_increment']['status'],'independent_confirmation':False}


def evaluate(contexts, predictions):
    wanted={t['uid']:t for c in contexts for t in c['targets']}
    s.require(set(wanted)==set(predictions),'PREDICTION_UIDS')
    rows=[]
    for uid,t in sorted(wanted.items()):
        q=predictions[uid];s.require(type(q) is float and math.isfinite(q),'PREDICTION_FINITE')
        rows.append({**t,'logit':q,'hard':int(q>=0),'error':int(q>=0)!=t['label']})
    return rows


def counts(rows):
    return {'targets':len(rows),'contexts':len({r['context_key'] for r in rows}),
            'components':len({r['component_id'] for r in rows}),
            'errors':sum(r['error'] for r in rows),
            'error_contexts':len({r['context_key'] for r in rows if r['error']}),
            'error_components':len({r['component_id'] for r in rows if r['error']}),
            'old_correct_new_wrong':sum(r['owner']=='A' and r['old_hard']==r['label'] and r['error'] for r in rows),
            'old_wrong_new_correct':sum(r['owner']=='A' and r['old_hard']!=r['label'] and not r['error'] for r in rows),
            'evidence':'EXPOSED_DEVELOPMENT' if rows else 'NOT_ESTABLISHED'}


def comparison(contexts, predictions_a, predictions_ab):
    check=s.views(contexts,'check','AB')
    a=evaluate(check,predictions_a);ab=evaluate(check,predictions_ab)
    pairs=list(zip(a,ab))
    covered={(t['owner'],t['label'],t['attack_family'] if t['label'] else t['device_family'])
             for c in contexts if c['role']=='train' for t in c['targets']}
    for rows in (a,ab):
        for r in rows:
            r['training_covered']=(r['owner'],r['label'],r['attack_family'] if r['label'] else r['device_family']) in covered
    gates={}
    for name,rows in (('A',a),('AB',ab)):
        gates[name]={}
        for label in (0,1):
            part=[r for r in rows if r['owner']=='A' and r['label']==label]
            n=sum(r['old_hard']==label for r in part)
            gates[name][str(label)]=('NOT_ESTABLISHED' if not n else
                'PASS' if counts(part)['old_correct_new_wrong']==0 else 'FAIL')
    negative=sum(x['owner']=='A' and not x['error'] and y['error'] for x,y in pairs)
    retention='PASS' if all(v=='PASS' for d in gates.values() for v in d.values()) and not negative else (
        'FAIL' if negative or any(v=='FAIL' for d in gates.values() for v in d.values()) else 'NOT_ESTABLISHED')
    increments={}
    for label in (0,1):
        p=[(x,y) for x,y in pairs if x['owner']=='B' and x['label']==label]
        cells=defaultdict(list)
        for x,y in p:cells[(x['attack_family'] if label else x['device_family'],x['source_group'])].append((x,y))
        table=[]
        for key,vs in sorted(cells.items()):
            ca,cb=counts([x for x,y in vs]),counts([y for x,y in vs])
            table.append({'family':key[0],'source_group':key[1],'A':ca,'AB':cb,
                'no_regression':cb['errors']<=ca['errors'] and cb['error_contexts']<=ca['error_contexts']})
        ca,cb=counts([x for x,y in p]),counts([y for x,y in p])
        increments[str(label)]={'A':ca,'AB':cb,'cells':table,'status':'NOT_ESTABLISHED' if not p else
            'PASS' if cb['errors']<ca['errors'] and all(r['no_regression'] for r in table) else 'NOT_DEMONSTRATED'}
    attack_regressions=sum(x['owner']=='B' and x['label']==1 and not x['error'] and y['error'] for x,y in pairs)
    if attack_regressions or any(not r['no_regression'] for r in increments['1']['cells']):
        if increments['0']['status']=='PASS':increments['0']['status']='BLOCKED_BY_B_ATTACK_REGRESSION'
    groups=[]
    for fields in (('owner','label'),('owner','label','attack_family'),('owner','label','device_family'),
                   ('owner','label','source_group','member'),('owner','label','training_covered'),
                   ('owner','label','context_key'),('owner','label','component_id')):
        keys=sorted({tuple(r[f] for f in fields) for r in a},key=str)
        for key in keys:
            groups.append({'dimensions':list(fields),'values':list(key),
                'A':counts([r for r in a if tuple(r[f] for f in fields)==key]),
                'AB':counts([r for r in ab if tuple(r[f] for f in fields)==key])})
    flips=[{'uid':x['uid'],'context':x['context_key'],'component':x['component_id'],'owner':x['owner'],
            'label':x['label'],'A_hard':x['hard'],'AB_hard':y['hard']} for x,y in pairs if x['hard']!=y['hard']]
    return {'status':'PAIRED_COMPARISON_COMPLETE','A_retention':retention,'old_reference_gates':gates,
            'A_to_AB_negative_flips':negative,'B_normal_increment':increments['0'],
            'B_attack_increment':increments['1'],'B_attack_negative_flips':attack_regressions,
            'groups':groups,'flips':flips,'check_targets':len(a),'independent_confirmation':False,
            'new_device':'NOT_TESTED','deployment':False}, {'A':a,'AB':ab}
