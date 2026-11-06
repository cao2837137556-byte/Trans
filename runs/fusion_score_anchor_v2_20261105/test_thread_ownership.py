"""Real PyTorch subprocess regression for duplicate interop initialization."""
import json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main(output='THREAD_REGRESSION.json'):
    cases={}
    for case in ['old_duplicate_rejected','decode_owner_pass','training_owner_pass']:
        code="import torch,worker\ncase="+repr(case)+"\n"
        code+="worker.configure_threads('DECODE_PREFLIGHT' if case=='decode_owner_pass' else 'TRAIN_27')\ntorch.nn.Linear(4,4)(torch.ones(2,4))\n"
        if case=='old_duplicate_rejected':
            code+="try:\n torch.set_num_interop_threads(1)\nexcept RuntimeError as e:\n assert 'cannot set number of interop threads' in str(e)\n print('REJECTED_EXPECTED')\nelse:raise AssertionError('NEGATIVE_CONTROL_DID_NOT_FAIL')\n"
        elif case=='decode_owner_pass':code+="torch.set_num_interop_threads(1)\nassert torch.get_num_threads()==torch.get_num_interop_threads()==1\nprint('PASS')\n"
        else:code+="assert torch.get_num_threads()==torch.get_num_interop_threads()==1\nprint('PASS')\n"
        env=dict(os.environ,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        cp=subprocess.run([sys.executable,'-X','utf8','-B','-c',code],cwd=HERE,env=env,capture_output=True,text=True,timeout=90)
        assert cp.returncode==0,case+':'+cp.stderr[-2000:]
        assert cp.stdout.strip()==('REJECTED_EXPECTED' if case=='old_duplicate_rejected' else 'PASS')
        cases[case]=cp.stdout.strip()
    result=dict(status='PASS',cases=cases,scope='REAL_TORCH_INITIALIZATION_NOT_ENCODER_PARITY')
    (HERE/output).write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
if __name__=='__main__':main()
