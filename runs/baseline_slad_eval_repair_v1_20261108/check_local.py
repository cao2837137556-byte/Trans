import ast,json,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'baseline_author_defaults_v1_20261108'
sys.path.insert(0,str(OLD));import formal as f
import numpy as np,torch
torch.set_num_threads(1)
if len(sys.argv)>1:
    folder=Path(sys.argv[2]);f.HERE=folder
    if sys.argv[1]=='fixed':sys.path.insert(0,str(OLD/'vendor/slad'))
    fn=f.predictor('SLAD',27);np.save(folder/'actual.npy',fn(np.load(folder/'x.npy')))
else:
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    with tempfile.TemporaryDirectory() as td:
        folder=Path(td);(folder/'CONFIG.json').write_bytes((OLD/'CONFIG.json').read_bytes());dest=folder/'artifacts/SLAD/27';dest.mkdir(parents=True)
        torch.manual_seed(27);np.random.seed(27);x=np.random.randn(512,790).astype('float32');m,s,loader,opt=f.construct('SLAD',27,x)
        f.one_epoch('SLAD',m,loader,opt,'TEST');f.save(dest/'checkpoint.pt',f.snapshot('SLAD',m,s,opt,100));np.save(folder/'x.npy',x[:32])
        expected=m.decision_function(x[:32])
        r=subprocess.run([sys.executable,'-X','utf8','-B',__file__,'broken',td],capture_output=True,text=True,timeout=60)
        assert r.returncode!=0 and "No module named 'algorithms'" in r.stderr
        subprocess.run([sys.executable,'-X','utf8','-B',__file__,'fixed',td],check=True,timeout=60)
        assert np.array_equal(expected,np.load(folder/'actual.npy'))
    (HERE/'LOCAL_REGRESSION.json').write_text(json.dumps(dict(status='PASS',clean_predictor_failure_reproduced=True,clean_predictor_fix_exact=True,linux_full_checkpoints_pending=True),indent=2))
    print('PASS: clean prediction-only failure reproduced and fixed exactly')
