"""Bind incremental validation to the final installed revision, never rerun work."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]


def sha(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''): result.update(data)
    return result.hexdigest()


def read(path): return json.loads(path.read_text('utf-8-sig'))


def require(value,message):
    if not value: raise RuntimeError(message)


def write(name,value):
    path=HERE/name; require(not path.exists(),'RECEIPT_EXISTS:'+name)
    path.write_bytes((json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))


def sealed_files(root):
    values={}
    for line in (root/'SHA256SUMS').read_text('utf-8').splitlines():
        digest,path=line.split('  ',1); require(sha(root/path)==digest,'SEALED_CONTENT_CHANGED:'+path); values[path]=digest
    values['SHA256SUMS']=sha(root/'SHA256SUMS')
    return values


def main():
    require(not (HERE/'validation.json').exists() and not (HERE/'source_manifest.json').exists(),'FINAL_RECEIPTS_EXIST')
    build=read(HERE/'build_receipt.json'); old=ROOT/'runs/modern_head_comparison_v1_20261018'
    previous=read(old/'validation.json'); bundle=HERE/'bundle'
    require(sha(HERE/build['archive'])==build['archive_sha256'],'ARCHIVE_CHANGED')
    require(sha(old/previous['archive'])==build['previous_archive_sha256']==previous['archive_sha256'],'ORIGINAL_ARCHIVE_CHANGED')
    files=sealed_files(bundle); old_files=sealed_files(old/'bundle')
    require(files['SHA256SUMS']==build['package_seal_sha256'],'SEAL_CHANGED')
    installations={}
    for name in ('clean_install','linux_clean_install'):
        require(sealed_files(HERE/name)==files,'INSTALLATION_CONTENT_CHANGED:'+name)
        receipt=read(HERE/(name+'.install_receipt.json'))
        require(receipt['archive_sha256']==build['archive_sha256'] and receipt['internal_seal_sha256']==build['package_seal_sha256'],'INSTALLATION_RECEIPT_MISMATCH')
        installations[name]=receipt
    for name in ('protocol.json','query_tail_design.json','design_contract.json'):
        require(files[name]==old_files[name],'ORIGINAL_SCIENTIFIC_CONTRACT_CHANGED')
    config=read(bundle/'experiment_contract.json'); old_config=read(old/'bundle/experiment_contract.json')
    require(config['training']==old_config['training'] and config['seeds']==old_config['seeds'],'TRAINING_RECIPE_CHANGED')
    gates=copy.deepcopy(config['gates']); gates['additional_regression']['applies_to']=old_config['gates']['additional_regression']['applies_to']
    require(gates==old_config['gates'],'ACCEPTANCE_RULE_CHANGED')
    plan=read(bundle/'resource_plan.json'); old_plan=read(old/'bundle/resource_plan.json')
    normalized=copy.deepcopy(plan); normalized['workload_identity']['experiment_contract_sha256']=old_plan['workload_identity']['experiment_contract_sha256']
    require(normalized==old_plan,'RESOURCE_BUDGET_UNEXPECTED_CHANGE')
    source={}
    for name,digest in files.items():
        if name.startswith('repo/ood/') and ('modern_head' in name or name.endswith('constrained_onboarding_query_tail_adapter_v2.py')):
            require(sha(ROOT/name)==digest,'WORKING_SOURCE_PACKAGE_DRIFT:'+name); source[name]=digest
    synthetic=read(HERE/'final_synthetic/result.json')
    require(synthetic['status']=='PASS' and synthetic['total_tests']==57 and synthetic['package_seal_sha256']==files['SHA256SUMS'],'SYNTHETIC_FAILED')
    for item in synthetic['tests'].values():
        require(item['success'] and not any(item[key] for key in ('failures','errors','skipped')),'SYNTHETIC_NOT_PASS')
        require(sha(HERE/'final_synthetic'/item['log'])==item['sha256'],'SYNTHETIC_LOG_CHANGED')
    linux=read(HERE/'linux_validation/result.json'); windows=read(HERE/'windows_export_validation/result.json')
    for result in (linux,windows):
        require(result['status']=='PASS' and result['archive_sha256']==build['archive_sha256'] and result['package_seal_sha256']==files['SHA256SUMS'],'DELIVERY_CHECK_MISMATCH')
    require(linux['checks']['scheduler']['tests_run']==37 and linux['checks']['export_phases']['tests_run']==3,'DELIVERY_TEST_COUNT')
    for result in linux['checks'].values():
        require(result['exit_code']==0 and not result.get('skipped') and sha(HERE/result['log'])==result['log_sha256'],'LINUX_LOG_CHANGED')
    require(windows['tests']==3 and sha(HERE/windows['log'])==windows['log_sha256'],'WINDOWS_EXPORT_LOG_CHANGED')
    powershell=read(HERE/'powershell_parser.json')
    require(powershell['status']=='PASS','POWERSHELL_SYNTAX')
    inherited={}
    for folder in ('query_tail_configured_v2r3_20261017','onboarding_configured_v1r1_20261017'):
        path=ROOT/'runs'/folder; receipt=read(path/'validation.json')
        require(sha(path/receipt['archive'])==receipt['archive_sha256'],'UPSTREAM_PACKAGE_CHANGED')
        inherited[folder]=dict(archive_sha256=receipt['archive_sha256'],validation_sha256=sha(path/'validation.json'),rerun=False)
    support={}
    for path in sorted(HERE.rglob('*')):
        relative=path.relative_to(HERE)
        if not path.is_file() or relative.parts[0] in ('bundle','clean_install','linux_clean_install','__pycache__'): continue
        if path.suffix in ('.json','.log','.py','.ps1','.md','.sha256') or relative.parts[0]=='delivery_scripts':
            support[relative.as_posix()]=sha(path)
    changed=sorted(name for name in old_files if name in files and files[name]!=old_files[name])
    added=sorted(set(files)-set(old_files))
    write('source_manifest.json',dict(schema='modern-head-v1r1-source-manifest',archive_sha256=build['archive_sha256'],
        package_files=files,changed_payload_files=changed,added_payload_files=added,
        working_source_files=source,supporting_files=support))
    findings={
        'P1':dict(status='FIXED',tests='test_modern_head_revision_train_v1.NativeStopTests',
            clarification='Observed LightGBM4.6.0 constant features: requested500/callback500/effective1. Original callback assertion does not fail in this fixture; revision permits valid native truncation and separates accounting.'),
        'P2':dict(status='FIXED',tests='test_modern_head_revision_runner_v1 plus phased Linux scheduler tests',
            behavior='heads-only P/T/K independent of onboarding; modules-only uses sealed heads and requires banks.'),
        'P3':dict(status='FIXED',tests='revision_train + revision_replay + revision_runner reuse cases',
            behavior='Actual per-pool score/decision/UID digests; shared preconditions; typed ineligibility retrains, corruption remains fatal.'),
        'P4':dict(status='FIXED',tests='revision_replay CAL scope tests plus selected original adapter regression'),
        'P5':dict(status='FIXED',tests='revision_runner.ScopeTextTests and selected original gate/evaluation tests',
            numeric_gates_unchanged=True),
        'P6':dict(status='FIXED',tests='RevisionRunnerTests.test_module_optimizer_update_guard'),
        'P7':dict(status='FIXED',tests='Linux missing extra_deps/receipt and module-readiness tests',
            automatic_installation=False),
    }
    record=dict(status='LOCAL_REVISION_PASS_TARGET_VERIFICATION_PENDING',date='2026-10-18',
        archive=build['archive'],archive_sha256=build['archive_sha256'],archive_bytes=build['archive_bytes'],
        package_seal_sha256=files['SHA256SUMS'],experiment_contract_sha256=build['experiment_contract_sha256'],
        resource_plan_sha256=build['resource_plan_sha256'],source_manifest_sha256=sha(HERE/'source_manifest.json'),
        previous_archive_sha256=previous['archive_sha256'],review_findings=findings,
        changed_path_python_tests=57,linux_scheduler_tests=37,export_tests_per_platform=3,
        distinct_reported_cases=97,total_test_executions_final_installs=100,
        synthetic_checks=synthetic,linux_delivery=linux,windows_export=windows,powershell_syntax=powershell,
        installation_checks=installations,
        inherited_v1_full_suite=dict(path='../modern_head_comparison_v1_20261018/validation.json',
            sha256=sha(old/'validation.json'),tests=65,rerun=False,
            note='Changed Python tests and selected original regressions rerun as listed; original full suite not repeated.',
            original_python_tests_rerun=20,original_python_tests_not_rerun=21,
            untouched_python_tests=dict(rerun=False,models=15,evaluate=6),
            original_export_7_assertion_fixture=dict(rerun=False,replaced_for_revision_by='3 phase-aware exporter tests on Windows and Linux')),
        inherited_upstream=inherited,training_recipe_unchanged=True,numeric_gates_unchanged=True,
        resource_allocation_reused=dict(cpus=8,memory_gib=16,threads=4,heavy_stage_processes=1,rss_guard_gib=14,
            whole_stage_peak='ESTIMATED_NOT_MEASURED',slurm_hours_per_job=72,wall_guard_hours_per_job=70),
        real_experiment='NOT_STARTED',remote_actions=False,
        limitations=['Target Python3.9/NumPy2.0.1/Torch2.5.1 and Linux glibc>=2.28 remain unverified.',
            'Local numeric tests used Python3.9/NumPy2.0.2/Torch2.8.0+cpu; WSL3.12 only exercised standard-library/mock delivery.',
            'No real training, PCAP decode, E3 or new performance result.',
            'Modules require completed onboarding v1r1 banks; heads require original complete QUERY_TAIL and parent assets.',
            'Three-device regression remains absent, so complete-system PASS remains disallowed.',
            'Modules submit requires heads final job exit zero, including successful export; failure does not auto-retry.',
            'PowerShell transfer was parsed, not executed; no real network transfer tested.'])
    write('validation.json',record)
    print(json.dumps(dict(status=record['status'],archive_sha256=build['archive_sha256'],python_tests=57,
        scheduler_tests=37,export_tests_per_platform=3,changed_payload_files=len(changed),added_payload_files=added)))


if __name__=='__main__': main()
