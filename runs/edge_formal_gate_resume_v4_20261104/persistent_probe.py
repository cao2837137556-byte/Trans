"""Restore the actual stopped UDP checkpoint in an isolated Linux child."""
import sys
from pathlib import Path
sys.path.insert(1, str(Path(__file__).resolve().parent.parent/'edge_formal_execution_v4_20261104'))
import argparse
import time
import worker
from checkpoint import PackedRoleSpool, atomic_json, require, sha
from streaming import ROOT, module
from worker import Guard, read, input_binding, selection_inputs, merge_selected, runtime_identity
from replay_resume import seed_role, snapshots, Checkpoints
from progress_io import install
from runtime_control import bounded_process

def child(spec_path):
    spec=read(spec_path);card=read(spec['card']);runtime=read(spec['runtime'])
    from engineering_gate import require_engineering_authorization
    require_engineering_authorization(spec['card'],spec['auth'])
    output=Path(spec['output']);scratch=Path(spec['scratch']);scratch.mkdir()
    guard=Guard(output,scratch,dict(card['budget'],wall_seconds=spec['deadline']-time.monotonic()),formal=False)
    adapter=module('_persistent_probe_adapter',ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py')
    source=adapter.card()
    for role,raw in source['raw_inputs'].items():
        path=Path(runtime['raw_paths'][role]);require(path.stat().st_size==raw['bytes'] and sha(path)==raw['sha256'],'RESTORE_PROBE_RAW_SHA');raw['path']=str(path)
    identity=runtime_identity(runtime['tshark']);require(identity==card['runtime_identity'],'RESTORE_RUNTIME')
    binding=input_binding(card,identity,source);_,refs,selected=selection_inputs();expected={r['uid']:r for r in selected['UDP']}
    prior=Path(card['replay_checkpoint_source'])
    from runtime_control import current_status
    require(current_status(prior)['status']=='STOP','RESTORE_SOURCE_STOP')
    require(read(prior/'replay_checkpoints/UDP/CURRENT.json')==card['resume_plan']['checkpoint_pointer'],'RESTORE_EXACT_POINTER')
    seed_role(prior,output,'UDP',binding,expected)
    spool=PackedRoleSpool(output/'spools/UDP',binding,'UDP',sorted(expected));manager=Checkpoints(output/'replay_checkpoints/UDP',spool,expected)
    saved=manager.load();require(saved[1]['frame']==2877608,'RESTORE_EXPECTED_FRAME')
    replay=module('_persistent_probe_replay',ROOT/'runs/edge_preflight_io_repair_v1_20261103/replay_io.py')
    count=0
    with install(replay,worker,output),replay.install(adapter,output=output/'replay_status',cache_root=output/'unused_cache',scratch_root=scratch,deadline=spec['deadline']-120,guard=guard,heartbeat=guard.progress) as patched:
        patched.active=dict(role='UDP',frame=0,start=time.monotonic(),append_seconds=0.,decoder_next_seconds=0.,selected_persisted=0)
        stream=snapshots(adapter,patched,spool,expected,output/'replay_checkpoints/UDP','UDP',[r['frame'] for r in selected['UDP']],output/'decode',interval_seconds=10**9,value=source,tshark=Path(runtime['tshark']),deadline=spec['deadline']-120)
        try:
            for snapshot in stream:
                require(snapshot['row']['frame']>2877608,'RESTORE_SUFFIX_FRAME')
                spool.append(merge_selected(snapshot,expected[snapshot['uid']]))
                count+=1
                if count==16:break
        finally:stream.close()
    attempt=read(output/'replay_checkpoints/UDP/LAST_ATTEMPT.json')
    require(count==16 and attempt['resume_from_frame']==2877608 and 0<attempt['numerical_frames_appended']<100000,'RESTORE_ACTUAL_SUFFIX')
    require(read(prior/'replay_checkpoints/UDP/CURRENT.json')==card['resume_plan']['checkpoint_pointer'],'RESTORE_SOURCE_UNCHANGED')
    atomic_json(output/'RESULT.json',dict(status='PASS_REAL_PRIOR_CHECKPOINT_RESTORE',resume_from_frame=2877608,selected_suffix_snapshots=count,numerical_frames_appended=attempt['numerical_frames_appended'],checkpoint_pointer=card['resume_plan']['checkpoint_pointer'],same_scientific_binding=True,source_unchanged=True))

def run(args,scratch):
    output=Path(args.output)/'prior_checkpoint_probe';output.mkdir()
    spec=dict(card=str(args.card),auth=str(args.authorization),runtime=str(args.runtime),output=str(output),scratch=str(Path(scratch)/'prior_checkpoint_probe'),deadline=args.deadline)
    atomic_json(output/'SPEC.json',spec)
    result=bounded_process([sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'--spec',str(output/'SPEC.json')],output/'RESTORE.log',args.deadline-120,session=True)
    require(result==0,'REAL_PRIOR_RESTORE_CHILD:'+str(result))
    return read(output/'RESULT.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--spec',required=True);child(parser.parse_args().spec)
