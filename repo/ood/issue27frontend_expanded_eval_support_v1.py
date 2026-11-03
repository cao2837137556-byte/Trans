"""Fixed AB expanded development evaluation: metadata, receipts and metrics."""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import issue27frontend_expanded_eval_scope_v1 as scope

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'runs/frontend_expanded_eval_implementation_v1_20260910'
REAL = ROOT / 'runs/frontend_expanded_eval_v1_20260910'
PYTHON = Path('C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe')
AUTH = 'USER_CONFIRMED_HISTORICAL_REPORT_AND_RAW_INPUT_FIXED_AB_EVALUATION_20260910'
PINS = {scope.OLD + k: v for k, v in scope.REPORT_REFERENCES.items()}
PINS.update({k:v for k,v in scope.ALLOWED.items() if v is not None and not k.endswith(('check_predictions.json','postfit_predictions.json'))})
PINS.update({
    'runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_packet_identity_attachment.csv': '5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c',
    'runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_r0_identity_audit.json': '41b524918af9fd07d65460bc2e7c86367b1ba1bc6c1522bc0a9683adc2c68e11',
})
FINAL = re.compile(r'cooler[-_]motor|seed[-_ ]?(?:37|47)(?:\D|$)',re.I)
CAPS = dict(wall_seconds=28800,memory_bytes=8*1024**3,output_bytes=40*1024**3,
            minimum_free_bytes=42*1024**3,decoder_passes=80,packets_per_pass_total=23148691)
EXPECTED_FAMILIES = {
    'C&C Communication':179,'CoAP Amplification':320,'File Download':2569,
    'Ingress Tool Transfer':10069,'Merlin C&C Communication':9926,'Merlin ICMP Flooding':19730,
    'Merlin TCP Flooding':27722,'Merlin UDP Flooding':10298,'Mirai C&C Communication':369,
    'Mirai GRE Flooding':27722,'Mirai TCP Flooding':27721,'Mirai UDP Flooding':27722,
    'Reporting':167,'TCP Scan':39711,'Telnet Brute Force':39712,'UDP Scan':113,
}


def require(ok,reason):
    if not ok: raise RuntimeError(reason)


def sha_file(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):
            h.update(b);check()
    return h.hexdigest()


def atomic_json(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_csv(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)


def ordinal(value):
    require(bool(re.fullmatch(r'(0|[1-9][0-9]*)(\.0+)?',str(value))),'PACKET_ORDINAL')
    return int(str(value).split('.')[0])


def boolean(value):
    require(str(value).lower() in ('true','false','0','1'),'BOOLEAN_VALUE')
    return int(str(value).lower() in ('true','1'))


def seal(folder):
    files=sorted(p for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    require(not (folder/'SHA256SUMS').exists(),'ALREADY_SEALED')
    temporary=folder/'SHA256SUMS.tmp'
    with temporary.open('x',encoding='utf-8',newline='\n') as f:
        for p in files:f.write(sha_file(p)+'  '+p.relative_to(folder).as_posix()+'\n')
    os.replace(temporary,folder/'SHA256SUMS')


def validate_targets(rows):
    require(len(rows)==262050 and len({r['uid'] for r in rows})==262050,'REPORT_UID_COUNT')
    require(Counter(r['role'] for r in rows)==scope.REPORT_ROLES,'REPORT_ROLE_COUNTS')
    require(Counter(r['attack_family'] for r in rows if r['label']==1)==EXPECTED_FAMILIES,'ATTACK_FAMILIES')
    require(Counter(r['pool'] for r in rows)=={p['pool']:p['targets'] for p in scope.POOLS},'REPORT_POOL_COUNTS')
    for t in rows:
        require(not any(FINAL.search(str(t[k])) for k in ('uid','source_group','member')),'FINAL_TARGET')
        require(t['label'] in (0,1) and (t['pool']=='GLOBAL_ATTACK_PRESERVATION')==(t['label']==1),'POOL_LABEL')


def prepare_metadata():
    require(not PACKAGE.exists(),'IMPLEMENTATION_NAMESPACE_EXISTS')
    PACKAGE.mkdir()
    atomic_json(PACKAGE/'authorization.json',{
        'authorization':AUTH,'user_reply':'是的，我要外出了，希望回来能看到测试结果。',
        'scope':'262050 disclosed report targets including old support_val/sealed_final_*; local raw inputs, fixed AB evaluation after input validation.',
        'no_training':True,'no_HPC':True,'no_download':True,'no_true_FINAL':True,'stop_on_error_zero_retry':True,
        'time_unix':time.time()})
    audit=[]
    for rel,h in PINS.items():
        require(sha_file(ROOT/rel)==h,'INPUT_SHA_DRIFT:'+rel);audit.append({'path':rel,'sha256':h})
    membership=list(read_csv(ROOT/scope.META/'membership.csv'))
    require(len(membership)==18266,'V3_MEMBERSHIP_COUNT')
    train={r['uid']:r for r in membership if r['new_role']=='train'}
    check={r['uid']:r for r in membership if r['new_role']=='check'}
    train_members={r['member'] for r in train.values()}
    check_members={r['member'] for r in check.values()}
    keys=('uid','role','source_group','device_family','attack_family','label_metric_only','held_value')
    plans={r['uid']:tuple(r[k] for k in keys) for r in read_csv(ROOT/scope.OLD/'ckda_d1_report_plan.csv')}
    require(len(plans)==262050,'PLAN_COUNT')
    rows=[];groups={}
    for r in read_csv(ROOT/scope.OLD/'ckda_d1_report_target_metadata.csv'):
        require(plans.pop(r['uid'],None)==tuple(r[k] for k in keys),'PLAN_METADATA_JOIN')
        require(r['plan_scope']=='REPORT_ONE_SHOT_ONLY' and boolean(r['metadata_matched']) and not boolean(r['review']) and r['seed']=='27','METADATA_SCOPE')
        member=r['raw_source_path'];container=r['container_path']
        require(r['dataset_kind']=='gotham_zip' and not FINAL.search(member) and not FINAL.search(container),'RAW_ALLOWLIST')
        t=dict(uid=r['uid'],role=r['role'],pool=r['held_value'],source_group=r['source_group'],
               device_family=r['device_family'],attack_family=r['attack_family'],label=int(r['label_metric_only']),
               member=member,position=ordinal(r['target_event_position_within_capture']),
               uid_in_ab_train=r['uid'] in train,uid_in_ab_check=r['uid'] in check,
               member_in_ab_train=member in train_members,member_in_ab_check=member in check_members)
        rows.append(t)
        g=groups.setdefault(member,{'member':member,'container':container,'source_group':r['source_group'],'targets':0,'packets':0})
        require(g['container']==container and g['source_group']==r['source_group'],'MEMBER_SOURCE_ALIAS')
        g['targets']+=1;g['packets']=max(g['packets'],t['position']+1)
    require(not plans,'UNMATCHED_PLAN_TARGETS');validate_targets(rows)
    by_uid={r['uid']:r for r in rows};seen=set();scores_total=0
    for r in read_csv(ROOT/scope.OLD/'ckda_d1_report_scores.csv.gz'):
        scores_total+=1
        if r['probe_id']!='P2':continue
        uid=r['uid'];require(uid in by_uid and uid not in seen,'P2_UID');seen.add(uid);t=by_uid[uid]
        require(r['candidate_id']=='E3' and int(r['label_metric_only'])==t['label'] and not boolean(r['review']),'P2_SCOPE')
        for k in ('role','source_group','attack_family','device_family'):require(t[k]==r[k],'P2_METADATA_JOIN')
        t.update(old_hard=boolean(r['hard']),old_missing=boolean(r['missing']))
    require(scores_total==786150 and seen==set(by_uid),'P2_FULL_DENOMINATOR')
    require(sum(r['old_missing'] for r in rows)==64782,'OLD_MISSING_COUNT')
    require(len(groups)==40 and sum(g['packets'] for g in groups.values())==23148691,'MEMBER_PACKET_CENSUS')
    identities=list(read_csv(ROOT/'runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_packet_identity_attachment.csv'))
    identity=next(r for r in identities if r['dataset_kind']=='gotham_zip')
    archive=Path(identity['container_path'])
    require(all(Path(g['container'])==archive for g in groups.values()),'ARCHIVE_ALIAS')
    require(archive.stat().st_size==int(identity['container_bytes']),'ARCHIVE_SIZE')
    with zipfile.ZipFile(archive) as z:
        for member,g in groups.items():
            info=z.getinfo(member);require(not info.is_dir(),'RAW_MEMBER_DIRECTORY')
            g.update(id=hashlib.sha256(member.encode()).hexdigest()[:24],member_bytes=info.file_size,member_crc32='%08x'%info.CRC)
    require(shutil.disk_usage(str(ROOT)).free>CAPS['minimum_free_bytes'],'LOCAL_FREE_DISK')
    members=sorted(groups.values(),key=lambda g:g['member'])
    member_index={g['member']:g['id'] for g in members}
    for t in rows:t['member_id']=member_index[t['member']]
    rows.sort(key=lambda t:(t['member'],t['position'],t['uid']))
    require(len({(r['member'],r['position']) for r in rows})==len(rows),'DUPLICATE_TARGET_ORDINAL')
    with gzip.open(PACKAGE/'targets.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    ts=read_json(ROOT/'runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_r0_identity_audit.json')['tshark_identity']
    config={'authorization':AUTH,'head':scope.HEAD,'candidate_path':scope.RUN+'candidate_AB.pt',
            'candidate_file_sha256':PINS[scope.RUN+'candidate_AB.pt'],
            'candidate_state_sha256':'b800d9f1a3e11e557838cb9bdc22e7acc8559d198a57fa21a3da6c80bb7b9fda',
            'hard_rule':'logit >= 0','archive':str(archive),'archive_bytes':int(identity['container_bytes']),
            'archive_sha256':identity['container_sha256'],'tshark':ts,'members':members,'caps':CAPS,
            'targets_sha256':sha_file(PACKAGE/'targets.csv.gz'),'input_pins':PINS,
            'train_context_events':{},'check_context_keys':sorted({r['context_key'] for r in check.values()}),
            'exposed_development_only':True,'true_FINAL_opened':False}
    for r in train.values():
        k=r['context_key'];config['train_context_events'][k]=max(config['train_context_events'].get(k,-1),int(r['event_index']))
    census={'targets':len(rows),'attacks':244050,'benign_ood':18000,'members':40,
            'source_packets':23148691,'two_pass_decoder_packets':46297382,
            'old_missing':64782,'uid_overlap_train':sum(t['uid_in_ab_train'] for t in rows),
            'uid_overlap_check':sum(t['uid_in_ab_check'] for t in rows),
            'member_overlap_train':sum(t['member_in_ab_train'] for t in rows),
            'member_overlap_check':sum(t['member_in_ab_check'] for t in rows),
            'old_attack_hard':sum(t['old_hard'] for t in rows if t['label']),
            'role_counts':dict(Counter(t['role'] for t in rows)),
            'raw_packets_decoded':0,'model_forwards':0,'optimizer_steps':0,
            'old_report_opened_with_user_authorization':True,'true_FINAL_opened':False}
    atomic_json(PACKAGE/'config.json',config);atomic_json(PACKAGE/'metadata_census.json',census)
    atomic_json(PACKAGE/'metadata_access.json',{'verified':audit,'data_roles':scope.REPORT_ROLES,'select_score_files_opened':0,'viewed_files_opened':0,'old_embeddings_opened':0})
    return census


def metrics(rows):
    def count(rs):
        n=len(rs);positives=sum(t['label'] for t in rs);negatives=n-positives
        tp=sum(t['label']==1 and t['ab_hard']==1 for t in rs)
        fp=sum(t['label']==0 and t['ab_hard']==1 for t in rs)
        old_tp=sum(t['label']==1 and t['old_hard']==1 for t in rs)
        old_fp=sum(t['label']==0 and t['old_hard']==1 for t in rs)
        bad=sum(t['old_hard']==t['label'] and t['ab_hard']!=t['label'] for t in rs)
        good=sum(t['old_hard']!=t['label'] and t['ab_hard']==t['label'] for t in rs)
        return dict(targets=n,attacks=positives,benign=negatives,ab_attack_detected=tp,ab_false_alarms=fp,
                    old_attack_detected=old_tp,old_false_alarms=old_fp,
                    ab_recall=tp/positives if positives else None,old_recall=old_tp/positives if positives else None,
                    ab_fpr=fp/negatives if negatives else None,old_fpr=old_fp/negatives if negatives else None,
                    old_correct_new_wrong=bad,old_wrong_new_correct=good,
                    contexts=len({t['context_key'] for t in rs}),sources=len({t['source_group'] for t in rs}),
                    evidence='EXPOSED_DEVELOPMENT_ONLY')
    result={'overall':count(rows),'groups':[]}
    for fields in [('pool',),('role',),('attack_family',),('pool','owner'),('pool','source_group'),
                   ('pool','context_in_ab_train'),('pool','member_in_ab_train')]:
        grouped=defaultdict(list)
        for t in rows:grouped[tuple(t[k] for k in fields)].append(t)
        for values,part in sorted(grouped.items(),key=lambda p:str(p[0])):
            result['groups'].append({'dimensions':list(fields),'values':list(values),**count(part)})
    result['future_query']=count([t for t in rows if t['role']=='future_query'])
    result['attack']=count([t for t in rows if t['label']==1])
    return result


if __name__=='__main__':
    print(json.dumps(prepare_metadata(),ensure_ascii=False))
