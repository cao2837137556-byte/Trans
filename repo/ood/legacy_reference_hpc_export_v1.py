"""Export explicit run evidence, declaring excluded large intermediate caches."""
from pathlib import Path
import argparse,hashlib,json,os,tarfile

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);a=parser.parse_args();root=Path(a.root).resolve()
    output=root/'pullback.tar.gz';assert not output.exists() and not Path(str(output)+'.partial').exists()
    included=[];omitted=[]
    for category in ('runs','logs','submit_claim'):
        folder=root/category
        if not folder.exists():continue
        for p in sorted(folder.rglob('*')):
            if not p.is_file():continue
            assert not p.is_symlink() and p.resolve().is_relative_to(root)
            rel=p.relative_to(root).as_posix()
            large_intermediate=('/features_' in rel or '/plan/' in rel) and p.name not in ('cache.json','status.json','SHA256SUMS','plan.json','recipe.json')
            if large_intermediate:omitted.append(dict(path=rel,bytes=p.stat().st_size,reason='Large intermediate; original per-stage SHA manifests retained'))
            else:included.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
    report=dict(schema='reference-hpc-evidence-export-v1',included=included,omitted=omitted,full_run_seal_verifiable_without_omitted_files=False,inputs_included=False)
    manifest=root/'EXPORT_MANIFEST.json';manifest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    with tarfile.open(str(output)+'.partial','w:gz',compresslevel=1) as archive:
        archive.add(manifest,arcname='EXPORT_MANIFEST.json',recursive=False)
        for r in included:archive.add(root/r['path'],arcname=r['path'],recursive=False)
    os.replace(str(output)+'.partial',output)
    Path(str(output)+'.sha256').write_text(sha(output)+'  '+output.name+'\n',encoding='utf-8')
    print('EVIDENCE_EXPORTED',output,output.stat().st_size)
if __name__=='__main__':main()
