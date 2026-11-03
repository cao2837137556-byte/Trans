"""Resume after capinfos all-info timeout, reusing verified extraction."""
import audit as a
import importlib.util
import subprocess
from pathlib import Path

receipt=a.read(a.HERE/'NETATMO_EXTRACTION.json');spec=receipt['member'];path=Path(spec['path'])
assert a.sha(path)==spec['sha256']
command=['C:/Program Files/Wireshark/capinfos.exe','-t','-E','-I','-c','-a','-e','-M','-S',str(path)]
run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',check=True,timeout=300)
out=a.HERE/(path.stem+'.capinfos.txt')
with out.open('x',encoding='utf-8') as f:f.write(run.stdout)
print(run.stdout,flush=True)
src=a.pin(a.ROOT/'runs/targeted_normal_raw_qualification_v1_20261031/qualify_raw.py')
ms=importlib.util.spec_from_file_location('raw_qualification_reuse',src)
module=importlib.util.module_from_spec(ms);ms.loader.exec_module(module);module.RUN=a.HERE
stats=module.scan(spec)
assert stats['counts']['owner_present_packets']==stats['counts']['packets']
assert stats['counts'].get('packets_at_or_after_2018_01_01',0)==0
assert a.sha(path)==spec['sha256']
a.write('NETATMO_RAW_ACCEPTANCE.json',dict(status='STRUCTURAL_METADATA_PASS_REFERENCE_ADMISSION_PENDING',
    member=spec,independent_checks=stats['independent_checks'],all_packets_owner_present=True,all_packets_before_2018=True,
    normality='Publisher normal-source assumption, no packet-level benign certification',
    statistics_sha256=a.sha(a.HERE/(path.stem+'.raw_stats.json')),qualification_code_sha256=a.sha(src),
    new_features=0,new_references=0,new_experiments=0,
    engineering_recovery='All-info capinfos exceeded 120s; resumed metadata-only capinfos on same verified member, no re-extraction.',
    script_sha256=a.sha(__file__)))
print('NETATMO_RAW_ACCEPTED_FOR_DESIGN',flush=True)
