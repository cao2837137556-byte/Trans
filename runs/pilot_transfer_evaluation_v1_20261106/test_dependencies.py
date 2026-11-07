import hashlib,json,tempfile
from pathlib import Path
import dependency_gate as d
def main():
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/'runtime.py').write_bytes(b'pass\n');h=hashlib.sha256(b'pass\n').hexdigest()
        assert d.verify(p,{'runtime.py':h})['files_checked']==1
        for pins,expected in [({'audit_completion.py':h},'DEPENDENCY_MISSING'),({'runtime.py':'0'*64},'DEPENDENCY_SHA'),({'../outside.py':h},'DEPENDENCY_PATH_ESCAPE')]:
            try:d.verify(p,pins)
            except AssertionError as e:assert str(e).startswith(expected)
            else:raise AssertionError('INVALID_DEPENDENCY_ACCEPTED')
    result=dict(status='PASS',tests=['valid_pin_passes','local_only_missing_fails_before_submit','wrong_sha_fails','path_escape_fails'])
    Path(__file__).with_name('DEPENDENCY_REGRESSION.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
