"""Prepare a bounded remote read-only/synthetic check; never call Slurm."""
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    code = '''import pathlib,sys,json,subprocess,os,hashlib,signal
project=pathlib.Path('/public/home/jiangxinwei.zr/work/paper04')
original=project/'runs/dense_reference_matrix_v1_20261027'
repair=project/'runs/dense_reference_launch_repair_v1_20261027'
sys.path.insert(0,str(repair))
import verify_original as v
expected='12bac486285b6cbaa0a58df7c8ded17dc6c1a74d79632f2ff7763e33f4c34300'
result=dict(scope='READ_ONLY_AND_SYNTHETIC_ONLY',scientific_forwards=0,new_submissions=0)
result['original']=v.verify(original,v.ORIGINAL_MANIFEST_SHA,v.ORIGINAL_FILES,ignored=('.private','runtime','local_progress'))
result['overlay']=v.verify(repair,expected,5,'OVERLAY_SHA256SUMS',ignored=('.private','runtime','validation'))
assert v.sha(original/'hpc/run_dense.slurm')==v.ORIGINAL_LAUNCHER_SHA
assert v.sha(original/'.private/APPROVED.json')==v.ORIGINAL_APPROVAL_SHA
subprocess.run(['/bin/bash','-n',str(repair/'run_repair.slurm')],check=True,timeout=10)
result['bash_syntax']='PASS'
env=dict(os.environ,PYTHONPATH=str(project/'environment/vendor_py311_v1'),PAPER04_FROZEN_PACKAGE=str(original),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
test=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(repair),'-p','test_launch_repair.py','-v'],capture_output=True,text=True,timeout=120,env=env)
validation=repair/'validation'
validation.mkdir(exist_ok=True)
(validation/'REMOTE_TESTS.log').write_text(test.stdout+test.stderr)
result['tests_returncode']=test.returncode
result['test_summary']=test.stderr.splitlines()[-5:]
result['tests_log_sha256']=v.sha(validation/'REMOTE_TESTS.log')
result['status']='PASS' if test.returncode==0 else 'TEST_FAILURE'
result['stopped_temporary_helpers']=[]
for pid,script,job in [(3485075,str(project/'runs/dense_reference_deployment_20261027/deploy_bridge.py'),None),(3485360,str(original/'hpc/status_bridge.py'),'179523')]:
    proc=pathlib.Path('/proc')/str(pid)/'cmdline'
    if proc.exists():
        argv=proc.read_bytes().decode().split(chr(0))
        if script in argv and (job is None or job in argv):
            os.kill(pid,signal.SIGTERM)
            result['stopped_temporary_helpers'].append(pid)
(validation/'REMOTE_READONLY_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\\n')
print('DENSE_REPAIR_CHECK_BEGIN'+json.dumps(result)+'DENSE_REPAIR_CHECK_END')
'''
    wrapped = 'import base64;exec(base64.b64decode(' + repr(base64.b64encode(code.encode()).decode()) + '))'
    executable = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B'
    command = executable + " -c '" + wrapped.replace("'", "'\"'\"'") + "'"
    (HERE / 'REPAIR_READONLY_CHECK.command.sh').write_text(command+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='COMMAND_PREPARED',scope='READ_ONLY_AND_SYNTHETIC_ONLY',new_submissions=0)))


if __name__ == '__main__':
    main()
