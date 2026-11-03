"""Create an isolated C4 runner from pinned C1 engineering primitives."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'runs/history_normal_reference_keyrepair_v1_20261031'
PROPOSAL=ROOT/'runs/history_sample_coverage_c4_v1_20261101'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
origin={}
for name in ('__init__.py','common.py','contexts.py','history.py','encoding.py','assets.py','evaluation.py','runtime.py','selection.py'):
    source=OLD/'hnr'/name;origin['hnr/'+name]=sha(source)
    target=HERE/'hnr'/('component_selection.py' if name=='selection.py' else name)
    target.parent.mkdir(exist_ok=True)
    text=source.read_text(encoding='utf-8')
    if name=='common.py':
        text=text.replace("VERSION = 'history-normal-reference-r2-c1-keyrepair-20261031'","VERSION = 'history-sample-coverage-c4-v1-20261101'")
        text=text.replace("    'TP_LINK':", "    'NETATMO': dict(owner='70:ee:50:18:34:43', display_name='Netatmo Camera', reference_end_us=1485907186758350, bank_end_frame=3766102, first_dev_time_us=1485907201277175, packets=4967010),\n    'TP_LINK':",1)
        text=text.replace('PAIR_LIMIT = 579614444','PAIR_LIMIT = 1000000000')
    if name=='history.py':
        text=text.replace("    return db\n", "    db.execute('CREATE TABLE physical_origins(raw_sha TEXT,ordinal INTEGER,owner TEXT,uid TEXT UNIQUE,PRIMARY KEY(raw_sha,ordinal,owner)) WITHOUT ROWID')\n    return db\n",1)
        text=text.replace("                rank = hashlib.sha256", "                census.execute('INSERT INTO physical_origins VALUES (?,?,?,?)', (row['origin_raw_sha256'],row['origin_packet_ordinal'],row['owner'],row['uid']))\n                rank = hashlib.sha256",1)
    if name=='encoding.py':
        text=text.replace("        require(len(rr) > 0, 'EMPTY_ENCODED_ROLE')", "        # C4 reuses the three existing DEV encodings; saturated REF groups may be empty.\n        require(role in ('HIST_REF','HIST_DEV'), 'ENCODED_ROLE')")
    if name=='runtime.py':
        text=text.replace('rss_bytes=16 * 2**30','rss_bytes=8 * 2**30')
        # No extra A/B encodings: 32768 new reference ceiling + Netatmo DEV 4096.
        text=text.replace("[PACKAGE / 'run.py', PACKAGE / 'progress.py', PACKAGE / 'progress.html',", "[*PACKAGE.glob('*.py'),")
    with target.open('x',encoding='utf-8') as f:f.write(text)
for source,target in ((PROPOSAL/'selection.py',HERE/'topup_selector.py'),(OLD/'config/ASSETS.json',HERE/'config/ASSETS.json'),(OLD/'config/ENCODER_RUNTIME_FILES.json',HERE/'config/ENCODER_RUNTIME_FILES.json')):
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(source.read_bytes())
    origin[str(source.relative_to(ROOT))]=sha(source)
cfg=read(OLD/'config/EXECUTION.json');cfg['candidate']='C4_HISTORY_SAMPLE_COVERAGE_TOPUP'
cfg['version']='history-sample-coverage-c4-v1-20261101';cfg['assets_manifest']=str(HERE/'config/ASSETS.json')
diag=ROOT/'runs/b_sample_fpr_mechanism_v1_20261101'
raw=read(diag/'NETATMO_RAW_ACCEPTANCE.json')['member'];info=read(diag/'NETATMO_CHRONOLOGY_AND_ROLE_PROPOSAL.json');idx=info['index_receipt'];role=info['role_proposal']
net=dict(cfg['devices'][0]);net.update(key='NETATMO',owner=raw['owner_MAC'],device='unsw-attack-traces-2018:'+raw['owner_MAC'],display_name='Netatmo Camera',
    capture_id='c4-history-netatmo-'+raw['sha256'][:16],raw={k:raw[k] for k in ('path','sha256','bytes')},
    packet_index=dict(path=idx['packet_index'],sha256=idx['packet_index_sha256']),chronological_order=dict(path=idx['chronological_order'],sha256=idx['chronological_order_sha256']))
net.update({k:role[k] for k in ('reference_end_us','bank_end_frame','first_dev_time_us','packets')});cfg['devices'].append(net)
write(HERE/'config/EXECUTION.json',cfg)
write(HERE/'VENDOR_ORIGIN.json',dict(source_sha256=origin,policy='Separate copies; no C1/C2/C3 files modified.'))
print('C4_ISOLATED_MODULES_CREATED')
