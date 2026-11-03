"""Bind the completed 20261022 heads/cache to the unchanged onboarding algorithm.

No historical-parent impersonation, training, threshold fitting or E3 extraction.
"""
import importlib
from collections import Counter
from pathlib import Path
import sys
import numpy as np
import torch

HERE = Path(__file__).resolve().parent


def bootstrap(config, strict_versions=True):
    lineage = Path(config['lineage_root']).resolve()
    sys.path.insert(0, str(lineage))
    import lineage_core as lc
    lc.pin(lineage/'code_manifest.json', config['lineage_manifest_sha256'])
    frozen = HERE/'frozen_onboarding'
    lc.verify(frozen, config['onboarding_seal_sha256'])
    # This identical legacy declaration loader resolves three decoder files
    # relative to __file__. They exist in the full onboarding package, whereas
    # the head-only package intentionally omits them. Select its pinned provider
    # before query imports transitively import it; no constants/code are patched.
    loader='legacy_cic2022_two_camera_semantic_probe_v1'
    lc.require(lc.sha(frozen/'repo/ood'/(loader+'.py')) ==
               lc.sha(Path(config['query_root'])/'repo/ood'/(loader+'.py')), 'DECODER_LOADER_DRIFT')
    sys.path.insert(0,str(frozen/'repo/ood'))
    try: decoder_module=importlib.import_module(loader)
    finally: sys.path.pop(0)
    lc.require(Path(decoder_module.__file__).resolve().parent == (frozen/'repo/ood').resolve(), 'DECODER_LOADER_PROVIDER')
    modules, design, _ = lc.bootstrap(config['query_root'], strict_versions=strict_versions)
    sys.path.append(str(frozen/'repo/ood'))
    # Duplicated scientific dependencies must be identical; never shadow versions.
    for name in ('continuous_common_v3.py','continuous_input_v3.py','query_tail_core_v2.py',
                 'query_tail_train_v2.py','query_tail_prepare_v2.py'):
        lc.require(lc.sha(frozen/'repo/ood'/name) == lc.sha(Path(config['query_root'])/'repo/ood'/name),
                   'SCIENTIFIC_DEPENDENCY_DRIFT:'+name)
    names = ('constrained_onboarding_query_tail_adapter_v2','constrained_onboarding_runner_v2',
             'constrained_onboarding_reference_v2','onboarding_delivery_v1')
    for name in names:
        module = importlib.import_module(name)
        lc.require(Path(module.__file__).resolve().parent == (frozen/'repo/ood').resolve(),
                   'ONBOARDING_IMPORT_SHADOW:'+name)
        modules[name] = module
    lc.pin(frozen/'protocol.json', modules[names[0]].PROTOCOL_SHA256)
    return lc, modules, design


def validate_prepared(cache, run, binding, complete, design, indices, norm, lc, modules):
    p, c = modules['query_tail_prepare_v2'], modules['query_tail_core_v2'].c
    old = modules['constrained_onboarding_query_tail_adapter_v2']
    for stage in ('P','T','K'):
        lc.pin(run/f'LINEAGE_{stage}_COMPLETE.json', complete[stage+'_sha256'])
    prepared = lc.read(run/'LINEAGE_P_COMPLETE.json')
    lc.require(prepared['status']=='COMPLETE' and prepared['lineage']==lc.LINEAGE
               and prepared['cache_binding_digest']==c.digest(binding), 'PREPARED_CACHE_BINDING')
    lc.verify(run/'prepared', prepared['prepared_seal_sha256'])
    receipt=lc.read(run/'prepared/receipt.json')
    lc.require(receipt['status']=='COMPLETE' and receipt['lineage']==lc.LINEAGE
               and receipt['binding_digest']==c.digest(binding)
               and receipt['descriptor_rows']==sum(old.EXPECTED_COUNTS[r] for r in old.k.ROLES)
               and receipt['historical_scores_used'] is False and receipt['reference_body_read'] is False
               and receipt['optimizer_updates']==0, 'PREPARED_SPOOL_IDENTITY')
    pins=p.manifest(cache/'inputs', binding['marker']['original_input_manifest_sha256'])
    q={}
    for role in old.k.ROLES:
        lc.pin(run/'prepared'/(role+'.jsonl.gz'),pins[role+'.jsonl.gz'])
        q[role]=np.load(run/'prepared'/(role+'_q.npy'),mmap_mode='r',allow_pickle=False)
        old._q_schema(q[role],old.EXPECTED_COUNTS[role])
    for split in ('FIT','CAL'):
        with np.load(run/'prepared'/(split+'.npz'),allow_pickle=False) as saved:
            lc.require(np.array_equal(saved['indices'],indices[split]),'PREPARED_SPLIT_CHANGED')
    with np.load(run/'prepared/normalizer.npz',allow_pickle=False) as saved:
        lc.require(old._exact_equal(saved['mean'],norm[0]) and old._exact_equal(saved['scale'],norm[1]),
                   'PREPARED_NORMALIZER_CHANGED')
    return q


def validate_endpoint_binding(folder, binding, training, receipt, lc):
    evidence=lc.read(folder.parent.parent/'endpoint_audits'/folder.name/'lineage.json')
    lc.require(receipt in training['endpoints'] and evidence['lineage']==lc.LINEAGE
               and evidence['arm']==receipt['arm'] and evidence['seed']==receipt['seed'], 'ENDPOINT_T_JOIN')
    lc.require(evidence['cache_binding_sha256']==lc.sha(folder.parent.parent/'cache_binding.json')
               and evidence['feature_manifest_sha256']==binding['marker']['feature_manifest_sha256']
               and evidence['normalizer_manifest_sha256']==binding['marker']['normalizer_manifest_sha256'],
               'ENDPOINT_CACHE_IDENTITY')
    lc.require(all(evidence[k] is False for k in ('historical_weights_or_scores_used','CAL_used',
                'DEV_used','reference_used','synthetic_only')), 'ENDPOINT_DATA_ISOLATION')
    lc.pin(folder/'head.npz',evidence['head_sha256'])
    lc.pin(folder/'SHA256SUMS',evidence['endpoint_seal_sha256'])
    return evidence


def old_references(cache,binding,lc,modules):
    c=modules['query_tail_core_v2'].c
    old=modules['constrained_onboarding_query_tail_adapter_v2']
    ref=modules['constrained_onboarding_reference_v2']
    result={}
    for role,count,expected in [('SOURCE_REFS',179,{'LEARN':104,'DEV':75}),
                                ('UNSW_REFS',92,{'EXTERNAL_ARCHIVAL_EVALUATION':92})]:
        rows=list(c.rows(cache/'inputs'/(role+'.jsonl.gz')))
        lc.require(len(rows)==count and Counter(r['partition'] for r in rows)==expected
                   and all(r['use']=='REFERENCE' and r['label']==0 for r in rows), 'REFERENCE_ROSTER')
        rows=[dict(r,parent_slot=i) for i,r in enumerate(rows)]
        path=lc.pin(cache/'features'/(role+'.npy'),binding['feature_files'][role+'.npy'])
        z=np.load(path,mmap_mode='r',allow_pickle=False)
        lc.require(z.shape==(count,794) and z.dtype==np.float32 and np.isfinite(z).all(), 'REFERENCE_FEATURES')
        q=ref.extract_old_bank_q14(cache/'spool/snapshots.sqlite',rows,binding['marker']['spool_sha256'])
        old._q_schema(q,count)
        for partition in expected:
            ix=np.asarray([i for i,r in enumerate(rows) if r['partition']==partition],dtype=np.int64)
            result[partition]=old._bundle_rows([rows[int(i)] for i in ix],z[ix,:768],q[ix])
        z._mmap.close()
    return result


def prepare(config, progress=None):
    lc,m,design=bootstrap(config)
    k,p,t=(m[name] for name in ('query_tail_core_v2','query_tail_prepare_v2','query_tail_train_v2'))
    old=m['constrained_onboarding_query_tail_adapter_v2']; c=k.c
    from indexed_features_v1 import take
    cache,run=Path(config['cache']).resolve(),Path(config['head_run']).resolve()
    complete=lc.verify_run_complete(run,config['head_complete_sha256'])
    binding=lc.read(lc.pin(run/'cache_binding.json',config['head_cache_binding_sha256']))
    actual=lc.bind_cache(cache,config['cache_marker_sha256'],design,c)
    lc.require(binding==actual,'HEAD_CACHE_BINDING_CHANGED')
    metadata,indices=p.load_metadata(cache,design)
    lc.require(all(len(metadata[r])==old.EXPECTED_COUNTS[r] for r in k.ROLES)
               and all(len(indices[r])==old.EXPECTED_COUNTS[r] for r in ('FIT','CAL')), 'PRODUCTION_COUNTS')
    values,norm=lc.load_arrays(cache,binding,design,progress)
    q=validate_prepared(cache,run,binding,complete,design,indices,norm,lc,m)
    training=lc.read(run/'LINEAGE_T_COMPLETE.json')
    lc.require(training['status']=='COMPLETE' and training['lineage']==lc.LINEAGE
               and training['total_updates']==1158720 and training['new_heads']==12
               and training['historical_R0_reused'] is False, 'TWELVE_HEAD_T_NOT_COMPLETE')
    cutoff=lc.read(run/'thresholds.json')
    lc.require(cutoff['source']=='ORIGINAL_SOURCE_CAL_NORMAL_ONLY' and cutoff['comparator']=='strict >'
               and cutoff['budget']==.01 and cutoff['normal_rows']==33147 and cutoff['target_calibration'] is False
               and cutoff['lineage']==lc.LINEAGE, 'THRESHOLD_CONTRACT')
    cal=[metadata['LEARN'][int(i)] for i in indices['CAL']]
    lc.require(cutoff['normal_uid_sha256']==c.uid_sha(r['uid'] for r in cal if r['label']==0),'CAL_NORMAL_UID')
    arm='QUERY_TAIL';cuts=np.asarray([cutoff['cuts'][arm+'_'+str(s)] for s in c.SEEDS]);ecut=cutoff['cuts'][arm+'_ensemble']
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    models=[];audits=[]
    for seed in c.SEEDS:
        folder=run/'endpoints'/(arm+'_'+str(seed))
        receipt=old._endpoint(folder,arm,seed,design,norm)
        audits.append(validate_endpoint_binding(folder,binding,training,receipt,lc))
        models.append(t.load(folder,arm,seed,design))
    pools={};proof=dict(schema='new-lineage-onboarding-head-replay-v1',pools={},endpoint_lineage=audits)
    for pool in ('CAL','CIC_DEV','UNSW_DEV','FIT'):
        role='LEARN' if pool in ('FIT','CAL') else pool
        ix=indices[pool] if role=='LEARN' else np.arange(len(metadata[role]),dtype=np.int64)
        rows=[metadata[role][int(i)] for i in ix]
        if progress is not None: progress.stage='HEAD_REPLAY_'+pool
        logits=np.column_stack([k.scores(model,values[role],q[role],ix,norm,782,progress) for model in models])
        recent_decisions=None
        if pool!='FIT':
            # RECENT is the saved same-cache baseline; old historical scores are never loaded.
            recent={'cuts':{s:cutoff['cuts']['RECENT_'+s] for s in old.SUFFIXES}}
            with np.load(run/pool/'scores.npz',allow_pickle=False) as saved:
                for suffix in old.SUFFIXES: recent[suffix]=saved['RECENT_'+suffix].copy()
            lc.require(old._exact_equal(np.stack([recent[s] for s in old.SUFFIXES[:3]]).mean(0,dtype=np.float64),
                                        recent['ensemble']),'BASELINE_ENSEMBLE')
            recent_decisions=old._verify_saved_pool(run/pool,rows,logits,arm,cuts,ecut,recent)
            proof['pools'][pool]=dict(status='BITWISE_IDENTICAL',rows=len(rows),
                uid_sha256=c.uid_sha(r['uid'] for r in rows),
                scores_sha256=lc.sha(run/pool/'scores.npz'),decisions_sha256=lc.sha(run/pool/'decisions.npz'),
                seeds=list(c.SEEDS),ensemble=True,RECENT_baseline_verified=True)
        e3=take(values[role],ix,slice(0,768)) if role=='LEARN' else values[role][:,:768]
        qq=take(q[role],ix) if role=='LEARN' else q[role]
        pools[pool]=old._bundle_rows(rows,e3,qq,logits)
        if recent_decisions is not None:pools[pool]['recent_decisions']=recent_decisions
    refs=old_references(cache,binding,lc,m)
    pools['CIC_DEV']['banks']={'OLD_BANK':refs['DEV']}
    pools['UNSW_DEV']['banks']={'OLD_BANK':refs['EXTERNAL_ARCHIVAL_EVALUATION']}
    return dict(schema=old.SCHEMA if hasattr(old,'SCHEMA') else 'constrained-onboarding-bundle-v1',
        synthetic_only=False,head_family=arm,replay_evidence=proof,normalizer=norm,
        input_version=old.INPUT_VERSION,protocol_sha256=old.PROTOCOL_SHA256,
        provenance=dict(adapter='new-lineage-onboarding-v1',lineage=lc.LINEAGE,
            verified_current_parent=True,parent_parity='PARENT_PARITY_UNAVAILABLE',historical_R0_used=False,
            head_complete_sha256=config['head_complete_sha256'],cache_marker_sha256=config['cache_marker_sha256'],
            normalizer_sha256=binding['normalizer_files']['RECENT.npz'],
            protected_paths=[str(cache),str(run),str(HERE)],
            source='VERIFIED_RECONSTRUCTED_CACHE_AND_COMPLETED_SAME_CACHE_QUERY_TAIL',
            no_training=True,no_pcap_decode=True,no_e3_forward=True),
        source_fit=pools['FIT'],source_cal=pools['CAL'],source_references=refs['LEARN'],
        cuts=cuts,ensemble_cut=ecut,targets={p:pools[p] for p in ('CIC_DEV','UNSW_DEV')})
