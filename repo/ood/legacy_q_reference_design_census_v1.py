"""Design-time metadata census only: no features, model, scores, or HOLDOUT queries."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import math
import legacy_reference_executor_common_v1 as c

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'runs/legacy_q_reference_correction_design_v1_20260922/census'
SALT = 'q-normal-verifier-component-cal-v1-20260922'
FOLDS = [ ['Amcrest Camera','Philips Hue Bridge'],
          ['SimCam','Atomi Coffee Maker'],
          ['ArloQ Camera','Globe Lamp'] ]


def main():
    c.require(not OUT.exists(), 'NEW_OUTPUT_REQUIRED')
    recipe=c.recipe(); specs=recipe['data']['manifests']
    for role in ('LEARN','DEV','REFERENCE'):
        c.pin(c.confined(ROOT,specs[role]['path']),specs[role]['sha256'])
    refs=defaultdict(list)
    for r in c.rows(c.confined(ROOT,specs['REFERENCE']['path'])):
        if r['partition'] in ('LEARN','DEV'):refs[r['device']].append(r)
    ref_components={d:{r['component_id'] for r in rr} for d,rr in refs.items()}
    counts=Counter(); components=defaultdict(set); activities=defaultdict(set)
    role_uids=defaultdict(list); assignments={}; component_roles={}; eligible_uids=defaultdict(list)
    all_normal_activities=defaultdict(set); main_counts=Counter(); groups=defaultdict(list)
    for role in ('LEARN','DEV'):
        for r in c.rows(c.confined(ROOT,specs[role]['path'])):
            d=r['device'];comp=r['component_id'];proto=r['protocol'];eligible=sum(s['protocol']==proto for s in refs[d])>=2
            c.require(all(s['timestamp']<=r['reference_end']<r['timestamp'] for s in refs[d]), 'REFERENCE_CAUSALITY')
            if role=='DEV': subrole='DEV_UNCHANGED'
            else:
                key=(d,comp)
                if key not in assignments:
                    h=hashlib.sha256((SALT+'|'+d+'|'+comp).encode()).hexdigest()
                    assignments[key]='CAL' if int(h,16)%5==0 and comp not in ref_components[d] else 'FIT'
                subrole=assignments[key]
                if comp in component_roles:c.require(component_roles[comp]==subrole,'CROSS_ROLE_COMPONENT')
                component_roles[comp]=subrole
                role_uids[subrole].append(r['uid'])
                if eligible:eligible_uids[subrole].append(r['uid'])
            key=(subrole,d,r['label'],r['activity'],proto,eligible)
            counts[key]+=1;components[key].add(comp);activities[subrole,d,r['label']].add(r['activity'])
            main_counts[subrole,d,r['label']]+=1
            if role=='LEARN' and r['label']==0:all_normal_activities[d].add(r['activity'])
            groups[(subrole,d)].append(r['uid'])
    c.require(len(role_uids['FIT'])+len(role_uids['CAL'])==specs['LEARN']['rows'],'LEARN_CONSERVATION')
    c.require(set(role_uids['FIT']).isdisjoint(role_uids['CAL']),'UID_ROLE_OVERLAP')
    summary=[]
    for (role,d,y),n in sorted(main_counts.items()):
        relevant=[k for k in counts if k[0:3]==(role,d,y)]
        summary.append(dict(role=role,device=d,label=y,rows=n,
            components=len(set().union(*(components[k] for k in relevant))),
            eligible_rows=sum(counts[k] for k in relevant if k[-1]),
            eligible_components=len(set().union(*(components[k] for k in relevant if k[-1]))),
            activities=sorted(activities[role,d,y])))
    fold_out=[]
    fit_devices={r['device'] for r in summary if r['role']=='FIT'}
    for i,held in enumerate(FOLDS):
        training=sorted(fit_devices-set(held));uids=[u for d in training for u in groups['FIT',d]]
        queries=[u for d in held for u in groups['FIT',d]]
        fold_out.append(dict(fold=i,held_devices=held,training_devices=training,train_rows=len(uids),
            train_uid_sha256=c.uid_sha(uids),oof_fit_rows=len(queries),oof_uid_sha256=c.uid_sha(queries),
            updates_per_seed=40*math.ceil(len(uids)/256)))
    source=ROOT/'runs/legacy_reference_hpc_preparation_v1_20260918/pullback/extracted/runs/real_dev/features_LEARN_DEV/cache.json'
    cache=c.load(source)
    OUT.mkdir()
    c.atomic_json(OUT/'data_plan.json',dict(status='DESIGN_METADATA_CENSUS',salt=SALT,
        split='All reference-sharing components FIT; other whole components: SHA256(salt|device|component) mod5 ==0 CAL, otherwise FIT',
        counts=summary,role_identity={k:dict(rows=len(v),uid_sha256=c.uid_sha(v),eligible_rows=len(eligible_uids[k]),eligible_uid_sha256=c.uid_sha(eligible_uids[k])) for k,v in role_uids.items()},
        cells=[dict(role=k[0],device=k[1],label=k[2],activity=k[3],protocol=k[4],eligible=k[5],rows=v,components=len(components[k])) for k,v in sorted(counts.items())],
        helper_folds=fold_out,normal_activities={d:sorted(a) for d,a in all_normal_activities.items()},
        references=[dict(device=d,rows=len(rr),protocol_counts=dict(Counter(r['protocol'] for r in rr)),activities=sorted({r['activity'] for r in rr})) for d,rr in sorted(refs.items())],
        cached_features={role:cache['roles'][role] for role in ('LEARN','DEV','REFERENCE')},
        required_float32_feature_bytes=sum(cache['roles'][k]['rows'] for k in ('LEARN','DEV','REFERENCE'))*768*4,
        no_model_forwards=True,no_optimizer_updates=True,no_threshold_computation=True,holdout_queries_opened=False,
        source_pins={specs[k]['path']:specs[k]['sha256'] for k in ('LEARN','DEV','REFERENCE')},script_sha256=c.sha(Path(__file__))))
    c.seal(OUT)
    print('DESIGN_CENSUS_COMPLETE',OUT,flush=True)


if __name__=='__main__':main()
