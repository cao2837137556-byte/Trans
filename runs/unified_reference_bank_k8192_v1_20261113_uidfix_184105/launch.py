"""Release one formal replay only after 184105's recovered inputs pass preflight."""
import getpass
import sys
import traceback
from pathlib import Path

import dispatch as d
from frozen_selector import need
from runtime_support import asset,digest,read,write

BASE = 'unified_reference_bank_k8192_v1_20261113'
PARENT = BASE+'_early_183987'
RUN = BASE+'_uidfix_184105'
HISTORY = {'183971':('FAILED','1:0'), '183987':('TIMEOUT','0:0'), '184105':('FAILED','1:0')}


def gate(project,out,preparation=None):
    root = project/'runs'
    squeue = d.checked(['squeue','-h','-u',getpass.getuser(),'-o','%i|%j|%T']).splitlines()
    sacct = d.checked(['sacct','-n','-P','-X','-u',getpass.getuser(),'-S','2026-11-11',
        '-o','JobIDRaw,JobName%100,State%32,ExitCode']).splitlines()
    def matching(lines):
        return [x.split('|') for x in lines if len(x.split('|'))>=3 and
                ('k8192' in x.split('|')[1].lower() or 'p04-unified' in x.split('|')[1].lower())]
    history = dict(HISTORY)
    if preparation is not None:
        history[preparation]=('COMPLETED','0:0')
    records = matching(sacct)
    need(not matching(squeue) and len(records)==len(history) and
         {row[0]:(row[2],row[3]) for row in records}==history and
         all(row[1]=='p04-k8192-prepare' for row in records),'K8192_JOB_RECONCILIATION')
    for folder in (root/BASE,root/(BASE+'_repair_183971'),root/(BASE+'_resume_183987'),root/PARENT,out):
        marker = folder/'SUBMIT_INTENT_replay.json'
        if marker.is_file():
            expected = d.hold_payload(root/PARENT,'183987','replay')
            need(folder.name==BASE+'_repair_183971' and read(marker)==expected,'EXISTING_FORMAL_INTENT')
        need(all(not (folder/name).exists() for name in d.FORMAL_MARKERS[1:]),
             'EXISTING_FORMAL_RECEIPT:'+folder.name)
    failure = root/PARENT/'FAILURE_prepare.json'
    pin = read(root/PARENT/'RETURN.json')['files'][failure.name]
    need(asset(failure)==pin and read(failure)['error']=='QUERY_CONTEXT_UID_BINDING',
         '184105_FAILURE_IDENTITY')
    write(out/('DUPLICATE_REPLAY_GATE.json' if preparation else 'DUPLICATE_RECOVERY_GATE.json'),
          dict(status='PASS',previous_jobs=history,active_jobs=0,formal_runs=0))


def pullback(out):
    d.seal_results(out)
    manifest = read(out/'RETURN.json')
    for name in ('REUSED_184105.json','DUPLICATE_RECOVERY_GATE.json','DUPLICATE_REPLAY_GATE.json'):
        if (out/name).is_file():
            manifest['files'][name]=asset(out/name)
    write(out/'RETURN.json',manifest)


def main():
    project,out=map(Path,sys.argv[1:])
    archive=project/'runs/.unified_reference_bank_k8192_v1_20261113_motion_ingress/motion.pcap.gz'
    try:
        need(out.name==RUN,'RECOVERY_RUN_SCOPE')
        d.state(out,'CHECKPOINT_ADMISSION')
        gate(project,out)
        prep=d.submit(out,project,archive,'prepare',12288,7200)
        result=d.wait(out,'prepare',prep,7200)
        need(result['status']=='READY_FOR_ONE_PAIRED_REPLAY' and
             read(out/'PREFLIGHT.json')['status']=='PASS' and
             all(result[key]['sha256']==digest(path) for key,path in (
                 ('preflight',out/'PREFLIGHT.json'),('sizing',out/'FORMAL_SIZING.json'),
                 ('candidate',out/'candidate/CANDIDATE.json'))),'RECOVERY_PREFLIGHT_GATE')
        candidate=read(out/'candidate/CANDIDATE.json')
        write(out/'CANDIDATE_SHA.json',dict(receipt=result['candidate'],
            sources=read(out/'candidate/SELECTION.json'),features=candidate['pools']))
        sizing=read(out/'FORMAL_SIZING.json')
        wall=sizing['planned_wall_seconds']
        need(sizing['status']=='PASS' and type(wall) is int and 3600<=wall<=21600 and
             sizing['memory_mib']==12288,'FORMAL_RESOURCE_PLAN')
        gate(project,out,preparation=prep)
        replay=d.submit(out,project,archive,'replay',sizing['memory_mib'],wall)
        result=d.wait(out,'replay',replay,wall)
        a=read(out/'ACCEPTANCE.json')
        need(result['status']=='FORMAL_REPLAY_COMPLETE' and
             result['acceptance']['sha256']==digest(out/'ACCEPTANCE.json') and
             a['formal_replays']==1 and a['status']==result['outcome'],'FINAL_ACCEPTANCE')
        (out/'RESULTS_FOR_PAPER.md').write_text(
            '# K8192 统一建库配对重放\n\n结果为 '+a['status']+'。'
            '\n\n[集成结果](RESULT_INDEX.json) · [全部指标](METRICS.csv) · '
            '[配对变化](PAIRED.csv) · [逐门验收](ZERO_DEGRADATION.csv)\n',encoding='utf-8')
        d.state(out,'COMPLETE',phase='replay',job_id=replay,outcome=a['status'])
    except Exception as e:
        write(out/'CONTROLLER_FAILURE.json',dict(status='ENGINEERING_STOP',
                error=str(e),traceback=traceback.format_exc()))
        d.state(out,'STOP',error=str(e))
        raise
    finally:
        pullback(out)


if __name__=='__main__':
    main()
