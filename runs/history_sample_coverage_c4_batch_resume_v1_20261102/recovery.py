"""Read-only verification and reuse of the three complete job-180552 members."""
import math
import os
import hashlib
from pathlib import Path
import shutil
import numpy as np
from hnr.common import ROOT,PACKAGE,read,rows,sha,write,require,digest

PREVIOUS=ROOT/'runs/history_sample_coverage_c4_memory_repair_v1_20261101'
LATEST=ROOT/'runs/history_sample_coverage_c4_checkpoint_repair_v1_20261101'
KEYS=('TP_LINK','WEMO_POWER','SAMSUNG')
EXPECTED={'TP_LINK':4096,'WEMO_POWER':8192,'SAMSUNG':8192}

def previous_status():
    state=read(PREVIOUS/'outputs/encoding/STATUS.json')
    require(state['technical_status']=='EXCEPTION_STOPPED' and state['error'].startswith('ISOLATED_NETATMO_prepare_FAILED:'),'EXPECTED_PREVIOUS_FAILURE')
    require(state['encoded_rows']==20480 and state['pairs']==0,'PREVIOUS_NO_EVALUATION')
    require(not (PREVIOUS/'outputs/evaluation').exists(),'NO_PREVIOUS_CANDIDATE_EVALUATION')
    card=read(PACKAGE/'EXECUTION_CARD.json')
    require(sha(PREVIOUS/'EXECUTION_CARD.json')==card['recovery']['previous_card_sha256'],'PREVIOUS_CARD')
    latest=read(LATEST/'outputs/encoding/STATUS.json')
    require(sha(LATEST/'EXECUTION_CARD.json')==card['recovery']['latest_failed_card_sha256'],'LATEST_FAILED_CARD')
    require(latest['technical_status']=='EXCEPTION_STOPPED' and latest['encoded_rows']==20480 and latest['pairs']==0,'LATEST_NO_EVALUATION')
    require(not (LATEST/'outputs/evaluation').exists(),'LATEST_NO_CANDIDATE_EVALUATION')
    require(read(LATEST/'outputs/encoding/workers/NETATMO_prepare_ERROR.json')['error']=='AUDIT_INVALID_INTEGER:tcp.flags.syn','EXACT_HEADER_PARSER_FAILURE')
    from prepared_reuse import source_package
    prepared_package=source_package(card)
    require(sha(prepared_package/'EXECUTION_CARD.json')==card['recovery']['prepared_source_card_sha256'],
            'PREPARED_ATTEMPT_CARD')
    status_path=prepared_package/'outputs/encoding/STATUS.json'
    require(sha(status_path)==card['recovery']['prepared_source_status_sha256'],'PREPARED_ATTEMPT_STATUS_PIN')
    prepared_state=read(status_path)
    require(prepared_state['technical_status']=='EXCEPTION_STOPPED' and
            prepared_state['error']=='WALL_SECONDS_LIMIT' and prepared_state['pairs']==0 and
            prepared_state['phase']=='HISTORY_E3' and prepared_state['encoded_rows']==32768,
            'EXPECTED_EXHAUSTED_PREPARED_ATTEMPT')
    require(not (prepared_package/'outputs/evaluation').exists(),'PREPARED_ATTEMPT_NO_EVALUATION')
    encoded=prepared_package/'outputs/encoding/history/NETATMO/encoded'
    require({p.name for p in encoded.iterdir()}=={'BATCH_LEDGER.jsonl'}, 'LEGACY_NETATMO_HAS_NO_RECOVERABLE_ARRAYS')
    ledger=list(rows(encoded/'BATCH_LEDGER.jsonl'))
    charged_forward=sum(b['logical_rows'] for b in ledger if b['status']=='ATTEMPT')
    complete_forward=sum(b['logical_rows'] for b in ledger if b['status']=='COMPLETE')
    require(charged_forward==4674 and complete_forward==4658 and
            prepared_state['worker_encoded_charged']==charged_forward and prepared_state['completed']==complete_forward,
            'UNPERSISTED_LEGACY_FORWARD_ACCOUNTING')
    require(card['recovery']['prior_encoded_rows_charged']==20480+charged_forward and
            card['recovery']['reused_encoded_rows']==20480 and card['recovery']['new_encoded_rows']==12288,
            'CUMULATIVE_FORWARD_ACCOUNTING')
    charged=9064+math.ceil(float(state['elapsed_seconds']))+60+math.ceil(float(latest['elapsed_seconds']))+60
    charged+=math.ceil(float(prepared_state['elapsed_seconds']))+60
    require(charged==card['recovery']['prior_wall_seconds_charged'],'PRIOR_WALL_CHARGE')
    require(read(PREVIOUS/'outputs/encoding/workers/NETATMO_prepare_ERROR.json')['error']=='DECODER_STDERR','EXACT_NETATMO_FAILURE')
    return dict(completed_encoding_source=state,latest_failed_snapshot_replay=latest,
                completed_preparation_source=prepared_state,prior_encoded_rows_charged=20480+charged_forward,
                unrecoverable_legacy_completed_rows=complete_forward,prior_wall_seconds_charged=charged)

def check_member(key):
    require(key in KEYS,'ONLY_COMPLETED_MEMBERS')
    member=PREVIOUS/'outputs/encoding/history'/key;encoded=member/'encoded'
    result=read(encoded/'ENCODE_RESULT.json');prepare=read(member/'PREPARE_RESULT.json');selection=read(member/'selection/SELECTION.json')
    require(result['status']=='COMPLETE' and not result['synthetic_only'],'COMPLETE_REAL_ENCODING')
    require(result['rows']==EXPECTED[key] and result['prepared_receipt_sha256']==sha(member/'PREPARE_RESULT.json'),'ENCODE_PREPARE_LINK')
    require(prepare['status']=='PREPARED' and prepare['logical_input_sha256']==sha(member/'LOGICAL_INPUT.json') and prepare['snapshots_sha256']==sha(member/'selected_snapshots.jsonl.gz'),'PREPARE_SOURCE_LINK')
    mandatory={'references.jsonl.gz','queries.jsonl.gz','references.npz','queries.npz','tensor_receipts.jsonl.gz','BATCH_LEDGER.jsonl'}
    require(mandatory<=set(result['files']),'REUSED_ARTIFACT_SET')
    for name,pin in result['files'].items():require(sha(encoded/name)==pin,'REUSED_ENCODE_PIN:'+name)
    rr=list(rows(encoded/'references.jsonl.gz'));qq=list(rows(encoded/'queries.jsonl.gz'))
    require(len(rr)==EXPECTED[key] and not qq and all(r['use']=='REFERENCE' and r['history_role']=='HIST_REF' for r in rr),'REUSED_ROLES')
    require(selection['ref_rows']['rows']==len(rr) and selection['dev_rows']['rows']==0,'REUSED_SELECTION_COUNT')
    require(rr==list(rows(member/'selection/HIST_REF.jsonl.gz')),'REUSED_SELECTION_ROWS')
    with np.load(encoded/'references.npz',allow_pickle=False) as z:
        require(z['uid'].tolist()==[r['uid'] for r in rr],'REUSED_ARRAY_UID')
        e3=z['e3'].copy();q14=z['q14'].copy()
    require(e3.shape==(len(rr),768) and q14.shape==(len(rr),14) and e3.dtype==q14.dtype==np.float32 and np.isfinite(e3).all() and np.isfinite(q14).all(),'REUSED_ARRAY_SCHEMA')
    with np.load(encoded/'queries.npz',allow_pickle=False) as z:require(z['uid'].tolist()==[] and z['e3'].shape==(0,768) and z['q14'].shape==(0,14),'REUSED_EMPTY_QUERY_ARRAY')
    tensors=list(rows(encoded/'tensor_receipts.jsonl.gz'));require(len(tensors)==len(rr) and len({r['uid'] for r in tensors})==len(rr),'REUSED_TENSOR_COVERAGE')
    grouped={}
    for t in tensors:
        slot=t['slot'];require(0<=slot<len(rr) and t['uid']==rr[slot]['uid'] and t['feature_sha256']==hashlib.sha256(e3[slot].tobytes()).hexdigest(),'REUSED_FEATURE_RECEIPT')
        grouped.setdefault(t['batch_id'],[]).append(t['uid'])
    attempts={};completed={}
    for b in rows(encoded/'BATCH_LEDGER.jsonl'):
        require(b['status'] in ('ATTEMPT','COMPLETE'),'REUSED_BATCH_STATUS');target=attempts if b['status']=='ATTEMPT' else completed
        require(b['batch'] not in target,'REUSED_DUPLICATE_BATCH');target[b['batch']]={k:v for k,v in b.items() if k!='status'}
    require(attempts==completed and set(completed)==set(grouped),'REUSED_BATCH_COMPLETION')
    for batch,ids in grouped.items():require(completed[batch]['logical_rows']==len(ids) and completed[batch]['uid_sha256']==digest(sorted(ids)),'REUSED_BATCH_UID_RECEIPT')
    require(read(member/'INTERMEDIATE_CLEANUP.json')['selected_evidence_retained'],'COMPLETED_MEMBER_CLEANUP')
    return dict(source=member,rows=len(rr),encode_sha256=sha(encoded/'ENCODE_RESULT.json'),selection_sha256=sha(member/'selection/SELECTION.json'))

def reuse_member(key,destination):
    checked=check_member(key);source=checked.pop('source');destination=Path(destination)
    require(not destination.exists(),'REUSE_DESTINATION_NEW')
    destination.mkdir(parents=True)
    pins={}
    for p in sorted(source.rglob('*')):
        if not p.is_file():continue
        require(not p.is_symlink(),'REUSE_NO_LINK_SOURCE')
        rel=p.relative_to(source);target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True)
        try:os.link(p,target)
        except OSError:shutil.copyfile(p,target)
        pins[rel.as_posix()]=sha(p);require(sha(target)==pins[rel.as_posix()],'REUSE_EXACT_BYTES')
    write(destination/'REUSE_RECEIPT.json',dict(previous_job='180552',source=str(source),files=pins,**checked))
    return checked
