"""Small synthetic traffic only. Never opens a real capture or model state."""
from __future__ import annotations
import copy,gzip,json,math
from pathlib import Path
import numpy as np
import legacy_reference_executor_common_v1 as c
import legacy_reference_sample_prepare_v1 as p
def create(folder,force_gate=None,inject_failure=None):
    folder=c.confined(c.PACKAGE/'synthetic',folder);folder.mkdir(parents=True,exist_ok=False)
    import issue27ckda_d0_resource_pilot_v1 as translator
    from test_legacy_reference_sample_prepare_v1 import row
    from legacy_reference_sample_finalize_v1 import weight_rows
    r=copy.deepcopy(c.recipe());api,_,_=p.old.legacy_runtime()
    devices=[];catalog=[];raw={};manifests={x:[] for x in ('REFERENCE','LEARN','DEV','DEVICE_HOLDOUT')}
    for d,partition in enumerate(['LEARN','LEARN','DEV','DEV','DEVICE_HOLDOUT']):
        name='Synthetic device '+str(d);mac='02:00:00:00:01:%02x'%(d+1)
        devices.append(dict(device=name,mac=mac,proposed_partition=partition,reference_end=10.))
        for capture,use,label,times in [('ref','REFERENCE',0,[1.,2.]),('normal','QUERY',0,[20.,21.,22.]),('attack','QUERY',1,[30.,31.,32.])]:
            cid=str(d)+'_'+capture;records=[]
            for frame,ts in enumerate(times,1):
                one={k:'' for k in translator.TSHARK_FIELDS}
                one.update(row(frame,ts,src_mac=p.ATTACKER_MAC if label else '02:00:00:ff:ff:ff',dst_mac=mac,
                               src=p.ATTACKER_IP if label else '10.1.1.200',dst='10.1.1.'+str(d+1),sport=40000+frame,dport=80))
                records.append(one)
            source_sha=c.digest(records);raw[cid]=records
            spec=dict(capture_id=cid,sha256=source_sha,provenance='attack' if label else 'normal',owner=mac,mode='UDP' if label else 'NORMAL',
                      use=use,expected_packets=len(records),skip_reason=None,path='SYNTHETIC_NO_PCAP',device=name)
            catalog.append(spec)
            for one in records:
                frame=int(one['frame.number']);e=api.event_from_tshark(one);key=p.old.old_key(e)
                target=dict(uid=p.digest([source_sha,frame,mac]),capture_id=cid,source_sha256=source_sha,frame=frame,timestamp=e.timestamp,
                            device=name,owner=mac,partition=partition,use=use,label=label,activity=spec['mode'],
                            session_id=p.digest([mac,cid,key]),component_id=p.digest([mac,key]),protocol=17,canonical_key=key,
                            candidate_rank=0,candidate_count=1,sample_count=1,reference_end=10.,
                            normal_activity_stratum='attack' if label else 'reference_covered',reference_dependency_stratum='different_canonical_component')
                manifests['REFERENCE' if use=='REFERENCE' else partition].append(target)
    index={}
    for role,values in manifests.items():
        if role!='REFERENCE':weight_rows(values)
        path=folder/(role+'.jsonl.gz')
        with gzip.open(path,'wt',encoding='utf8') as f:
            for value in values:f.write(json.dumps(value)+'\n')
        index[role]=dict(path=str(path),sha256=c.sha(path),rows=len(values),sorted_uid_lines_sha256=c.uid_sha(x['uid'] for x in values))
    r['synthetic_only']=True;r['data']['manifests']=index;r['data']['reference_costs']=[]
    r['data']['devices']=[dict(device=d['device'],partition=d['proposed_partition'],attack_modes={'UDP':3}) for d in devices]
    r['evaluation']['interventions']=[]
    dev_devices=[d['device'] for d in devices if d['proposed_partition']=='DEV']
    for name,donor in [dev_devices,dev_devices[::-1]]:
        own=[x['uid'] for x in manifests['REFERENCE'] if x['device']==name]
        wrong=[x['uid'] for x in manifests['REFERENCE'] if x['device']==donor]
        queries=[x for x in manifests['DEV'] if x['device']==name]
        r['evaluation']['interventions'].append(dict(device=name,donor=donor,partition='DEV',status='DEFINED',
            equal_count=2,protocol_multiset={'17':2},correct_reference_uids=own,wrong_reference_uids=wrong,
            applicable_after=10.,applicable_query_count=len(queries),applicable_query_uid_hash=p.digest(sorted(x['uid'] for x in queries))))
    opt=r['optimization'];opt['rows']=len(manifests['LEARN']);opt['epochs']=2;opt['batch_size']=5
    opt['updates_per_model']=2*math.ceil(opt['rows']/5);opt['all_updates']=9*opt['updates_per_model']
    r['runtime']['wall_time_chain_limit_hours']=.5;r['runtime']['disk_new_output_limit_GiB']=.5
    rng=np.random.default_rng(8)
    state={'normalizer_mean':np.zeros(768,dtype=np.float64),'normalizer_scale':np.ones(768,dtype=np.float64),
           'p2__0.weight':rng.normal(0,.01,(128,769)).astype(np.float32),'p2__0.bias':np.zeros(128,dtype=np.float32),
           'p2__3.weight':rng.normal(0,.01,(1,128)).astype(np.float32),'p2__3.bias':np.array([-2.7],dtype=np.float32)}
    path=folder/'synthetic_state.npz'
    with path.open('xb') as f:np.savez(f,**state)
    fixture=dict(synthetic_only=True,recipe=r,state=str(path),state_sha256=c.sha(path),devices=devices,catalog=catalog,rows=raw,force_gate=force_gate,inject_failure=inject_failure)
    target=folder/'fixture.json';c.atomic_json(target,fixture);return target

