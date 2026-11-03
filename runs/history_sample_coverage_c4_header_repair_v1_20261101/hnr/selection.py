"""C4 full-census reference selection; original component-balanced Netatmo DEV."""
import json
from pathlib import Path
import sqlite3
from .common import PACKAGE,TARGETS,VERSION,DEV_CAP,digest,read,require,sha,write,write_rows
from .component_selection import _allocate,point_rank
from topup_selector import select

def select_candidates(db_path,old_rows,output_dir,*,devices=None):
    require(devices is not None and len(devices)==1,'ONE_MEMBER_SELECTION')
    device=devices[0]
    spec=next(x for x in read(PACKAGE/'config/EXECUTION.json')['devices'] if x['device']==device)
    admitted={device:dict(raw_sha256=spec['raw']['sha256'],owner=spec['owner'],
        reference_end_us=spec['reference_end_us'],bank_end_frame=spec['bank_end_frame'])}
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect('file:'+Path(db_path).resolve().as_posix()+'?mode=ro',uri=True)
    try:
        db.execute('PRAGMA temp_store=FILE');db.execute('PRAGMA cache_size=-32768')
        require(db.execute('SELECT count(*) FROM candidates').fetchone()[0]==db.execute('SELECT count(*) FROM physical_origins').fetchone()[0],'GLOBAL_PHYSICAL_COUNT')
        require(db.execute('SELECT count(*) FROM candidates c LEFT JOIN physical_origins p ON p.uid=c.uid WHERE p.uid IS NULL').fetchone()[0]==0,'GLOBAL_PHYSICAL_UID_JOIN')
        require({x[0] for x in db.execute('SELECT DISTINCT device FROM candidates')}=={device},'EXACT_MEMBER_CENSUS')
        def metadata(role):
            for uid,dev,proto,component,timestamp,frame,actual_role,rank,body in db.execute('SELECT * FROM candidates WHERE role=? ORDER BY uid',(role,)):
                row=json.loads(body)
                require([row[k] for k in ('uid','device','protocol','component_id','timestamp','frame','history_role')]==[uid,dev,proto,component,timestamp,frame,actual_role],'CENSUS_METADATA_JOIN')
                require(rank==point_rank(uid)[0],'CENSUS_FROZEN_RANK')
                origin=db.execute('SELECT raw_sha,ordinal,owner FROM physical_origins WHERE uid=?',(uid,)).fetchone()
                require(origin==(row['origin_raw_sha256'],row['origin_packet_ordinal'],row['owner']),'CENSUS_PHYSICAL_JOIN')
                yield row
        chosen,summary=select(metadata('HIST_REF'),old_rows,admitted)
        dev=[];dev_stats=None
        if spec['key']=='NETATMO':
            db.execute('CREATE TEMP TABLE old_components(device TEXT,protocol INTEGER,component_id TEXT,PRIMARY KEY(device,protocol,component_id)) WITHOUT ROWID')
            db.execute('CREATE TEMP TABLE census_groups AS SELECT device,protocol,role,component_id,count(*) AS n,min(rank||uid) AS point_order FROM candidates GROUP BY device,protocol,role,component_id')
            db.execute('CREATE INDEX temp.group_lookup ON census_groups(device,role,protocol,point_order)')
            selected,dev_stats=_allocate(db,device,'HIST_DEV',DEV_CAP)
            for uid in sorted(selected):
                body=db.execute('SELECT body FROM candidates WHERE uid=?',(uid,)).fetchone()[0]
                row=json.loads(body);require(row['history_role']=='HIST_DEV' and row['use']=='QUERY' and row['timestamp_us']>spec['reference_end_us'] and row['frame']>spec['bank_end_frame'],'DEV_ROLE_TIME')
                dev.append(row)
            require(dev,'EMPTY_NETATMO_DEV')
        require(not {r['uid'] for r in chosen}&{r['uid'] for r in dev},'REF_DEV_OVERLAP')
        specs={}
        for role,rr in (('HIST_REF',chosen),('HIST_DEV',dev)):
            path=output/(role+'.jsonl.gz');write_rows(path,sorted(rr,key=lambda r:r['uid']))
            specs[role]=dict(path=str(path),sha256=sha(path),rows=len(rr),uid_sha256=digest(sorted(r['uid'] for r in rr)))
        result=dict(status='SELECTED',version=VERSION,device_scope=devices,candidate_domain='ALL_LEGAL_ENDPOINTS',
            census_sha256=sha(db_path),ref_rows=specs['HIST_REF'],dev_rows=specs['HIST_DEV'],
            groups=summary['groups'],selection_rule=summary,dev_rule='C1_ALL_COMPONENT_ROUND_ROBIN_THEN_UNIFORM_TIME',
            dev_stats=dev_stats,previous_three_DEV_reused=True,global_physical_uniqueness=True)
        write(output/'SELECTION.json',result);return result
    finally:db.close()
