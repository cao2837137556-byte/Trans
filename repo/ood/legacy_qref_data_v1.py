"""Pinned cache joins and whole-component roles; no feature decoder or HOLDOUT loader."""
from collections import defaultdict, Counter
from pathlib import Path
import hashlib
import math
import numpy as np
import legacy_qref_common_v1 as c


def metadata_valid(rows, partition, reference=False):
    c.require(bool(rows) and len({r['uid'] for r in rows}) == len(rows), 'EMPTY_OR_DUPLICATE_UID')
    for r in rows:
        c.require(r['partition'] in partition and r['protocol'] in (6,17), 'ROLE_OR_PROTOCOL')
        c.require(r['label'] in (0,1) and math.isfinite(r['timestamp']) and math.isfinite(r['reference_end']), 'LABEL_OR_TIME')
        if reference:
            c.require(r['use'] == 'REFERENCE' and r['label'] == 0 and r['timestamp'] <= r['reference_end'], 'REFERENCE_INVALID')
        else:
            c.require(r['use'] != 'REFERENCE' and r['reference_end'] < r['timestamp'], 'QUERY_CAUSALITY')


def split(rows, refs, salt):
    metadata_valid(rows, {'LEARN'})
    metadata_valid(refs, {'LEARN'}, True)
    components = defaultdict(set)
    for r in refs:
        components[r['device']].add(r['component_id'])
    roles = {}; answer = defaultdict(list)
    for i,r in enumerate(rows):
        text = salt+'|'+r['device']+'|'+r['component_id']
        cal = r['component_id'] not in components[r['device']] and int(hashlib.sha256(text.encode()).hexdigest(),16)%5 == 0
        role = 'CAL' if cal else 'FIT'
        c.require(roles.setdefault(r['component_id'],role) == role, 'CROSS_COMPONENT_ROLE')
        answer[role].append(i)
    c.require(set(answer['FIT']).isdisjoint(answer['CAL']), 'FIT_CAL_OVERLAP')
    return {k:np.asarray(v,dtype=np.int64) for k,v in answer.items()}


def class_weights(rows):
    """One-class hierarchy, including only nonempty branches; sums to one."""
    c.require(rows and len({r['label'] for r in rows}) == 1, 'SINGLE_CLASS_REQUIRED')
    branches = defaultdict(set); counts = Counter()
    fields = ('device','activity','capture_id','session_id')
    for r in rows:
        key = tuple(r[f] for f in fields)
        for depth in range(4):
            branches[key[:depth]].add(key[depth])
        counts[key] += 1
    values = []
    for r in rows:
        key = tuple(r[f] for f in fields)
        denominator = counts[key] * math.prod(len(branches[key[:d]]) for d in range(4))
        values.append(1/denominator)
    weights = np.array(values, dtype=np.float64)
    c.require(math.isclose(math.fsum(weights),1,abs_tol=1e-12), 'WEIGHT_MASS')
    return weights


def weights(rows, hard=None):
    c.require(all(r['partition']=='LEARN' and r.get('fit_role')=='FIT' for r in rows), 'OPTIMIZER_FIT_ONLY')
    result = np.zeros(len(rows),dtype=np.float64)
    for label in (0,1):
        ix = [i for i,r in enumerate(rows) if r['label']==label]
        c.require(bool(ix),'MISSING_TRAIN_CLASS')
        result[ix] = (.25 if label==0 and hard is not None else .5)*class_weights([rows[i] for i in ix])
    if hard is not None:
        ix = [i for i,r in enumerate(rows) if r['uid'] in hard]
        c.require(len(ix)==len(hard) and all(rows[i]['label']==0 for i in ix),'H_NOT_FIT_NORMAL')
        result[ix] += .25*class_weights([rows[i] for i in ix])
    c.require(math.isclose(math.fsum(result),1,abs_tol=1e-12),'TOTAL_WEIGHT_MASS')
    return result


def load_cache(root, cache_dir, recipe):
    root, cache_dir = Path(root), Path(cache_dir)
    cache = c.read(cache_dir/'cache.json')
    c.require(cache['status']=='COMPLETE' and cache['stage']=='LEARN_DEV' and not cache.get('synthetic_only',True), 'CACHE_CONTRACT')
    loaded = {}
    for role in ('REFERENCE','LEARN','DEV'):
        spec = recipe['data']['cache'][role]
        c.require(cache['roles'][role] == spec, 'CACHE_MANIFEST_DRIFT')
        meta = c.rows(c.pin(c.confined(cache_dir,spec['metadata']),spec['metadata_sha256']))
        metadata_valid(meta, {'LEARN','DEV'} if role=='REFERENCE' else {role}, role=='REFERENCE')
        c.require(len(meta)==spec['rows'] and c.uid_sha(r['uid'] for r in meta)==spec['uid_sha256'], 'CACHE_UIDS')
        source = recipe['data']['manifests'][role]
        original = c.rows(c.pin(c.confined(root,source['path']),source['sha256']))
        if role=='REFERENCE':
            original = [r for r in original if r['partition'] in ('LEARN','DEV')]
        c.require(len(original)==len(meta), 'SOURCE_COUNT')
        # Cache may carry extra annotations; all original scientific fields must agree in order.
        for a,b in zip(original,meta):
            c.require(all(k in b and b[k]==v for k,v in a.items()), 'CACHE_METADATA_JOIN')
        arr = np.load(c.pin(c.confined(cache_dir,spec['features']),spec['features_sha256']),mmap_mode='r',allow_pickle=False)
        c.require(arr.dtype==np.float32 and arr.shape==(len(meta),768), 'CACHE_ARRAY_SHAPE')
        for start in range(0,len(arr),4096):
            c.require(np.isfinite(arr[start:start+4096]).all(), 'CACHE_NONFINITE')
        loaded[role]=(meta,arr)
    refs = loaded['REFERENCE'][0]
    registry={}
    for r in refs:
        key=(r['partition'],r['device'])
        c.require(registry.setdefault(key,r['reference_end'])==r['reference_end'],'REGISTRATION_END')
    for role in ('LEARN','DEV'):
        for r in loaded[role][0]:
            c.require(registry.get((role,r['device']))==r['reference_end'],'REGISTRATION_IDENTITY')
    learn_refs = [r for r in refs if r['partition']=='LEARN']
    c.require(len(learn_refs)==104 and len(refs)==179,'REFERENCE_COUNT')
    roles = split(loaded['LEARN'][0],learn_refs,recipe['data']['split_salt'])
    for role,ix in roles.items():
        selected = [loaded['LEARN'][0][int(i)] for i in ix]
        spec = recipe['data']['role_identity'][role]
        c.require(len(ix)==spec['rows'] and c.uid_sha(r['uid'] for r in selected)==spec['uid_sha256'],'SPLIT_IDENTITY')
        for r in selected:
            r['fit_role']=role
    return loaded, roles


def validate_controls(rows, refs, recipe):
    by_uid = {r['uid']:r for r in refs}
    for ctrl in recipe['evaluation']['controls']:
        rr = [r for r in rows if r['device']==ctrl['device'] and r['protocol']==ctrl['protocol']]
        c.require(len(rr)==ctrl['rows'],'CONTROL_DENOMINATOR')
        if ctrl['status']!='MATCHED':
            continue
        c.require(c.uid_sha(r['uid'] for r in rr)==ctrl['query_uid_sha256'],'CONTROL_QUERY_IDENTITY')
        for key,device in [('correct_reference_uids',ctrl['device']),('wrong_reference_uids',ctrl['donor'])]:
            chosen = [by_uid[u] for u in ctrl[key]]
            c.require(len(chosen)==len({r['component_id'] for r in chosen})==ctrl['count'],'CONTROL_COMPONENT_COUNT')
            c.require(all(r['device']==device and r['protocol']==ctrl['protocol'] and r['reference_end']<min(q['timestamp'] for q in rr) for r in chosen),'CONTROL_PROTOCOL_TIME_OWNER')
