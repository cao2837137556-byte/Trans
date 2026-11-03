"""Build a separate adapter package; copy the sealed scientific package unchanged."""
import argparse,hashlib,json,shutil,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,default=3);args=parser.parse_args()
assert args.revision==3,'THIS_FIX_IS_REVISION_3'
out=HERE/'package_v3'
out.mkdir(exist_ok=True)
frozen=ROOT/'runs/onboarding_configured_v1r1_20261017/bundle'
if not (out/'frozen_onboarding').exists():shutil.copytree(frozen,out/'frozen_onboarding')
for p in (HERE/'src').glob('*.py'):shutil.copyfile(p,out/p.name)
shutil.copyfile(HERE/'src/resume_inputs_v3.json',out/'resume_inputs_v3.json')
shutil.copyfile(ROOT/'runs/ecs_migration_v1_20261019/new_lineage_service_v1/backup_chunks.py',out/'backup_chunks.py')
cfg=dict(schema='new-lineage-onboarding-cloud-v1',arm='QUERY_TAIL',optimizer_updates=0,retries=0,
    raw_worker_uid=65534,raw_worker_gid=65534,
    resume_manifest_sha256=sha(out/'resume_inputs_v3.json'),
    lineage_root='/srv/paper04/new_lineage_query_v1',query_root='/srv/paper04/assets/query_tail_v2r3',
    cache='/srv/paper04/cache/coupon_resume_20261020_v2',head_run='/srv/paper04/runs/query_twelve_heads_20261022_v1',
    checkpoint='/srv/paper04/assets/model.safetensors',tshark='/opt/paper04-wireshark-4.6.6/bin/tshark',
    raw=dict(CIC_DEV='/srv/paper04/assets/onboarding_raw/2021_11_02_Active.pcap',UNSW_DEV='/srv/paper04/assets/onboarding_raw/unsw-benign-20180528.pcap'),
    lineage_manifest_sha256='522faf0a0d02f031255fed88e9144dee0dee0a568a72443e0489b6ab76bdd0f4',
    onboarding_seal_sha256=sha(frozen/'SHA256SUMS'),
    cache_marker_sha256='0185757a4724569359e128a6d829e6a0e524df26e5011e7b2507a08d65d4a9b1',
    head_complete_sha256='fd9b46e510c0937d8c151aa80dd3940a636e8a68e618ec3ef9267a846705fd83',
    head_cache_binding_sha256='0f2f80101f17d461189150cdcc1089b59703ae539612080bf132a4514ce6a96c',
    run='/srv/paper04/runs/onboarding_new_lineage_20261022_v3',state='/srv/paper04/services/onboarding_new_lineage_20261022_v3',
    export='/srv/paper04/exports/onboarding_new_lineage_20261022_v3',unit='paper04-onboarding-20261022-v3')
dump(out/'config.json',cfg)
files={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='code_manifest.json' and '__pycache__' not in p.parts}
dump(out/'code_manifest.json',dict(schema='onboarding-new-lineage-code-v1',files=files))
with tarfile.open(HERE/'onboarding_new_lineage_20261022_v3.tar.gz','w:gz') as tar:
    for name in sorted(files):tar.add(out/name,arcname=name,recursive=False)
    tar.add(out/'code_manifest.json',arcname='code_manifest.json')
dump(HERE/'package_receipt_v3.json',dict(package_sha256=sha(HERE/'onboarding_new_lineage_20261022_v3.tar.gz'),code_manifest_sha256=sha(out/'code_manifest.json'),config_sha256=sha(out/'config.json'),frozen_onboarding_seal_sha256=cfg['onboarding_seal_sha256']))
print(json.dumps(json.loads((HERE/'package_receipt_v3.json').read_text())))
