"""Finalize newly prepared UIDs and a prospective recipe, with no model access."""
from __future__ import annotations
from collections import Counter,defaultdict
import gzip
import json
import math
from pathlib import Path
import subprocess
import time

import legacy_reference_sample_prepare_v1 as prep

ROOT=prep.ROOT
RUN=ROOT/'runs/legacy_reference_sample_preparation_v1_20260917'


def write_rows(path,rows):
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,separators=(',',':'),ensure_ascii=True)+'\n')
    return dict(path=str(path.relative_to(ROOT)),sha256=prep.old.sha(path),rows=len(rows),
        sorted_uid_lines_sha256=__import__('hashlib').sha256(''.join(x+'\n' for x in sorted(r['uid'] for r in rows)).encode()).hexdigest())


def weight_rows(rows):
    """Exact device/label/activity/capture/session/row hierarchical weighting."""
    activities=defaultdict(set);captures=defaultdict(set);sessions=defaultdict(set);per_session=Counter()
    devices=sorted({r['device'] for r in rows})
    for r in rows:
        d,y,a,c,s=(r[k] for k in ('device','label','activity','capture_id','session_id'))
        activities[d,y].add(a);captures[d,y,a].add(c);sessions[d,y,a,c].add(s);per_session[d,y,a,c,s]+=1
    if any(not activities[d,y] for d in devices for y in (0,1)):
        raise RuntimeError('Unpaired device/class in manifest')
    for r in rows:
        d,y,a,c,s=(r[k] for k in ('device','label','activity','capture_id','session_id'))
        den=len(devices)*len(activities[d,y])*len(captures[d,y,a])*len(sessions[d,y,a,c])*per_session[d,y,a,c,s]
        r['label_metric_weight_denominator']=den
        r['balanced_bce_weight_denominator']=2*den
    for y in (0,1):
        if not math.isclose(math.fsum(1/r['label_metric_weight_denominator'] for r in rows if r['label']==y),1,abs_tol=1e-12):
            raise RuntimeError('Weight mass mismatch')


def collapse_references(rows,devices):
    pools={};costs=[]
    for d in devices:
        source=[r for r in rows if r['device']==d['device'] and r['use']=='REFERENCE']
        # Repeated canonical keys in different captures are one conservative
        # dependency component; do not inflate registration budget with them.
        latest={}
        for r in source:
            k=r['component_id']
            if k not in latest or (r['timestamp'],r['uid'])>(latest[k]['timestamp'],latest[k]['uid']):latest[k]=r
        ordered=sorted(latest.values(),key=lambda r:prep.digest([prep.SELECTION_SALT,r['component_id']]))
        chosen=ordered[:prep.REFERENCE_CAP]
        if not chosen:raise RuntimeError('Empty legal reference: '+d['device'])
        pools[d['device']]=chosen
        costs.append(dict(device=d['device'],partition=d['proposed_partition'],reference_end=d['reference_end'],
            candidate_endpoints=len(source),canonical_components=len(latest),selected=len(chosen),
            protocols=sorted({r['protocol'] for r in chosen}),reference_uids=[r['uid'] for r in chosen],
            selected_activities=sorted({r['activity'] for r in chosen}),
            first=min(r['timestamp'] for r in source),independent_session_count=None))
    return pools,costs


def deduplicate(rows,pools):
    reference_events={(r['packet_sha256'],round(r['timestamp']*1e6)) for pool in pools.values() for r in pool}
    seen={};out=[];excluded=[]
    # A matching captured packet within the same microsecond is conservatively
    # a duplicate observation. Identical bytes at other times are retained.
    for r in sorted(rows,key=lambda r:(r['timestamp'],r['capture_id'],r['frame'])):
        if r['use']=='REFERENCE':continue
        event=(r['packet_sha256'],round(r['timestamp']*1e6))
        if event in reference_events:
            excluded.append(dict(uid=r['uid'],reason='SAME_PACKET_TIME_AS_REFERENCE'));continue
        if event in seen:
            prior=seen[event]
            if prior['partition']!=r['partition'] or prior['label']!=r['label'] or prior['owner']!=r['owner']:
                raise RuntimeError('Cross-role/label/owner duplicate observation; review required')
            excluded.append(dict(uid=r['uid'],reason='DUPLICATE_PACKET_TIME_QUERY',retained_uid=prior['uid']));continue
        seen[event]=r;out.append(r)
    return out,excluded


def reference_interventions(pools,devices,queries):
    pairing=[]
    for d in devices:
        if d['proposed_partition']=='LEARN':continue
        own=pools[d['device']];own_protocol={r['protocol'] for r in own}
        candidates=[x for x in devices if x['device']!=d['device'] and x['proposed_partition']==d['proposed_partition']
            and own_protocol=={r['protocol'] for r in pools[x['device']]}]
        if not candidates:
            pairing.append(dict(device=d['device'],status='UNAVAILABLE_NO_EQUAL_PROTOCOL_DONOR'));continue
        donor=min(candidates,key=lambda x:prep.digest([prep.SELECTION_SALT,d['device'],x['device']]))
        other=pools[donor['device']]
        correct_control=[];wrong_control=[];protocol_counts={}
        for protocol in sorted(own_protocol):
            own_part=[r for r in own if r['protocol']==protocol]
            other_part=[r for r in other if r['protocol']==protocol]
            count=min(len(own_part),len(other_part))
            correct_control.extend(own_part[:count]);wrong_control.extend(other_part[:count])
            protocol_counts[protocol]=count
        k=len(correct_control)
        cutoff=max(d['reference_end'],donor['reference_end'])
        applicable=[q for q in queries if q['device']==d['device'] and q['timestamp']>cutoff]
        pairing.append(dict(device=d['device'],donor=donor['device'],partition=d['proposed_partition'],status='DEFINED',
            equal_count=k,protocol_multiset=protocol_counts,correct_reference_uids=[r['uid'] for r in correct_control],wrong_reference_uids=[r['uid'] for r in wrong_control],
            applicable_after=cutoff,applicable_query_count=len(applicable),
            applicable_query_uid_hash=prep.digest(sorted(q['uid'] for q in applicable)),
            note='Offline diagnostic only; wrong-owner routing is prohibited in deployment. Equal reference count AND protocol multiset; compare these explicit correct/wrong UID lists, never full correct versus fewer wrong references.'))
    return pairing


def make_recipe(manifests,summary,reference_costs,interventions):
    old=prep.load(ROOT/'runs/mainline_docs/legacy_cic2022_p2_enhancement_small_recipe_v1_20260915.json')
    n=manifests['LEARN']['rows'];batches=math.ceil(n/256)
    model={k:v for k,v in old['model'].items() if k in ('source_root','checkpoint_dir','checkpoint_sha256','config_sha256','source_commit','release','vendor_source_manifest','e3_runtime','pooling','numeric_path','state_array_allowlist')}
    return dict(schema='legacy-reference-joint-development-v1',status='FROZEN_PROSPECTIVE_NOT_EXECUTED',
        authority=dict(preparation_authorized=True,features=False,training=False,scoring=False,hpc=False,new_download=False),
        objective='Earlier certified device-normal reference reduces later normal OOD false alarms while retaining SAME-device attack recall.',
        data=dict(manifests=manifests,devices=summary['devices'],labels='normal-source provenance; LOIC verified source/victim/local service and current data/SYN/request; Hydra current authorized DESCRIBE; all other attack-capture traffic unassigned',
            reference_costs=reference_costs,per_canonical_capture_max=prep.CAP,reference_budget=prep.REFERENCE_CAP,
            sample_semantics='Systematic equal-rank sample of every eligible capture-local canonical session, before scores; no claim of full-packet rate or independent samples.',
            roles='6 LEARN only optimizer rows, 2 DEV only fixed endpoint diagnostics/gate, 3 DEVICE_HOLDOUT only one conditional confirmation; registration references never optimizer targets.',
            calibration_rows=0,calibration='No new threshold calibration. DEV is a decision/gate set, not fitted threshold data.',
            reference_policy='Earliest three normal captures, latest valid endpoint per owner/canonical dependency component, hash-order up to64. Observation ended before query; live transport termination is NOT asserted.',
            ongoing_connection_policy='Same canonical reference/query component retained as causal continued-connection stratum; report separately from new components. No independence claim.',
            context='Use ScopedPrefixes shared guard before every reference/query append; source-local owner/capture/key; permanent poison on regression; no future/backfilled rows; full-row deep copy at target.',
            partial_failure='No silent feature-row deletion. Any in-scope forward, identity, numeric or source mismatch stops the chain. Metadata-stage exclusions remain explicit.'),
        legacy=dict(encoder_normalizer_R_immutable=True,model=model,
            probe_state_path='runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz',
            probe_state_sha256=old['legacy_asset_pins']['files']['runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz'],
            threshold_probability=old['evaluation']['probability_threshold'],decision='float32 sigmoid then float64 comparison >= unchanged probability threshold',
            no_reference='Exact original R path. Original ID and old unrelated OOD/attacks do not receive this device-specific adaptation.',
            ID_anchor=dict(rows=2378,sessions=248,previously_disclosed_false_positives=0,
                source='runs/mainline_docs/legacy_cic2022_p2_enhancement_real_result_v1_20260916.md',
                use='Historical unchanged fallback row, explicitly reused; no new independent ID experiment or reopened arrays. Verify routing with synthetic no-reference equality.')),
        arms=dict(R='original logit b_R',Q=dict(input='[z768,h_R128,b_R1]',hidden=16,activation='ReLU',parameters=14385),
            M=dict(input='[z768,mean(reference)768,std_population(reference)768,h_R128,b_R1]',hidden=16,activation='ReLU',parameters=38961),
            C=dict(pair='ReLU(Linear1536to16([z-r,abs(z-r)]))',pool='masked mean and max across actual refs; no padded entries in either reduction',
                residual='Linear16to1(ReLU(Linear161to16([h_R128,b_R1,pooled32])))',parameters=27201),
            shared='b_R plus residual; last linear weight/bias zero; hidden PyTorch Linear default initialization; no dropout in new heads; R eval, all R/E3 tensors frozen; z original float64 standardization then float32; metadata excluded'),
        optimization=dict(seeds=[27,127,227],arms=['Q','M','C'],epochs=40,batch_size=256,optimizer='AdamW',lr=0.0003,
            weight_decay=0.0001,betas=[0.9,0.999],eps=1e-8,amsgrad=False,gradient_clipping=None,scheduler=None,
            loss='BCEWithLogits; device and class equal, then activity/mode, capture, canonical session and selected row equal; exact per-row rational denominators in manifests',
            minibatch_loss='N/batch_actual_size * sum(weight_i * BCE_i); no within-batch weight renormalization',
            ordering='Independent local CPU randperm generator seeded with run seed; same permutations across Q/M/C; each epoch each UID once, no oversampling',
            initialization='torch.manual_seed(seed) before constructing each new head; deterministic CPU ops; R state never trained',
            rows=n,updates_per_model=40*batches,total_models=9,all_updates=9*40*batches,
            selection='Fixed final epoch only; all three seeds reported; main score average of final-seed logits, not best seed'),
        evaluation=dict(main='Matched UID/label/reference cost/operating point R/Q/M/C; report integer errors and sampled denominators plus exact hierarchical rates',
            mandatory=['Original ID FPR clearly marked reused unchanged fallback','LEARN normal/attack fit diagnostics clearly in-sample','DEV normal OOD FPR and per-device/mode attack TPR','Conditional DEVICE_HOLDOUT normal FPR and attack TPR',
                'Reference-covered vs novel annotated activity; Active is unknown activity, never asserted novel','Same-reference-component vs new-component queries',
                'R-correct new misses and R-missed new detections by device/attack/capture','Every missing capability cell, excluded label mode and unsupported protocol','Philips local inbound TCP80 normal control only; no outbound remote80 substitution'],
            uncertainty='Device/capture/attack-run clusters; only2DEV and3holdout devices. Descriptive paired group differences; no packet-binomial CI or independent1% risk certification.',
            low_fpr='Descriptive only; no fitted threshold, selected operating point or holdout-driven tuning',
            interventions=interventions,budget16='Same query, hash-first min(16,actual) true references; no retraining; report actual budget; no best intervention promotion',
            heldout_gate='After all9 endpoints sealed: open once if M or C reduces macro DEV normal FPR, neither DEV device normal FPR increases, and attack hierarchical TPR is >=R-0.01 in EACH DEV device and available attack mode. Missing essential cell or any engineering failure closes gate. Q alone passing does not establish reference utility.',
            mechanism_claim='C needs joint benefit over R AND lower DEV normal macro FPR than M with no >1pp per-device/mode attack loss versus M; equal-count correct/wrong-reference intervention must provide directional evidence on >=1DEV device. Otherwise no C-specific innovation claim; M may be preferable.',
            gate_status='Development decision only. Point estimates do not certify noninferiority. If opened, report ALL R/Q/M/C and ALL seeds/interventions on frozen holdout once; no subsequent tuning from holdout.'),
        runtime=dict(local_only=True,training_and_scoring_not_authorized=True,
            encoder_python='D:/study/paper/anomaly_detection/paper04/supercompute_transfer/ckda_d1_local_runtime_20260814/.venv/Scripts/python.exe',
            training_python='C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe',
            e3_batch=16,torch_cpu_threads=4,model_workers=1,decoder_workers_max=2,ram_process_tree_limit_GiB=12,
            disk_new_output_limit_GiB=16,wall_time_chain_limit_hours=72,retries=0,
            exact_new_feature_rows=sum(v['rows'] for v in manifests.values()),
            float32_embedding_payload_bytes=4*768*sum(v['rows'] for v in manifests.values()),
            feature_reuse='One identity-verified raw E3 feature cache shared across arms/seeds. Prepare LEARN/DEV first; heldout queries only after gate, within future explicit authorization.',
            throughput='No separate resource trial. Persist progress/observed rate during authorized real preparation; no promised finish time from unmeasured throughput.',
            stop='Identity/label/causality/shape/nonfinite/worker error, resource bound or stopped process: stop, retain receipts, no automatic retry, source changes or silent sample pruning.'),
        implementation_acceptance_required=['Exact shared guard on ALL feature appends and deep-copy at targets','Real tokenizer/collator with synthetic stand-in model, no checkpoint access in tests',
            'R equality at zero residual; no-reference exact fallback','Padding masked in C and M, population std and variable reference budgets','Equal weighted UID exposure across arms/seeds',
            'HOLDOUT inaccessible to optimizer/normalization/calibration and scoring before gate','End-to-end synthetic supervisor failure/no-retry/status/seal coverage'],
        claim_exclusions=['arbitrary unseen-attack generalization','normal/attack capture-view equivalence','all service shortcuts removed','universal protocol support','independent1% false-positive guarantee','simultaneous live-network interference proved by separately captured files'])


def main():
    status=prep.load(RUN/'status.json')
    if status['status']!='MANIFEST_SCAN_COMPLETE_REQUIRES_FINALIZATION':raise RuntimeError('Scan not complete')
    out=RUN/'finalized';out.mkdir(exist_ok=False)
    status.update(status='FINALIZING',stage='UID_REFERENCE_WEIGHT_SEALS')
    prep.progress(RUN,status)
    try:
        devices=prep.load(RUN/'devices.json');catalog=prep.load(RUN/'capture_catalog.json')
        rows=[]
        for s in catalog:
            p=RUN/'captures'/(s['capture_id']+'_targets.jsonl.gz')
            if p.exists():
                with gzip.open(p,'rt',encoding='utf8') as f:rows.extend(json.loads(line) for line in f)
        if len({r['uid'] for r in rows})!=len(rows):raise RuntimeError('UID collision before duplicate event handling')
        pools,costs=collapse_references(rows,devices)
        for cost in costs:
            observed=[s for s in catalog if s['device']==cost['device'] and s['use']=='REFERENCE']
            cost.update(observed_capture_ids=[s['capture_id'] for s in observed],observed_capture_bytes=sum(s['bytes'] for s in observed),
                observed_seconds_sum=sum(s['last']-s['first'] for s in observed),observation_interval_start=min(s['first'] for s in observed),
                observed_activities=sorted({s['mode'] for s in observed}))
        queries,excluded=deduplicate(rows,pools)
        refs=[r for pool in pools.values() for r in pool]
        reference_components={d:{r['component_id'] for r in pool} for d,pool in pools.items()}
        reference_activities=defaultdict(set)
        for r in refs:
            reference_activities[r['device']].add(r['activity'])
        for r in queries:
            r['reference_dependency_stratum']='same_canonical_component' if r['component_id'] in reference_components[r['device']] else 'different_canonical_component'
            r['normal_activity_stratum']='attack' if r['label'] else 'unannotated_active' if r['activity']=='ACTIVE_UNANNOTATED' else 'reference_covered' if r['activity'] in reference_activities[r['device']] else 'reference_not_covered'
        manifests={'REFERENCE':write_rows(out/'references.jsonl.gz',refs)}
        summary=dict(devices=[],total_raw_records=sum(s['expected_packets'] for s in catalog),catalog_captures=len(catalog),
            selected_before_reference_collapse_and_dedup=len(rows),query_rows=len(queries),reference_rows=len(refs),
            removed_duplicate_observations=len(excluded),feature_rows=len(queries)+len(refs),scoring=False,training=False)
        for role in ('LEARN','DEV','DEVICE_HOLDOUT'):
            subset=[r for r in queries if r['partition']==role];weight_rows(subset)
            manifests[role]=write_rows(out/(role.lower()+'.jsonl.gz'),subset)
        for d in devices:
            selected=[r for r in queries if r['device']==d['device']]
            summary['devices'].append(dict(device=d['device'],partition=d['proposed_partition'],normal=sum(r['label']==0 for r in selected),attack=sum(r['label']==1 for r in selected),
                references=len(pools[d['device']]),captures=len({r['capture_id'] for r in selected}),
                canonical_capture_sessions=len({r['session_id'] for r in selected}),canonical_dependency_components=len({r['component_id'] for r in selected}),
                normal_active_dates=len({r['capture_id'] for r in selected if r['activity']=='ACTIVE_UNANNOTATED'}),
                reference_shared_component_queries=sum(r['reference_dependency_stratum']=='same_canonical_component' for r in selected),
                attack_modes=dict(Counter(r['activity'] for r in selected if r['label'])),
                raw_counts_are_not_independent_units=True))
        intervention=reference_interventions(pools,devices,queries)
        prep.dump(out/'denominators.json',summary);prep.dump(out/'manifest_index.json',manifests)
        prep.dump(out/'reference_costs.json',costs);prep.dump(out/'reference_interventions.json',intervention)
        prep.dump(out/'excluded_duplicate_observations.json',excluded)
        prep.dump(out/'excluded_capture_modes.json',[dict(capture_id=s['capture_id'],device=s['device'],partition=s['partition'],
            member_path=s['member_path'],reason=s['skip_reason'],raw_records=s['expected_packets']) for s in catalog if s['skip_reason']])
        # Verify supporting metadata against the old recorded acquisition pins,
        # in addition to the core source hashes checked before scanning.
        source_receipts=prep.load(prep.AUDIT/'source_receipts.json')
        extra_sources=[]
        needed={'runs/legacy_cic2022_support_inventory_v1_20260915/support_inventory.json',
                'runs/legacy_cic2022_interactions_acquisition_v1_20260915/official_capture_method_evidence.json',
                'runs/legacy_cic2022_attack_acquisition_v1_20260915/inspection/readme_text/00000066_Readme.txt.txt'}
        for item in source_receipts['files']:
            if item['path'] in needed:
                if prep.old.sha(ROOT/item['path'])!=item['sha256']:raise RuntimeError('Supporting source drift')
                extra_sources.append(item)
        if len(extra_sources)!=len(needed):raise RuntimeError('Missing supporting source receipt')
        design_sources=prep.load(ROOT/'runs/legacy_reference_conditioned_joint_design_v1_20260916/sources.json')
        for item in design_sources['sources']:
            if item['path']=='runs/legacy_cic2022_interactions_acquisition_v1_20260915/metadata_assessment.json':
                if prep.old.sha(ROOT/item['path'])!=item['sha256']:raise RuntimeError('Device correspondence drift')
                extra_sources.append(item)
        acceptance=prep.load(RUN/'synthetic_acceptance.json')
        if acceptance['status']!='PASS' or acceptance['tests']!=18:raise RuntimeError('Missing synthetic acceptance')
        for rel in ['repo/ood/legacy_reference_feature_adapter_v1.py','repo/ood/legacy_reference_sample_finalize_v1.py',
                    'repo/ood/test_legacy_reference_sample_prepare_v1.py','repo/ood/test_legacy_reference_sample_finalize_v1.py',
                    'repo/ood/test_legacy_reference_feature_adapter_v1.py','scripts/show_legacy_reference_sample_preparation_v1.ps1',
                    'scripts/finish_legacy_reference_sample_preparation_v1.ps1']:
            extra_sources.append(dict(path=rel,sha256=prep.old.sha(ROOT/rel)))
        prep.dump(out/'implementation_and_semantic_pins.json',extra_sources)
        recipe=make_recipe(manifests,summary,costs,intervention);prep.dump(out/'recipe.json',recipe)
        current=prep.pin_sources();original=prep.load(RUN/'input_pins.json')
        if current!=original:raise RuntimeError('Inputs or implementation changed during preparation')
        branch=subprocess.run(['git','branch','--show-current'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        if branch!='codex/exp-mainline' or head!='4b28747b09480471e2bac1beb3a9badf27280efb':raise RuntimeError('Git identity drift')
        verification=dict(status='PASS_MANIFEST_AND_RECIPE_PREPARATION_ONLY',head=head,branch=branch,source_pins_preserved=True,unrelated_files_preserved=8,
            uid_unique=True,cross_partition_duplicate_observations=0,reference_query_packet_time_overlap_after_exclusion=0,
            all_query_times_after_reference=True,balanced_weight_mass_exact=True,manifests=manifests,
            scientific_result=False,features=False,training=False,holdout_scores_opened=False,
            limitations=['Forward eligibility not yet checked against real encoder','Expected safe feature path needs final synthetic executor acceptance','Small device/run count and service/view confounding remain'])
        prep.dump(out/'verification.json',verification)
        files=sorted(p for p in out.iterdir() if p.is_file())
        (out/'SHA256SUMS').write_text(''.join(prep.old.sha(p)+'  '+p.name+'\n' for p in files),encoding='utf8')
        status.update(status='COMPLETE_SEALED',finished_epoch=time.time(),query_rows=len(queries),reference_rows=len(refs),recipe=str((out/'recipe.json').relative_to(ROOT)))
    except BaseException as exc:
        status.update(status='STOPPED_NO_RETRY',error=type(exc).__name__+': '+str(exc));raise
    finally:prep.progress(RUN,status)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
