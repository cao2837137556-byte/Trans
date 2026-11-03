"""Standard-library delivery/preflight helpers, usable in a clean Linux directory."""
from pathlib import Path
from collections import Counter
import argparse
import ast
import json
import shutil
import tarfile
import tempfile
import legacy_qref_common_v1 as c

REPORT_INPUTS=(
 'runs/legacy_reference_sample_preparation_v1_20260917/finalized/excluded_capture_modes.json',
 'runs/legacy_reference_sample_preparation_v1_20260917/capture_receipts.json')


def coverage(root,pins):
    for p in REPORT_INPUTS:
        c.require(p in pins,'REPORT_DEPENDENCY_UNPINNED')
        c.pin(c.confined(root,p),pins[p])
    excluded=c.read(c.confined(root,REPORT_INPUTS[0]));receipts=c.read(c.confined(root,REPORT_INPUTS[1]))
    c.require(isinstance(receipts,list),'CAPTURE_RECEIPTS_SCHEMA')
    reasons=Counter()
    for item in receipts:reasons.update(item.get('context_reasons',{}))
    return dict(excluded_capture_modes=excluded,preparation_context_exclusions=dict(reasons),supported_protocols=[6,17],
        scope='Historical preparation exclusions, not newly scored packet denominators; no unsupported-protocol detection credit.')


def source_closure(root):
    root=Path(root);folder=root/'repo/ood'
    todo=[p.name for p in folder.glob('legacy_qref_*_v1.py')]+[p.name for p in folder.glob('test_legacy_qref*_v1.py')]
    found=set()
    while todo:
        name=todo.pop()
        if name in found:continue
        p=folder/name;c.require(p.exists(),'SOURCE_DEPENDENCY_MISSING:'+name);found.add(name)
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import):names=[a.name.split('.')[0] for a in node.names]
            if isinstance(node,ast.ImportFrom) and node.module:names=[node.module.split('.')[0]]
            for module in names:
                if (folder/(module+'.py')).exists():todo.append(module+'.py')
    return [folder/name for name in sorted(found)]


def package(root,out,include_inputs=False):
    root=Path(root).resolve();out=Path(out).resolve()
    c.require(not out.exists(),'PACKAGE_EXISTS')
    impl=root/c.IMPLEMENTATION_REL;c.verify(impl)
    pins=c.read(impl/'code_pins.json')
    for p,h in pins.items():c.pin(c.confined(root,p),h)
    with tempfile.TemporaryDirectory(prefix='qref_package_') as tmp:
        target=Path(tmp)
        files=[root/p for p in pins]
        files += [p for p in impl.rglob('*') if p.is_file()]
        files += [root/c.RECIPE_REL,Path(str(root/c.RECIPE_REL)+'.sha256')]
        if include_inputs:
            for p,h in c.read(impl/'input_pins.json').items():
                files.append(c.pin(c.confined(root,p),h))
        for p in sorted(set(files)):
            rel=p.relative_to(root);dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        c.write(target/'DELIVERY.json',dict(status='PREPARED_NOT_AUTHORIZED',include_inputs=include_inputs,
            features_included=False,required_feature_cache=['LEARN.npy','DEV.npy','REFERENCE.npy','*.rows.jsonl.gz','cache.json'],
            recipe_sha256=c.RECIPE_SHA,real_execution_authorized=False,holdout=False))
        c.seal(target);c.verify(target)
        out.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(out,'x:gz',compresslevel=1) as tar:
            for p in sorted(target.rglob('*')):
                if p.is_file():tar.add(p,arcname=p.relative_to(target).as_posix(),recursive=False)
    Path(str(out)+'.sha256').write_text(c.sha(out)+'  '+out.name+'\n',encoding='utf-8')
    return {'path':str(out),'bytes':out.stat().st_size,'sha256':c.sha(out)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True)
    p.add_argument('--include-inputs',action='store_true');a=p.parse_args()
    print(json.dumps(package(a.root,a.out,a.include_inputs),indent=2))


if __name__=='__main__':main()
