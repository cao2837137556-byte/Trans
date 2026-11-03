"""Resume only the complete Netatmo census; replay one continuous snapshot pass."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import numpy as np
from hnr.common import VERSION,read,write,sha,require,rows,write_rows,digest
from hnr.history import pin,role_binding,walk_decoded
from recovery import PREVIOUS,LATEST
from decoder_guard import parse_stderr,audit_packet,diagnostic_signature

COUNTS={'HIST_REF':2612450,'HIST_DEV':980497}
TSHARK_SHA='08573896ff5af2028972278388d7bd3b5cb3fb635a1e105bf45284adef93c301'

def census_check(member):
    member=Path(member)
    state=read(PREVIOUS/'outputs/encoding/workers/NETATMO_prepare.json')
    require(state['phase']=='ENDPOINT_CENSUS' and state['raw_packets']==state['total']==4967010,'COMPLETE_FIRST_PASS_STATUS')
    require(state['legal_endpoints']==COUNTS,'FIRST_PASS_COUNTS')
    error=read(PREVIOUS/'outputs/encoding/workers/NETATMO_prepare_ERROR.json')
    require(error['error']=='DECODER_STDERR' and 'process.wait' not in error['traceback'],'EXPECTED_LOG_POLICY_FAILURE')
    warning=parse_stderr((member/'decoder_pass1.stderr.log').read_bytes(),packets=4967010)
    require(sum(warning.values())==492 and warning,'EXACT_PRIOR_WARNING_COUNT')
    db=sqlite3.connect('file:'+str((member/'candidates.sqlite').resolve())+'?mode=ro',uri=True)
    try:
        require(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'CENSUS_SQLITE_INTEGRITY')
        actual=dict(db.execute('SELECT role,count(*) FROM candidates GROUP BY role'))
        require(actual==COUNTS,'COMPLETE_COMMITTED_CENSUS')
        require(db.execute('SELECT count(*) FROM physical_origins').fetchone()[0]==sum(COUNTS.values()),'PHYSICAL_CENSUS_COUNT')
        require(db.execute('SELECT count(*) FROM candidates c LEFT JOIN physical_origins p ON p.uid=c.uid WHERE p.uid IS NULL').fetchone()[0]==0,'PHYSICAL_CENSUS_JOIN')
    finally:db.close()
    logical=read(member/'LOGICAL_INPUT.json')
    require(logical['decoder']['executable_sha256']==TSHARK_SHA and logical['decoder']['unfiltered'] is True and len(logical['decoder']['fields'])==56,'FROZEN_CHECKPOINT_DECODER')
    return warning,logical

def copy_checked(source,target,runtime):
    source,target=Path(source),Path(target);require(not target.exists(),'NEW_CHECKPOINT_COPY')
    before=(source.stat().st_size,source.stat().st_mtime_ns);h=hashlib.sha256();done=0
    with source.open('rb') as r,target.open('xb') as w:
        for chunk in iter(lambda:r.read(4*1024**2),b''):
            w.write(chunk);h.update(chunk);done+=len(chunk)
            if done%(128*1024**2)==0:runtime.update('CHECKPOINT_COPY',completed=done,total=before[0],checkpoint_file=source.name)
    require(before==(source.stat().st_size,source.stat().st_mtime_ns),'CHECKPOINT_SOURCE_MUTATED')
    require(done==before[0] and sha(target)==h.hexdigest(),'CHECKPOINT_COPY_PIN')
    return dict(bytes=done,sha256=h.hexdigest())

def link_checked(source,target,runtime):
    """Retain immutable data; all later census connections use mode=ro."""
    source,target=Path(source),Path(target)
    require(not source.is_symlink() and not target.exists(),'NEW_CHECKPOINT_LINK')
    before=(source.stat().st_size,source.stat().st_mtime_ns);expected=sha(source)
    try:os.link(source,target);method='HARDLINK_READ_ONLY_USE'
    except OSError:return dict(method='COPY',**copy_checked(source,target,runtime))
    require(before==(source.stat().st_size,source.stat().st_mtime_ns) and sha(target)==expected,'CHECKPOINT_LINK_PIN')
    return dict(method=method,bytes=before[0],sha256=expected)

def indexed_checkpoint():
    source=LATEST/'outputs/encoding/history/NETATMO'
    warnings,logical=census_check(source)
    checkpoint=read(source/'CENSUS_CHECKPOINT.json')
    require(checkpoint['previous_job']=='180552' and checkpoint['legal_endpoints']==COUNTS,'INDEXED_CENSUS_PROVENANCE')
    for name in ('LOGICAL_INPUT.json','ROLE_BINDING.json','decoder_pass1.stderr.log','chronological.pcapng'):
        require(sha(source/name)==checkpoint['files'][name]['sha256'],'INDEXED_CHECKPOINT_PIN:'+name)
    selection=read(source/'selection/SELECTION.json')
    require(selection['status']=='SELECTED' and selection['census_sha256']==sha(source/'candidates.sqlite'),'INDEXED_CENSUS_SELECTION_PIN')
    for role,n in (('ref_rows',8192),('dev_rows',4096)):
        item=selection[role];path=source/'selection'/Path(item['path']).name
        require(path.resolve()==Path(item['path']).resolve() and item['rows']==n and sha(path)==item['sha256'],'RETAINED_SELECTION_PIN')
        rr=list(rows(path));require(len(rr)==n and digest(sorted(r['uid'] for r in rr))==item['uid_sha256'],'RETAINED_SELECTION_UIDS')
    return source,warnings,logical,selection

def prepare_member(spec,output,old_rows,runtime,tshark):
    require(spec['key']=='NETATMO','ONLY_NETATMO_REMAINS')
    import legacy_reference_sample_prepare_v1 as prep
    from legacy_unsw_archival_runtime_v1 import decode,fields
    from hnr.contexts import Contexts
    source,warnings,logical,selection=indexed_checkpoint();output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    runtime.update('CHECKPOINT_VERIFY',device=spec['display_name'])
    raw=pin(spec['raw']);before=(raw.stat().st_size,raw.stat().st_mtime_ns)
    index=np.load(pin(spec['packet_index']),mmap_mode='r',allow_pickle=False)
    order=np.load(pin(spec['chronological_order']),mmap_mode='r',allow_pickle=False)
    binding=role_binding(index,order,spec)
    saved_binding=read(source/'ROLE_BINDING.json')
    require(all(saved_binding[k]==v for k,v in binding.items()),'CHECKPOINT_BINDING_REPLAY')
    require(logical['raw']==spec['raw'] and logical['packet_index']==spec['packet_index'] and logical['chronological_order']==spec['chronological_order'],'CHECKPOINT_INPUT_PIN')
    require(sha(tshark)==TSHARK_SHA,'EXACT_TSHARK_BINARY')
    api=prep.old.legacy_runtime();require(fields(api)==logical['decoder']['fields'],'EXACT_FROZEN_FIELDS')
    require(subprocess.run([str(tshark),'--version'],capture_output=True,text=True,check=True,timeout=30).stdout.splitlines()[0]==logical['decoder']['version'].splitlines()[0],'EXACT_DECODER_VERSION')
    pins={}
    for name in ('LOGICAL_INPUT.json','ROLE_BINDING.json','decoder_pass1.stderr.log','chronological.pcapng','candidates.sqlite'):
        pins[name]=link_checked(source/name,output/name,runtime)
    require(pins['chronological.pcapng']['sha256']==logical['source_sha256'],'CHRONOLOGICAL_SOURCE_PIN')
    write(output/'CENSUS_CHECKPOINT.json',dict(previous_job='180591',original_complete_census_job='180552',original_member=str(source),files=pins,complete_first_pass_packets=len(order),legal_endpoints=COUNTS,original_frontend_reason_counts_persisted=False))
    dbpath=output/'candidates.sqlite'
    runtime.update('DETERMINISTIC_SELECTION_REUSED',device=spec['display_name'])
    (output/'selection').mkdir()
    for role in ('ref_rows','dev_rows'):
        item=selection[role];name=Path(item['path']).name
        link_checked(source/'selection'/name,output/'selection'/name,runtime)
        item['path']=str(output/'selection'/name)
    write(output/'selection/SELECTION.json',selection)
    write(output/'SELECTION_REUSE.json',dict(previous_job='180591',source_sha256=sha(source/'selection/SELECTION.json'),paths_explicitly_relocated=True,independent_selection_replay_before_encoding=True))
    require(selection['status']=='SELECTED','CHECKPOINT_SELECTION')
    rr=list(rows(selection['ref_rows']['path']))+list(rows(selection['dev_rows']['path']))
    selected={r['uid']:r for r in rr};require(len(selected)==len(rr),'REF_DEV_UID_OVERLAP')
    runtime.update('SELECTED_SNAPSHOTS',device=spec['display_name'],raw_packets=0,total=len(order),decoder_pass=2,selected_ref=selection['ref_rows']['rows'],selected_dev=selection['dev_rows']['rows'],completed_census_reused=True)
    db=sqlite3.connect('file:'+str(dbpath.resolve())+'?mode=ro',uri=True)
    audit=db.execute('SELECT frame,uid,body FROM candidates ORDER BY frame')
    contexts=Contexts(spec['capture_id'],spec['known_macs'],api[0],required_owners={spec['owner']},storage_path=output/'contexts_2.sqlite',resident_contexts=256)
    snapshots=[];audited={};observation=None;stderr_exception=False
    log=output/'decoder_pass2.stderr.log'
    try:
        with raw.open('rb') as raw_stream:
            try:
                with decode(output/'chronological.pcapng',{},api,runtime,log,tshark) as decoded:
                    def packets():
                        for packet in decoded:
                            frame=int(packet['frame.number'])
                            if frame in warnings:audited[frame]=audit_packet(packet,raw_stream,index[int(order[frame-1])])
                            yield packet
                    observation=walk_decoded(packets(),spec,binding,index,order,logical['source_sha256'],contexts,runtime,selected=selected,snapshots=snapshots,audit_census=audit)
            except RuntimeError as exc:
                if str(exc)!='DECODER_STDERR' or observation is None:raise
                stderr_exception=True
    finally:contexts.close();db.close()
    replay_warnings=parse_stderr(log.read_bytes(),packets=len(order))
    require(stderr_exception and replay_warnings==warnings and diagnostic_signature(log.read_bytes(),packets=len(order))==diagnostic_signature((output/'decoder_pass1.stderr.log').read_bytes(),packets=len(order)),'EXACT_WARNING_FRAME_MULTISET_REPLAY')
    require(set(audited)==set(warnings),'ALL_WARNING_FRAMES_RAW_HEADER_AUDITED')
    require(observation['legal_endpoints']==COUNTS and observation['packets']==len(order),'FULL_CENSUS_REPLAY')
    snapshots.sort(key=lambda x:x['uid']);write_rows(output/'selected_snapshots.jsonl.gz',snapshots)
    require(before==(raw.stat().st_size,raw.stat().st_mtime_ns),'RAW_MUTATED_DURING_PREPARATION')
    write(output/'DECODER_DIAGNOSTIC_AUDIT.json',dict(policy='ONLY_EXACT_OBSERVED_MPEG_SECT_AND_FRAME4058042_PES_DIAGNOSTIC_AFTER_RAW_HEADER_AUDIT',tshark_sha256=TSHARK_SHA,prior_stderr_sha256=pins['decoder_pass1.stderr.log']['sha256'],new_stderr_sha256=sha(log),warning_records=sum(warnings.values()),warning_frames=len(warnings),frame_multiplicity=dict(warnings),raw_header_audits=audited,all_other_diagnostics_rejected=True,decoder_exit_zero=True))
    receipt=dict(status='PREPARED',version=VERSION,source_sha256=logical['source_sha256'],selection=selection,role_binding=saved_binding,logical_input_sha256=sha(output/'LOGICAL_INPUT.json'),census_sha256=sha(dbpath),snapshots_sha256=sha(output/'selected_snapshots.jsonl.gz'),observations=[dict(recovered_complete_census=True,packets=len(order),legal_endpoints=COUNTS,frontend_reasons=None),observation],raw_packet_copy_traversals=0,raw_integrity_full_reads=1,complete_decoder_traversals=1,reused_complete_decoder_traversals=1,input_readout='RECENT_CURRENT_INCLUSIVE',real_E3_forwards=0,all_legal_endpoint_rows_exactly_replayed=True,diagnostic_audit_sha256=sha(output/'DECODER_DIAGNOSTIC_AUDIT.json'))
    write(output/'PREPARE_RESULT.json',receipt);return receipt
