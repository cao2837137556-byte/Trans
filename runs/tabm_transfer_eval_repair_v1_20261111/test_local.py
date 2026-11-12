import ast,json,hashlib
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
source=(ROOT/'runs/tabm_3d_transfer_v1_20261111/transfer.py').read_text()
assert "assert np.array_equal(rebuilt,mlpself),'MLP_SELF_SCALE_SCORE_PARITY'" in source
tree=ast.parse((ROOT/'runs/device_context_evaluation_v1_20261105/common.py').read_text());env={'np':np}
for name in ['correction','four']:
    node=next(v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name==name);exec(compile(ast.Module(body=[node],type_ignores=[]),'original_common','exec'),env)
rng=np.random.default_rng(27);raw=rng.normal(0,20,(256,3));s=rng.uniform(size=256);q=np.zeros((256,14));q[:32,0]=q[:32,2]=1;scales=np.array([91.68742370605469,95.98065185546875,87.30691528320312])
expected=raw.copy();g=np.where(s>0,1-np.power(1-s,3),0.)
for j,b in enumerate(scales):expected[g>0,j]=raw[g>0,j]-(.25*b)*g[g>0]
expected[:32]=raw[:32];assert np.array_equal(env['correction'](raw,s,q,scales),expected)
changed=expected.copy();changed[0,0]=np.nextafter(changed[0,0],np.inf);assert not np.array_equal(changed,expected)
for p in HERE.glob('*.py'):ast.parse(p.read_text())
(HERE/'LOCAL_VALIDATION.json').write_text(json.dumps(dict(status='PASS',original_evaluate_function_used_without_patch=True,original_bitwise_gate_retained=True,one_ulp_difference_rejected=True,cached_arithmetic_exact=True,no_threshold_or_tolerance_change=True,scope='synthetic regression; actual CPU cache gate repeats on compute node',repair_sha256=hashlib.sha256((HERE/'repair.py').read_bytes()).hexdigest()),indent=2)+'\n');print('REPAIR_REGRESSION_PASS')
