"""Seal this independent deliverable, never modify the inherited package."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent / 'package'
files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
         and p.name != 'code_manifest.json' and 'extra_deps' not in p.parts
         and p.name != 'dependency_install_receipt.json'}
(root / 'code_manifest.json').write_text(json.dumps(dict(schema='modern-new-lineage-package-v1', files=files),
    indent=2) + '\n', encoding='utf-8')
print(hashlib.sha256((root / 'code_manifest.json').read_bytes()).hexdigest())
