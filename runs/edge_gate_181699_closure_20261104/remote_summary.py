import json,hashlib
from pathlib import Path
p=Path('/public/home/jiangxinwei.zr/work/paper04/runs/edge_formal_gate_deployment_v3_20261104/outputs/gate_181699')
h=p/'replay_status/REPLAY_HEARTBEAT.json'
v=json.loads(h.read_text());print('FINAL_HEARTBEAT',json.dumps({k:v.get(k) for k in ('stage','role','frame','selected_persisted','role_elapsed_seconds','append_seconds','decoder_next_seconds','elapsed_seconds','reason')},sort_keys=True))
for role in ('NORMAL','HTTP','UDP'):
 s=p/'spools'/role;c=s/'COMPLETE.json';r=s/'REPLAY_COVERAGE.json';v=json.loads(c.read_text()) if c.exists() else {};coverage=json.loads(r.read_text()) if r.exists() else {}
 print('ROLE',json.dumps(dict(role=role,complete_exists=c.exists(),uid_count=len(v.get('uids',[])),chunks=len(v.get('chunks',[])),complete_sha256=hashlib.sha256(c.read_bytes()).hexdigest() if c.exists() else None,coverage=coverage),sort_keys=True))
print('READ_ONLY_DIAGNOSIS_DONE')
