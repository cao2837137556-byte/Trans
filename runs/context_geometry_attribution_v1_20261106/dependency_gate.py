"""Fail before sbatch if a runtime dependency is missing, changed or escapes root."""
import hashlib
from pathlib import Path
def verify(root,pins):
    root=Path(root).resolve();checked=0
    for rel,wanted in pins.items():
        path=(root/rel).resolve()
        assert path.is_relative_to(root),'DEPENDENCY_PATH_ESCAPE'
        assert path.is_file(),'DEPENDENCY_MISSING:'+rel
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual==wanted,'DEPENDENCY_SHA:'+rel
        checked+=1
    return dict(status='PASS',files_checked=checked,before_sbatch=True)
