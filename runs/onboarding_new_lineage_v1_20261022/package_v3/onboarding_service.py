"""Explicit new-lineage cloud entry. Frozen science, bounded sequential workers."""
import argparse,hashlib,importlib.metadata,json,os,shutil,signal,subprocess,sys,time,traceback
from pathlib import Path
import backup_chunks as b

HERE=Path(__file__).resolve().parent
POOLS=('CIC_DEV','UNSW_DEV');POLICIES=('B0','B1','B2')
STAGES=('replay',)+tuple('raw-'+p for p in POOLS)+tuple('encode-'+p+'-'+s for p in POOLS for s in POLICIES)+('evaluate',)

def write(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.next')
    tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,path)

def load():
    config=b.read(HERE/'config.json');manifest=b.read(HERE/'code_manifest.json')
    for name,digest in manifest['files'].items():
        path=(HERE/name).resolve();b.require(path.is_relative_to(HERE) and b.sha(path)==digest,'PACKAGE_IDENTITY:'+name)
    b.require({'config.json','new_onboarding_adapter.py','onboarding_service.py','backup_chunks.py'}<=set(manifest['files']),'PACKAGE_INCOMPLETE')
    return config

def bindings(config):
    import new_onboarding_adapter as adapter
    lc,m,design=adapter.bootstrap(config)
    original=lc.read(HERE/'frozen_onboarding/runtime_contract.json')
    plan=lc.read(HERE/'frozen_onboarding/resource_plan.json')
    lc.require(config['optimizer_updates']==0 and config['retries']==0 and config['arm']=='QUERY_TAIL','FROZEN_SCOPE')
    # Only paths change. Captures and policy/resource/version semantics remain sealed.
    captures=json.loads(json.dumps(original['captures']))
    for pool in POOLS:captures[pool]['capture']['path']=config['raw'][pool]
    return adapter,lc,m,design,original,plan,captures

def preflight(config,run):
    adapter,lc,m,design,original,plan,captures=bindings(config)
    for name,version in original['versions'].items():
        lc.require(importlib.metadata.version(name).split('+')[0]==version,'VERSION:'+name)
    for name in original['additional_required_packages']:importlib.metadata.version(name)
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):
        lc.require(os.environ.get(name)=='4','THREADS:'+name)
    lc.require(shutil.disk_usage(run).free>=plan['minimum_free_gib']*1024**3,'FREE_DISK')
    protected=[config[k] for k in ('cache','head_run','query_root','lineage_root','checkpoint')]+list(config['raw'].values())+[str(HERE)]
    for p in protected:
        p=Path(p).resolve();lc.require(not run.is_relative_to(p) and not p.is_relative_to(run),'INPUT_OUTPUT_OVERLAP')
    lc.pin(config['checkpoint'],original['checkpoint_sha256'])
    version=subprocess.run([config['tshark'],'--version'],capture_output=True,text=True,timeout=30,check=True).stdout
    lc.require(original['tshark_version'] in version.splitlines()[0],'DECODER_VERSION')
    for spec in captures.values():
        raw=spec['capture'];p=lc.pin(raw['path'],raw['sha256']);lc.require(p.stat().st_size==raw['bytes'],'RAW_BYTES')
    lc.pin(Path(config['head_run'])/'QUERY_LINEAGE_COMPLETE.json',config['head_complete_sha256'])
    lc.pin(Path(config['cache'])/'CACHE_REBUILD_COMPLETE.json',config['cache_marker_sha256'])
    write(run/'preflight.json',dict(status='PASS',lineage=lc.LINEAGE,raw=captures,tshark_version=version,
        tshark_sha256=lc.sha(config['tshark']),code_manifest_sha256=lc.sha(HERE/'code_manifest.json'),
        resource_plan_sha256=lc.sha(HERE/'frozen_onboarding/resource_plan.json'),allocation='SYSTEMD_8_CPU_16_GIB',optimizer_updates=0))
    write(run/'environment.json',m['constrained_onboarding_reference_v2']._environment())
    runtime=dict(paths=dict(checkpoint=config['checkpoint']),checkpoint_sha256=original['checkpoint_sha256'])
    if config.get('resume_manifest_sha256'):
        resume=lc.read(lc.pin(HERE/'resume_inputs_v3.json',config['resume_manifest_sha256']))
        source=Path(resume['run']).resolve()
        lc.require(source!=run and not run.is_relative_to(source) and not source.is_relative_to(run),'RESUME_SCOPE')
        lc.pin(Path(resume['source_package'])/'code_manifest.json',resume['source_code_manifest_sha256'])
        final=lc.read(lc.pin(resume['source_final_status'],resume['source_final_status_sha256']))
        lc.require(final['status']=='STOPPED_NO_RETRY' and final['failure']['stage']=='evaluate','RESUME_SOURCE_NOT_TERMINAL_EVALUATION')
        for name,digest in resume['files'].items():
            src=(source/name).resolve();dest=(run/name).resolve()
            lc.require(src.is_relative_to(source) and dest.is_relative_to(run) and not dest.exists(),'RESUME_FILE_SCOPE')
            lc.pin(src,digest);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest);lc.pin(dest,digest)
        for pool in POOLS:
            lc.require(lc.read(run/'raw'/pool/'raw_receipt.json')['status']=='COMPLETE','RESUME_RAW_INCOMPLETE')
            for policy in POLICIES:
                lc.require(lc.read(run/'encoded'/pool/policy/'receipt.json')['status']=='COMPLETE','RESUME_BANK_INCOMPLETE')
        write(run/'RESUME_INPUTS_VERIFIED.json',dict(status='PASS',source=str(source),files=len(resume['files']),
            source_manifest_sha256=config['resume_manifest_sha256'],raw_decode_rerun=False,E3_rerun=False))
    else:
        m['onboarding_delivery_v1'].make_encoder_runtime(HERE/'frozen_onboarding',run,runtime)

class ReplayProgress:
    def __init__(self,path):self.path=path;self.stage='VERIFY_CACHE';self.last=0
    def tick(self,completed,total):
        now=time.monotonic()
        if now-self.last>2 or completed==total:
            write(self.path,dict(status='RUNNING',stage=self.stage,completed=int(completed),total=int(total),updated_epoch=time.time()))
            self.last=now

def stage(config,name):
    adapter,lc,m,design,original,plan,captures=bindings(config)
    run=Path(config['run']);reference=m['constrained_onboarding_reference_v2'];runner=m['constrained_onboarding_runner_v2']
    launch=b.read(run/'stage_launch.json');lc.require(launch['stage']==name,'STAGE_IDENTITY')
    protected=[config['cache'],config['head_run'],config['checkpoint'],str(HERE)]
    if name.startswith('raw-'):
        lc.require(os.geteuid()==config['raw_worker_uid'] and os.getegid()==config['raw_worker_gid']
                   and os.geteuid()!=0, 'RAW_WORKER_MUST_BE_UNPRIVILEGED')
        profile=run/'decoder_profile'
        lc.require(os.environ.get('WIRESHARK_CONFIG_DIR')==str(profile) and profile.is_dir()
                   and not list(profile.iterdir()), 'EMPTY_DECODER_PROFILE_REQUIRED')
        spec=captures[name[4:]]
        spec.update(tshark=config['tshark'],state_storage=plan['state_storage'],
            limits=dict(wall_seconds=plan['wall_seconds'],memory_gib=plan['guard_gib'],disk_gib=launch['remaining_disk_gib']),protected_paths=protected)
        reference.prepare_raw_capture(spec,run/'raw'/name[4:])
    elif name.startswith('encode-'):
        _,pool,policy=name.split('-');prepared=run/'raw'/pool/'prepared'/policy
        binding=lc.read(lc.pin(Path(config['head_run'])/'cache_binding.json',config['head_cache_binding_sha256']))
        spec=dict(prepared_receipt_sha256=lc.sha(prepared/'receipt.json'),runtime_root=str(run/'encoder_runtime'),
            runtime_manifest_sha256=lc.read(run/'encoder_runtime_identity.json')['manifest_sha256'],
            normalizer=str(Path(config['cache'])/'normalizers/RECENT.npz'),normalizer_sha256=binding['normalizer_files']['RECENT.npz'],protected_paths=protected)
        reference.encode_selected(prepared,run/'encoded'/pool/policy,spec)
    elif name in ('replay','evaluate'):
        bundle=adapter.prepare(config,ReplayProgress(run/(name+'_progress.json')))
        write(run/(name+'_replay_proof.json'),bundle['replay_evidence'])
        if name=='replay':
            runner._validate_bundle(bundle,lc.read(HERE/'frozen_onboarding/protocol.json'))
            write(run/'REPLAY_PASS.json',dict(status='PASS',original_scores_and_decisions='BITWISE_IDENTICAL',
                source_fit_rows=617908,source_references=104,proof_sha256=lc.sha(run/'replay_replay_proof.json'),optimizer_updates=0))
        else:
            import constrained_onboarding_runner_v3 as runner
            runner.attach_reference_banks(bundle,run/'banks_manifest.json')
            lc.require(all(set(bundle['targets'][p]['banks'])=={'OLD_BANK',*POLICIES} for p in POOLS),'FULL_BANK_MATRIX')
            result=runner.run_development(bundle,run/'evaluation',HERE/'frozen_onboarding/protocol.json')
            validate_result(result,lc.require)
    else:raise RuntimeError('UNKNOWN_STAGE:'+name)

def validate_result(result,require=b.require):
    require(result['status']=='COMPLETE' and result['optimizer_updates']==0 and not result['automatic_model_selection'],'RESULT_SCOPE')
    require(set(result['scientific_decisions'])=={'OLD_BANK',*POLICIES},'RESULT_POLICIES')
    require(all(x['status']!='PASS' for x in result['scientific_decisions'].values()),'MISSING_REGRESSION_CANNOT_PASS')

def worker_options(config,name):
    if not name.startswith('raw-'):return {}
    uid,gid=config['raw_worker_uid'],config['raw_worker_gid']
    b.require(type(uid) is int and type(gid) is int and uid>0 and gid>0,'NON_ROOT_RAW_ID_REQUIRED')
    env=dict(os.environ,WIRESHARK_CONFIG_DIR=str(Path(config['run'])/'decoder_profile'))
    return dict(user=uid,group=gid,extra_groups=[],umask=0o022,env=env)

def supervise(config,run,name,plan,started):
    # Parent observes RSS/time. Raw worker owns its transient SQLite scratch guard.
    sys.path.append(str(HERE/'frozen_onboarding/repo/ood'))
    from engineering_progress_v1 import disk_bytes
    from legacy_unsw_archival_runtime_v1 import tree_rss
    from resource_observation_v1 import StageRecorder
    from onboarding_delivery_v1 import terminate_group
    remaining=plan['disk_gib']-disk_bytes(run)/1024**3;b.require(remaining>0,'WORKING_DISK_LIMIT')
    write(run/'stage_launch.json',dict(stage=name,remaining_disk_gib=remaining))
    folder=run/'monitor'/name;folder.mkdir(parents=True);recorder=StageRecorder(folder)
    child=None;peak=0;begin=time.monotonic();last=0
    options=worker_options(config,name)
    if options:
        # Only our new raw-output parent is writable by the unprivileged worker.
        # Inputs and every other stage keep their original ownership/permissions.
        os.chown(run/'raw',options['user'],options['group'])
        os.chmod(run/'raw',0o755)
        profile=run/'decoder_profile';profile.mkdir(exist_ok=True)
        b.require(not list(profile.iterdir()),'EMPTY_DECODER_PROFILE_REQUIRED')
        os.chmod(profile,0o755)
        write(run/'decoder_execution.json',dict(uid=options['user'],gid=options['group'],supplementary_groups=[],
            WIRESHARK_CONFIG_DIR=str(profile),profile_empty=True,tshark=config['tshark'],
            tshark_sha256=b.sha(config['tshark']),stderr_policy='REQUIRE_EMPTY_UNCHANGED'))
    try:
        with (run/'logs'/(name+'.log')).open('x') as stream:
            child=subprocess.Popen([sys.executable,'-B',str(HERE/'onboarding_service.py'),'stage','--name',name],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,**options)
            while True:
                now=time.monotonic();rss=tree_rss();peak=max(peak,rss)
                b.require(now-started<plan['wall_seconds'],'WALL_TIME_LIMIT')
                b.require(rss<plan['guard_gib']*1024**3,'COMBINED_MEMORY_LIMIT')
                b.require(not (run/'STOP_REQUESTED').exists(),'USER_STOP_REQUESTED')
                if now-last>5:
                    active=run/'raw'/name[4:] if name.startswith('raw-') else None
                    if active is None or child.poll() is not None:used=disk_bytes(run)
                    else:
                        used=sum(disk_bytes(p) if p.is_dir() else p.stat().st_size for p in run.iterdir() if p.name!='raw')
                        used+=sum(disk_bytes(p) for p in (run/'raw').iterdir() if p!=active)
                    b.require(used<plan['disk_gib']*1024**3 and shutil.disk_usage(run).free>1024**3,'DISK_LIMIT')
                    write(folder/'status.json',dict(status='RUNNING',stage=name,child_pid=child.pid,elapsed_seconds=now-begin,
                        rss_gib=rss/1024**3,sampled_peak_tree_rss_gib=peak/1024**3,updated_epoch=time.time()))
                    last=now
                recorder.observe(name,rss)
                if child.poll() is not None:break
                time.sleep(.5)
        b.require(child.returncode==0,'STAGE_FAILED:'+name)
        b.require(disk_bytes(run)<plan['disk_gib']*1024**3,'FINAL_DISK_LIMIT')
        write(folder/'status.json',dict(status='COMPLETE',stage=name,elapsed_seconds=time.monotonic()-begin,sampled_peak_tree_rss_gib=peak/1024**3))
    except BaseException as exc:
        if child is not None:terminate_group(child)
        write(folder/'status.json',dict(status='STOPPED_NO_RETRY',stage=name,error=repr(exc),sampled_peak_tree_rss_gib=peak/1024**3));raise

def run(config):
    target=Path(config['run']);state=Path(config['state']);export=Path(config['export'])
    b.require(not target.exists() and not state.exists() and not export.exists(),'NEW_RUN_ONLY_NO_RETRY')
    target.mkdir(parents=True);state.mkdir(parents=True)
    for p in ('logs','raw','encoded','monitor'): (target/p).mkdir()
    for p in POOLS:(target/'encoded'/p).mkdir()
    write(state/'request.json',dict(config=config,config_sha256=b.sha(HERE/'config.json'),started_epoch=time.time(),unit=config['unit']))
    stages=('evaluate',) if config.get('resume_manifest_sha256') else STAGES
    started=time.monotonic();current='PREFLIGHT';failure=None
    def stopped(signum,frame):raise RuntimeError('SIGNAL_STOP:'+str(signum))
    signal.signal(signal.SIGTERM,stopped);signal.signal(signal.SIGINT,stopped)
    try:
        write(target/'status.json',dict(status='RUNNING',stage=current,completed_stages=0,stages=len(stages),updated_epoch=time.time()))
        preflight(config,target)
        _,lc,m,_,_,plan,_=bindings(config)
        for i,name in enumerate(stages):
            current=name
            if name=='evaluate' and not config.get('resume_manifest_sha256'):m['onboarding_delivery_v1'].make_banks_manifest(target)
            write(target/'status.json',dict(status='RUNNING',stage=name,completed_stages=i,stages=len(stages),updated_epoch=time.time()))
            supervise(config,target,name,plan,started)
        result=b.read(target/'evaluation/result.json');validate_result(result)
        write(target/'COMPLETE.json',dict(status='COMPLETE',scope='TWO_POOL_PAIRED_ONBOARDING_DEVELOPMENT',
            scientific_decisions=result['scientific_decisions'],required_three_device_regression='NOT_RUN',
            evaluation_result_sha256=b.sha(target/'evaluation/result.json'),optimizer_updates=0,retries=0))
        write(target/'status.json',dict(status='COMPLETE',stage='COMPLETE',completed_stages=len(stages),stages=len(stages),elapsed_seconds=time.monotonic()-started,updated_epoch=time.time()))
    except BaseException as exc:
        failure=dict(stage=current,error=repr(exc),traceback=traceback.format_exc())
        write(target/'status.json',dict(status='STOPPED_NO_RETRY',**failure,updated_epoch=time.time()))
    try:
        write(state/'export_status.json',dict(status='EXPORTING',experiment_success=failure is None))
        # Keep the encoder identity, not a redundant 667MiB frozen checkpoint.
        # Preserve failed scratch remotely for diagnosis; successful raw outputs have closed it.
        excluded=['run/encoder_runtime']
        if failure:excluded+=['run/raw']
        archive=b.create_backup([('run',target),('package',HERE)],export,scope='ONBOARDING_RESULT_AND_PROVENANCE',
            identity=dict(config_sha256=b.sha(HERE/'config.json'),head_complete_sha256=config['head_complete_sha256'],
                cache_marker_sha256=config['cache_marker_sha256'],unit=config['unit']),excluded=excluded)
        write(state/'export_status.json',dict(status='COMPLETE',manifest_sha256=archive['manifest_sha256'],bytes=archive['bytes']))
    except BaseException as exc:
        failure=failure or dict(stage='EXPORT',error=repr(exc),traceback=traceback.format_exc())
    write(state/'final_status.json',dict(status='COMPLETE' if failure is None else 'STOPPED_NO_RETRY',
        failure=failure,finished_epoch=time.time(),automatic_stop_enabled=False,optimizer_updates=0))
    if failure:raise RuntimeError(str(failure))

def snapshot(config):
    run=Path(config['run']);state=Path(config['state'])
    def read(p):
        try:return b.read(p) if p.stat().st_size<8*1024**2 else None
        except (OSError,ValueError):return None
    status=read(run/'status.json') or {};name=status.get('stage','')
    detail=read(run/'monitor'/name/'status.json')
    if name.startswith('raw-'):detail=read(run/'raw'/name[4:]/'progress/status.json') or detail
    if name in ('replay','evaluate'):detail=read(run/(name+'_progress.json')) or detail
    if name=='evaluate':detail=read(run/'evaluation/status.json') or detail
    unit=subprocess.run(['systemctl','show',config['unit'],'--property=ActiveState,SubState,Result,MainPID,MemoryCurrent,ExecMainStatus'],capture_output=True,text=True,timeout=10,check=True)
    info=dict(x.split('=',1) for x in unit.stdout.splitlines() if '=' in x)
    error_log=None
    if status.get('status')=='STOPPED_NO_RETRY' and name in STAGES:
        p=run/'logs'/(name+'.log')
        if p.exists():
            with p.open('rb') as f:f.seek(max(0,p.stat().st_size-5000));error_log=f.read().decode(errors='replace')
    return dict(observed_epoch=time.time(),status=status,detail=detail,unit=info,error_log=error_log,
        replay=read(run/'REPLAY_PASS.json'),final_status=read(state/'final_status.json'),export=read(state/'export_status.json'),
        export_index=read(Path(config['export'])/'BACKUP_INDEX.json'),automatic_stop_enabled=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('run','stage','snapshot'));parser.add_argument('--name')
    args=parser.parse_args();config=load()
    if args.mode=='run':run(config)
    elif args.mode=='stage':stage(config,args.name)
    else:print(json.dumps(snapshot(config)))
