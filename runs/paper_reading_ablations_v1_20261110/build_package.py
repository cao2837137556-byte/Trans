"""Local only: no network, no scheduler and no large data in the ZIP."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
FILES=['.gitattributes','analysis_core.py','run.py','test_local.py','run.slurm','README.md','build_package.py','METHOD_FREEZE.json','BASE_EXPECTED_METRICS.json','INPUT_PINS.json','LOCAL_VALIDATION.json']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    test=json.loads((HERE/'LOCAL_VALIDATION.json').read_text());assert test['status']=='PASS'
    for n,h in test['source_hashes'].items():assert sha(HERE/n)==h,'STALE_LOCAL_VALIDATION'
    pins={n:sha(HERE/n) for n in FILES};revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip()
    manifest=dict(status='LOCAL_PREPARED_NOT_SUBMITTED',source_base_commit=revision,payload_identity='exact file SHA256; final source commit in repository history',files=pins,configurations=['BASE','GUARD_OFF','P1','P2','P4'],real_cache_validation='NOT_RUN',remote_submission=False,large_files_included=False)
    (HERE/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    target=HERE.parent/(HERE.name+'.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for n in FILES+['PACKAGE_MANIFEST.json']:z.write(HERE/n,HERE.name+'/'+n)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for n,h in pins.items():assert hashlib.sha256(z.read(HERE.name+'/'+n)).hexdigest()==h
    receipt=dict(status='LOCAL_PACKAGE_PASS_NOT_RUN',archive=target.name,bytes=target.stat().st_size,sha256=sha(target),members=len(FILES)+1,source_base_commit=revision,real_data_checked=False,submitted=False)
    (HERE/'PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    target.with_suffix('.zip.sha256').write_text(receipt['sha256']+'  '+target.name+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
