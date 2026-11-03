"""Prepare a fixed, additive repair upload; never submit a scientific job."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

HERE = Path(__file__).resolve().parent
REPAIR = HERE.parents[1] / 'dense_reference_launch_repair_v1_20261027'
REMOTE = '/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_launch_repair_v1_20261027'


def main():
    manifest = REPAIR / 'OVERLAY_SHA256SUMS'
    raw = manifest.read_bytes()
    members = {'OVERLAY_SHA256SUMS': base64.b64encode(raw).decode()}
    for line in raw.decode().splitlines():
        digest, name = line.split('  ', 1)
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('Invalid fixed repair member')
        data = (REPAIR / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Repair SHA mismatch: ' + name)
        members[name] = base64.b64encode(data).decode()
    packed = zlib.compress(json.dumps(members, sort_keys=True).encode(), 9)
    encoded = base64.b64encode(packed).decode()
    code = f'''import base64,zlib,json,pathlib,hashlib
root=pathlib.Path({REMOTE!r})
assert not root.exists(), 'NEW_REPAIR_DIRECTORY_REQUIRED'
members=json.loads(zlib.decompress(base64.b64decode({encoded!r})))
assert all(not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts and chr(92) not in n for n in members)
assert hashlib.sha256(base64.b64decode(members['OVERLAY_SHA256SUMS'])).hexdigest()=={hashlib.sha256(raw).hexdigest()!r}
root.mkdir()
for name,encoded_data in members.items():
    destination=root/name
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(base64.b64decode(encoded_data))
(root/'runtime').mkdir()
(root/'.private').mkdir(mode=448)
print('DENSE_REPAIR_UPLOAD_OK '+json.dumps(dict(files=len(members),overlay_sha256={hashlib.sha256(raw).hexdigest()!r},submitted=False)))
'''
    # Keep the UI transport a single shell input line.
    wrapped = "import base64;exec(base64.b64decode(" + repr(base64.b64encode(code.encode()).decode()) + "))"
    command = "python3 -c '" + wrapped.replace("'", "'\"'\"'") + "'"
    output = HERE / 'REPAIR_UPLOAD.command.sh'
    output.write_text(command + '\n', encoding='utf-8', newline='\n')
    receipt = dict(status='COMMAND_PREPARED_NO_REMOTE_ACTION', files=len(members),
                   overlay_sha256=hashlib.sha256(raw).hexdigest(), remote_directory=REMOTE,
                   automatic_submit=False, command_file=str(output))
    (HERE / 'REPAIR_UPLOAD_PREPARED.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
