"""Build the standalone commissioning chain; local files only, no execution."""
import argparse
import ast
import gzip
import json
from pathlib import Path
import shutil
import sys
import tarfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'repo/ood'));sys.dont_write_bytecode=True
import continuous_common_v3 as c
import onboarding_resources_v1 as resources

NAME='onboarding_configured_v1_20261017'
REMOTE='/public/home/jiangxinwei.zr/work'
QUERY=ROOT/'runs/query_tail_configured_v2r3_20261017'
FRONT=ROOT/'runs/legacy_continuous_input_repair_delivery_v3_20260929/bundle'
PARENT=ROOT/'runs/legacy_continuous_input_repair_delivery_v3_20260929/pullback/verified_job177891/runs/real_repair'
PROTOCOL=ROOT/'runs/onboarding_materials_and_protocol_20261015/protocol.json'
SCIENCE=('constrained_onboarding_core_v2.py','constrained_onboarding_runner_v2.py',
         'constrained_onboarding_reference_v2.py','constrained_onboarding_query_tail_adapter_v2.py',
         'constrained_onboarding_evaluate_v1.py')


def text(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value.replace('\r\n','\n').encode('utf-8'))


def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)


def part(name,value,why,instances=1):
    return dict(name=name,gib_per_instance=value,instances=instances,explanation=why)


def build(seal=False):
    archive=HERE/(NAME+'.tar.gz');bundle=HERE/'bundle'
    c.require(not archive.exists(),'SEALED_DELIVERY_NO_OVERWRITE')
    if bundle.exists():
        c.require(c.read(HERE/'draft_receipt.json')['status']=='LOCAL_DRAFT_NOT_EXECUTABLE' and
                  not any((bundle/x).exists() for x in ('runs','submit_claim','job.id')), 'DRAFT_HAS_RUNTIME_STATE')
        if (bundle/'SHA256SUMS').exists():
            c.verify(bundle);(bundle/'SHA256SUMS').unlink()
    query_receipt=c.read(QUERY/'validation.json');c.pin(QUERY/query_receipt['archive'],query_receipt['archive_sha256'])
    c.verify(QUERY/'bundle');c.verify(FRONT)
    engineering=c.read(ROOT/'runs/engineering_snapshot_journal_fix_20261017/source_manifest.json')['files']
    for name in SCIENCE:
        relative='repo/ood/'+name
        expected=engineering.get(relative)
        if expected: c.pin(ROOT/relative,expected)
    # Start with the verified full E3 dynamic runtime closure and current head closure.
    for source in (FRONT,QUERY/'bundle'):
        for file in (source/'repo/ood').glob('*.py'):copy(file,bundle/'repo/ood'/file.name)
    new={p.name for p in (ROOT/'repo/ood').glob('constrained_onboarding_*.py')}
    new.update(p.name for p in (ROOT/'repo/ood').glob('test_constrained_onboarding_*_v1.py'))
    new.update(('onboarding_delivery_v1.py','onboarding_resources_v1.py','onboarding_delivery_io_v1.py',
        'onboarding_synthetic_checks_v1.py','test_onboarding_delivery_v1.py','test_onboarding_delivery_io_v1.py',
        'test_onboarding_engineering_v2.py','test_engineering_state_storage_v1.py','test_engineering_progress_v1.py',
        'reference_storage_v1.py','spill_mapping_v1.py','scratch_registry_v1.py','indexed_features_v1.py',
        'engineering_progress_v1.py','continuous_input_engineering_v1.py'))
    for name in sorted(new):copy(ROOT/'repo/ood'/name,bundle/'repo/ood'/name)
    names={p.name for p in (bundle/'repo/ood').glob('*.py')};done=set()
    while names-done:
        name=sorted(names-done)[0];path=bundle/'repo/ood'/name
        if not path.exists():copy(ROOT/'repo/ood'/name,path)
        tree=ast.parse(path.read_text(encoding='utf-8-sig'),filename=name,feature_version=(3,9))
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import):modules=[x.name.split('.')[0]+'.py' for x in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module:modules=[node.module.split('.')[0]+'.py']
            elif isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.endswith('.py'):
                modules=[node.value.replace('\\','/').split('/')[-1]]
            names.update(x for x in modules if (ROOT/'repo/ood'/x).is_file())
        done.add(name)
    shutil.copytree(FRONT/'vendor',bundle/'vendor',dirs_exist_ok=True)
    shutil.copytree(FRONT/'repo/ood/fixtures',bundle/'repo/ood/fixtures',dirs_exist_ok=True)
    copy(PROTOCOL,bundle/'protocol.json');copy(QUERY/'bundle/design_contract.json',bundle/'query_tail_design.json')
    # Tests from the frozen runtime need its own input design; it is not this chain's contract.
    copy(FRONT/'design_contract.json',bundle/'design_contract.json')
    for file in (FRONT/'frozen').glob('*'):
        if file.is_file():copy(file,bundle/'frozen'/file.name)
    evidence=bundle/'resource_evidence';evidence.mkdir(exist_ok=True)
    copy(QUERY/'metadata_measurement/comparison.json',evidence/'full_metadata_measurement.json')
    for stem in ('cic_inventory','unsw_inventory'):
        copy(ROOT/'runs/onboarding_materials_and_protocol_20261015'/(stem+'.json'),evidence/(stem+'.json'))
    copy(ROOT/'runs/engineering_memory_followup_20261017/generated_benchmark/comparison.json',evidence/'generated_storage_benchmark.json')
    historical={p.parent.name:c.read(p) for p in sorted(PARENT.glob('features_worker_*/status.json'))}
    c.write(evidence/'historical_e3_status.json',dict(scope='Saved final states, not peak or current throughput',workers=historical),replace=True)
    catalog=c.read(PARENT/'inputs/raw_catalog.json');front_runtime=c.read(FRONT/'runtime_contract.json')
    captures={}
    for pool,capture_id,role,partition,t0 in (
            ('CIC_DEV','active-00','SOURCE_REFS','DEV',1635851700.06933),
            ('UNSW_DEV','unsw-benign-20180528','UNSW_REFS','EXTERNAL_ARCHIVAL_EVALUATION',1527465601.09039)):
        source=next(x for x in catalog if x['capture_id']==capture_id)
        refs=list(c.rows(PARENT/'inputs'/(role+'.jsonl.gz')))
        registry=[dict(device=d,owner=o,partition=partition) for d,o in sorted({(r['device'],r['owner']) for r in refs if r['partition']==partition})]
        capture={k:source[k] for k in ('capture_id','path','sha256','bytes','expected_packets')}
        capture.update(t0=t0,provenance='normal',normality_evidence='Pinned publisher-normal archive and fixed protocol inventory',
            known_macs=front_runtime['source_known_macs' if pool=='CIC_DEV' else 'external_known_macs'],
            activity='ACTIVE_UNANNOTATED' if pool=='CIC_DEV' else 'UNKNOWN',activity_verified=False)
        captures[pool]=dict(capture=capture,device_registry=registry)
    c.write(evidence/'workload_inventory.json',dict(captures=captures,query_rows=1094929,fit_normal=134493,
        cal_attack=115672,source_attack_bank_pairs=359875,target_rows=328202,max_new_references=1344,
        new_reference_bound='3 policies * 7 devices * 64; candidate universe is not bounded by this',
        input_pcap_bytes=sum(s['capture']['bytes'] for s in captures.values()),checkpoint_bytes=698780900,
        target_score_decision_bytes=328202*4*556,trace_budget_gib=1.5,other_persistent_budget_gib=.5,
        persistent_result_estimate_gib=3.,temporary_sqlite_journal_estimate_gib=2.,
        checkpoint_private_copy_gib=698780900/1024**3,whole_stage_measurement=False),replace=True)
    phases={
        'RAW_REFERENCE':[
            part('python_and_metadata_ledgers',1.5,'Complete namespace/candidate identity dictionaries remain; old full-capture component scale 1,378 CIC and 11,977 UNSW is context, not new-universe bound.'),
            part('decoder_process',1.,'tshark full-file streaming process; child peak not previously measured.'),
            part('bounded_heavy_state',1.,'1024 contexts and two windows of 128 resident snapshots; generated storage evidence only, counts are not byte caps.'),
            part('sqlite_and_serialization_buffers',1.,'Two snapshot stores plus contexts, page caches, serialization and last-flow copies.'),
            part('parent_runtime_and_uncertainty',1.5,'Supervisor, imports, Linux allocator, selected snapshots/census writing; no original model in this phase.')],
        'E3_REFERENCE':[
            part('model_runtime_residency',2.,'Frozen 0.651GiB checkpoint; prior E3 worker final RSS 1.660-1.867GiB, explicitly not peak.'),
            part('load_and_batch_activations',1.5,'One model, batch <=16 with original shape groups; loading, float32 forward activations and tokenizer temporary space.'),
            part('parent_and_selected_reference_buffers',.5,'One policy at a time, <=320 references; snapshots, tokenizer examples and supervisor.')],
        'HEAD_AND_MODULE':[
            part('all_role_metadata',5.,'Full-role Windows net loaded metadata 4.996GiB from QUERY_TAIL measurement, reused row objects across FIT/CAL.'),
            part('feature_mappings',3.25,'1,094,929 x 794 float32 payload 3.239GiB; mmap pages counted as resident.'),
            part('runtime_imports_and_parent',.75,'One evaluation child plus supervisor, Torch and target runtime allowance.'),
            part('q_indices_logits_uids',.25,'Mapped q, index indirection, three head logits and ordered UID lists; no copied full E3 subsets.'),
            part('trace_and_geometry_buffers',.25,'Blocked float64 geometry, support traces and source protection arrays.'),
            part('join_validation',.5,'Transient UID sets and cross-role identity joins.'),
            part('reports_and_writing',.5,'Scores, decisions and per-device/component reporting temporary objects.'),
            part('retained_allocator_and_reports',1.,'Conservative allowance across successive policies and source calibration; single process, no E3 model retained.')]
    }
    refs=[dict(path=p.relative_to(bundle).as_posix(),sha256=c.sha(p)) for p in sorted(evidence.glob('*.json'))]
    plan=dict(schema=resources.SCHEMA,status='REVIEWABLE',processes=1,threads=4,cpus=8,memory_gib=16,
        guard_gib=14,margin_fraction=.25,disk_gib=8,minimum_free_gib=16,export_included_limit_gib=4,
        wall_seconds=22*3600,slurm_time='1-00:00:00',
        state_storage=dict(resident_contexts=1024,resident_legacy_prefixes=128,resident_candidate_snapshots=128),
        workload_identity=dict(protocol_sha256=c.sha(PROTOCOL),query_tail_design_sha256=c.sha(bundle/'query_tail_design.json'),
            head_package_seal_sha256=query_receipt['package_seal_sha256'],target_pools=['CIC_DEV','UNSW_DEV'],
            target_policies=['OLD_BANK','B0','B1','B2'],optimizer_updates=0),
        concurrency_basis='Sequential fresh processes: two normal captures, six small reference banks, one head+module evaluation. Four numeric threads fixed; 8 CPUs cover decoder/supervisor. No duplicated large metadata or concurrent E3 models.',
        disk_basis='~3GiB persistent result estimate + .651GiB private checkpoint copy + 2GiB temporary SQLite/journal allowance; 8GiB run guard. 16GiB free covers live run, up to4GiB export, reserve. Source PCAP/parent caches remain read-only and additional.',
        time_basis='24h Slurm ceiling /22h run guard, not ETA. Decode all4.013GiB; historical E3 arithmetic for <=1344 rows is15-17min but shape/startup differ. Head replay and geometry unmeasured. No automatic retry or limit increase.',
        phases={name:dict(basis='ESTIMATED',components=parts,simultaneous_peak_gib=sum(p['gib_per_instance']*p['instances'] for p in parts),
            explanation='Sequential phase, whole stage not measured; contains child plus supervisor; new child per phase avoids retained model heap.',
            includes_mappings_and_temporary_buffers=True,evidence=refs) for name,parts in phases.items()})
    resources.validate(plan);c.write(bundle/'resource_plan.json',plan,replace=True)
    norm_sha=next(line.split('  ')[0] for line in (PARENT/'normalizers/SHA256SUMS').read_text().splitlines() if line.endswith('  RECENT.npz'))
    runtime=dict(version=NAME,real_execution_authorized=False,retries=0,optimizer_updates=0,arm='QUERY_TAIL',
        protocol_sha256=c.sha(PROTOCOL),query_tail_design_sha256=c.sha(bundle/'query_tail_design.json'),
        head_package_seal_sha256=query_receipt['package_seal_sha256'],resource_plan_sha256=c.sha(bundle/'resource_plan.json'),
        normalizer_sha256=norm_sha,checkpoint_sha256=front_runtime['checkpoint_sha256'],
        paths=dict(parent=REMOTE+'/legacy_continuous_input_repair_v3_20260929/runs/real_repair',
            head_root=REMOTE+'/query_tail_configured_v2r3_20261017',head_run=REMOTE+'/query_tail_configured_v2r3_20261017/runs/query_tail',
            checkpoint=front_runtime['checkpoint']),captures=captures,tshark='tshark',tshark_version='4.6.6',
        versions=front_runtime['versions'],additional_required_packages=['pandas'],
        scientific_code_sha256={name:c.sha(bundle/'repo/ood'/name) for name in SCIENCE})
    for name in ('cpus','memory_gib','guard_gib','disk_gib','minimum_free_gib','wall_seconds','export_included_limit_gib','state_storage','slurm_time'):
        runtime[name]=plan[name]
    c.write(bundle/'runtime_contract.json',runtime,replace=True)
    for file in (HERE/'delivery_scripts').glob('*'):copy(file,bundle/'scripts'/file.name)
    for name in ('README.md','RESOURCE_BUDGET.md','OPERATE_HPC.md'):
        if (HERE/name).is_file():copy(HERE/name,bundle/name)
        else:c.require(not seal,'MISSING_DELIVERY_DOC:'+name)
    for path in bundle.rglob('*.py'):ast.parse(path.read_text(encoding='utf-8-sig'),feature_version=(3,9))
    # Canonical LF for scripts; do not normalize the pinned Python scientific source.
    for path in (bundle/'scripts').glob('*'):text(path,path.read_text(encoding='utf-8-sig'))
    c.write(HERE/'draft_receipt.json',dict(status='LOCAL_DRAFT_NOT_EXECUTABLE',python_modules=len(done),
        query_tail_archive_sha256=query_receipt['archive_sha256'],protocol_sha256=c.sha(PROTOCOL),
        scientific_code_sha256=runtime['scientific_code_sha256']),replace=True)
    if not seal:
        print('LOCAL_DRAFT_READY');return
    c.seal(bundle);c.verify(bundle)
    with tarfile.open(archive,'x:gz') as tar:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():tar.add(path,arcname=path.relative_to(bundle).as_posix(),recursive=False)
    text(Path(str(archive)+'.sha256'),c.sha(archive)+'  '+archive.name+'\n')
    installer=HERE/'onboarding_install_v1.py';copy(bundle/'repo/ood/onboarding_delivery_io_v1.py',installer)
    text(Path(str(installer)+'.sha256'),c.sha(installer)+'  '+installer.name+'\n')
    c.write(HERE/'build_receipt.json',dict(status='BUILT_LOCAL_VALIDATION_PENDING',archive=archive.name,
        archive_sha256=c.sha(archive),archive_bytes=archive.stat().st_size,package_seal_sha256=c.sha(bundle/'SHA256SUMS'),
        resource_plan_sha256=c.sha(bundle/'resource_plan.json'),python_modules=len(done),
        original_scientific_code=runtime['scientific_code_sha256'],query_tail_package_unchanged=query_receipt['archive_sha256'],
        protocol_sha256=c.sha(PROTOCOL),real_experiment=False,remote_actions=False))
    print(json.dumps(dict(archive=archive.name,sha256=c.sha(archive),python_modules=len(done))))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seal',action='store_true');build(parser.parse_args().seal)
