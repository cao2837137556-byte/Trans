"""User-authorized frozen evaluation; orchestration only, scientific v4 unchanged."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
import argparse
from pathlib import Path
import platform
import sys
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(1,str(HERE.parent/'edge_formal_execution_v4_20261104'))
from checkpoint import atomic_json, require, sha, canonical, PackedRoleSpool
from streaming import ROOT, FrozenBackend, module, run_encoding
from worker import read, runtime_identity, input_binding, selection_inputs, prepare_inputs
from runtime_control import Attempt, JobMonitor, ProcessesNotStopped, bounded_process, current_status, attempt_directory, child_scratch

from disk_scan import Guard

SCOPE='EDGE_EXTERNAL_TEST_1_FULL_EVALUATION'

def require_engineering_authorization(card_path, auth_path, root=ROOT):
    # Kept as an orchestration API name for the tested preflight/receiver.
    gate=module('_formal_authorization_gate',ROOT/'runs/edge_external_test1_engineering_v1_20261103/execution_gate.py')
    gate.require_evaluation_authorization(card_path,auth_path,root)
    card,auth=read(card_path),read(auth_path)
    require(card['budget']['wall_seconds']==auth['wall_seconds']==86400 and
        card['budget']['cpu']==auth['cpu']==1 and card['budget']['rss_bytes']==8*1024**3 and
        auth['memory_gib']==8 and auth['allowed_jobs']==1 and auth['automatic_resubmit'] is False,
        'FORMAL_RESOURCE_CONTRACT')
    require(card['formal_worker_linux_recovery']['status']=='PASS' and
        card['training_authorized'] is False and card['no_quality_based_query_or_dataset_selection'] is True,
        'FORMAL_FROZEN_SCOPE')
    require(card['independent_review']['status']=='USER_DIRECTED_EXECUTION_WITHOUT_NEW_INDEPENDENT_REVIEW' and
        auth['authorization_quote']==card['independent_review']['execution_quote'], 'HONEST_REVIEW_DECISION')
    from dependency_identity import verify
    verify(card,root)
    return card

def import_complete(card, runtime, output, guard, identity):
    """All roles must already be complete under the identical scientific binding."""
    from replay_resume import seed_role
    spec=card['accepted_complete_source'];source=Path(spec['output'])
    require(source.is_absolute() and not source.is_symlink() and source.resolve().is_relative_to(ROOT.parents[1])
        and source.resolve()!=Path(output).resolve(), 'COMPLETE_SOURCE_SCOPE')
    before=sha(source/'CURRENT_ENGINEERING_ATTEMPT.json')
    accepted=current_status(source,card_sha256=spec['card_sha256'])
    require(accepted['status']=='PASS' and accepted['cleanup_complete'] is True, 'COMPLETE_SOURCE_PASS')
    candidate_path=attempt_directory(source,accepted['attempt_id'])/'CANDIDATE.json'
    require(sha(candidate_path)==spec['candidate_sha256'], 'COMPLETE_SOURCE_CANDIDATE_PIN')
    candidate=read(candidate_path)
    adapter=module('_formal_complete_adapter', ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py')
    raw=adapter.card();binding=input_binding(card,identity,raw)
    require(canonical(candidate['input_binding'])==canonical(binding), 'COMPLETE_SCIENTIFIC_BINDING')
    _,refs,selected=selection_inputs();records={}
    for role in ('NORMAL','HTTP','UDP'):
        guard.progress('IMPORT_COMPLETE_ROLE',role=role)
        expected={r['uid']:r for r in ((refs if role=='NORMAL' else [])+selected[role])}
        old=PackedRoleSpool(source/'spools'/role,binding,role,sorted(expected))
        require(old.is_complete(),'SOURCE_ROLE_INCOMPLETE')
        coverage=read(old.root/'REPLAY_COVERAGE.json')
        require(coverage['last_frame']==raw['raw_inputs'][role]['records'] and
            coverage['raw_sha256']==raw['raw_inputs'][role]['sha256'] and
            coverage['generator_exhausted'] is True and coverage['final_raw_identity_pass'] is True,
            'SOURCE_ROLE_EOF')
        pin=sha(old.root/'COMPLETE.json')
        seed_role(source,output,role,binding,expected)
        target=PackedRoleSpool(Path(output)/'spools'/role,binding,role,sorted(expected))
        require(target.is_complete() and sha(old.root/'COMPLETE.json')==pin and
            sha(target.root/'COMPLETE.json')==pin, 'COMPLETE_IMPORT_EXACT')
        records[role]=dict(rows=len(expected),complete_sha256=pin,coverage=coverage)
        guard()
    require(sha(source/'CURRENT_ENGINEERING_ATTEMPT.json')==before,'SOURCE_POINTER_UNCHANGED')
    receipt=dict(status='PASS_COMPLETE_IMPORT',roles=records,logical_rows=sum(r['rows'] for r in records.values()),
        source=spec,source_pointer_unchanged=True,input_binding=binding)
    require(receipt['logical_rows']==64124,'IMPORT_EXACT_ROWS')
    atomic_json(Path(output)/'COMPLETE_IMPORT.json',receipt)
    return receipt

def execute(args):
    card=require_engineering_authorization(args.card,args.authorization);runtime=read(args.runtime)
    identity=runtime_identity(runtime['tshark'])
    require(platform.system()=='Linux' and identity==card['runtime_identity'],'FORMAL_LINUX_RUNTIME')
    import psutil
    require(len(psutil.Process().cpu_affinity())==1,'FORMAL_ONE_CPU')
    output=Path(args.output);scratch=child_scratch(output,args.attempt_id,'main',sha(args.card))
    guard=Guard(output,scratch,dict(card['budget'],wall_seconds=args.deadline-time.monotonic()),formal=True)
    guard.attempt_id,guard.card_sha256=args.attempt_id,sha(args.card)
    try:
        imported=import_complete(card,runtime,output,guard,identity)
        prepared=prepare_inputs(card,runtime,output,scratch,guard,identity,replay_to_eof=True)
        plan=prepared['plan'];require(len(plan)==4046 and sum(len(e['uids']) for e in plan)==64124,'FULL_ENCODE_PLAN')
        atomic_json(output/'BATCH_PLAN.json',plan)
        from encoding_resume import import_batches
        binding,resumed=import_batches(card,identity,output,plan,guard)
        atomic_json(output/'ENCODING_PROVENANCE.json',dict(execution_card_sha256=sha(args.card),encoding_card_sha256=binding['execution_card_sha256'],import_receipt_sha256=sha(output/'ENCODING_IMPORT.json')))
        timing=read(HERE/'BUDGET_EVIDENCE.json')['encoding']['shapes']
        rates={tuple(x['shape']):x['seconds_per_physical_row'] for x in timing}
        costs=[rates[tuple(e['shape'])]*e['physical_rows'] for e in plan]
        total=sum(costs);done=0.;started=time.monotonic();completed=0
        def progress(stage,**kw):
            nonlocal done,completed
            if stage in ('ENCODE_COMMITTED','ENCODE_REUSED'):
                done+=costs[completed];completed+=1
            kw.update(encoding_rows_total=64124,encoding_batches_total=4046,encoding_batches_completed=completed,
                encoding_measured_fraction=done/total,encoding_measured_remaining_seconds=max(0.,total-done),
                encoding_elapsed_seconds=time.monotonic()-started)
            guard.progress(stage,**kw)
        store,receipt=run_encoding(plan,prepared['load'],FrozenBackend,output/'encoded',binding,guard,progress)
        atomic_json(output/'ENCODING_ATTEMPT.json',receipt)
        guard.progress('ENCODING_COMPLETE',logical_rows=64124)
        census=ROOT/card['population_census']['path'];require(sha(census)==card['population_census']['sha256'],'CENSUS_PIN')
        from evaluate import evaluate
        metrics=evaluate(store,plan,output/'evaluation',binding,read(census),card['budget']['distance_pairs'],guard,guard.progress)
        from formal_acceptance import validate_outputs
        checked=validate_outputs(output,sha(args.card),encoding_card_sha=card['encoding_resume_source']['card_sha256'])
        candidate=dict(status='CANDIDATE_SUCCESS',kind='EDGE_FORMAL_FULL_EVALUATION',scope=SCOPE,
            attempt_id=args.attempt_id,card_sha256=sha(args.card),runtime_identity=identity,
            encoding_card_sha256=binding['execution_card_sha256'],reused_encoding_rows=resumed['rows'],input_binding=prepared['input_binding'],logical_spool_rows=64124,encoding_rows=64124,
            query_rows=60000,reference_rows=4124,metrics_sha256=sha(metrics),validation=checked,
            external_quality_computed=True,training=False,methods_frozen=True,elapsed_seconds=time.monotonic()-guard.started)
        atomic_json(attempt_directory(output,args.attempt_id)/'CANDIDATE.json',candidate)
    except BaseException as exc:
        atomic_json(attempt_directory(output,args.attempt_id)/'CHILD_STOP_main.json',dict(reason=type(exc).__name__+':'+str(exc)))
        raise

def supervise(attempt,command,deadline,budget):
    monitor=JobMonitor(attempt.output,[Path(v['scratch']) for v in attempt.scratch_plan['phases'].values()],budget)
    try:
        require(bounded_process(command,attempt.directory/'WORKER.log',deadline,monitor=monitor,session=True)==0,'WORKER_FAILED')
        monitor.sample(force_disk=True)
        p=attempt.directory/'CANDIDATE.json';c=read(p)
        require(c['status']=='CANDIDATE_SUCCESS' and c['attempt_id']==attempt.id and c['card_sha256']==attempt.card_sha,'CANDIDATE_BINDING')
        quality=c.get('external_quality_computed',False)
        if quality:
            from formal_acceptance import validate_outputs
            require(c['validation']==validate_outputs(attempt.output,attempt.card_sha,encoding_card_sha=c['encoding_card_sha256']),'FINAL_OUTPUTS_UNCHANGED')
        cleaned=attempt.cleanup();require(time.monotonic()<deadline+30,'CLEANUP_DEADLINE')
        return attempt.publish('PASS',candidate=p.name,candidate_sha256=sha(p),resources=monitor.receipt(),
            scratch_removed=cleaned,cleanup_complete=True,evaluation_authorized=True,external_quality_computed=quality)
    except BaseException as exc:
        try:
            require(not isinstance(exc,ProcessesNotStopped),'PRESERVE_SCRATCH_UNTIL_STOPPED')
            cleaned=dict(complete=True,removed=attempt.cleanup())
        except BaseException as err:cleaned=dict(complete=False,reason=str(err))
        attempt.publish('STOP',reason=type(exc).__name__+':'+str(exc),resources=monitor.receipt(),scratch_cleanup=cleaned,
            completed_batches_preserved=True,quality_acceptance=False)
        raise

def run(card_path,auth_path,runtime_path,output):
    started=time.monotonic();attempt=Attempt(output,sha(card_path))
    try:
        card=require_engineering_authorization(card_path,auth_path)
        from preflight_acceptance import validate_saved
        validate_saved(Path(output).parents[1],card_path)
        attempt.allocate_scratch(Path(read(runtime_path)['scratch_root']).resolve())
        deadline=started+card['budget']['wall_seconds']-30
        command=[sys.executable,'-X','utf8','-B',str(HERE/'formal_job.py'),'--child',
            '--card',str(card_path),'--authorization',str(auth_path),'--runtime',str(runtime_path),
            '--output',str(output),'--attempt-id',attempt.id,'--deadline',str(deadline)]
        return supervise(attempt,command,deadline,card['budget'])
    except BaseException as exc:
        if current_status(output,attempt_id=attempt.id)['status']=='RUNNING':
            attempt.publish('STOP',reason=type(exc).__name__+':'+str(exc),scratch_removed=attempt.cleanup())
        raise
    finally:attempt.close()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for field in ('card','authorization','runtime','output'):p.add_argument('--'+field,type=Path,required=True)
    p.add_argument('--child',action='store_true');p.add_argument('--attempt-id');p.add_argument('--deadline',type=float)
    args=p.parse_args()
    if args.child:execute(args)
    else:run(args.card,args.authorization,args.runtime,args.output)
