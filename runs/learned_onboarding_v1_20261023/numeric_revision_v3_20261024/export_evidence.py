"""Export only the small validation evidence; no models or original outputs."""
import hashlib
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parent
names=['VALIDATION_RECEIPT.json','SOURCE_IDENTITY_SUPPLEMENT.json',
       'original_tests.log','numeric_tests.log','source_forward.log',
       'source_validation/AUX_G0.json','source_validation/AUX_G1.json',
       'source_validation/SOURCE_VALIDATION.json']
files={name:dict(sha256=hashlib.sha256((root/name).read_bytes()).hexdigest(),
                 bytes=(root/name).stat().st_size) for name in names}
manifest=root/'EVIDENCE_MANIFEST.json'
with manifest.open('x') as stream:
    json.dump(dict(schema='paper04-numeric-revision-evidence-v3',files=files),stream,indent=2)
with tarfile.open(root/'validation_evidence.tar.gz','x:gz') as archive:
    for name in names+['EVIDENCE_MANIFEST.json']:
        archive.add(root/name,arcname=name)
path=root/'validation_evidence.tar.gz'
print(json.dumps(dict(archive_bytes=path.stat().st_size,
    archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())))
