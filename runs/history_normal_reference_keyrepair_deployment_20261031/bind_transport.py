"""Bind this attempt's transport after building the immutable input inventory."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def main():
    manifest = HERE / 'DELIVERY_INPUTS.json'
    raw = manifest.read_bytes()
    body = json.loads(raw)
    assert body['file_count'] == len(body['files']) > 0
    checksum = hashlib.sha256(raw).hexdigest()
    for name in ('local_client.py', 'remote_receiver.py'):
        path = HERE / 'transport' / name
        value = path.read_text(encoding='utf-8')
        current = re.search(r"^MANIFEST_SHA = '([^']+)'$", value, re.MULTILINE)
        assert current and current.group(1) in ('REPAIR_DELIVERY_MANIFEST_UNBOUND', checksum), 'TRANSPORT_ALREADY_BOUND_DIFFERENTLY'
        value = value[:current.start(1)] + checksum + value[current.end(1):]
        if name == 'remote_receiver.py':
            count = re.search(r'^MANIFEST_COUNT = ([0-9]+)', value, re.MULTILINE)
            assert count and int(count.group(1)) in (0, body['file_count'])
            value = value[:count.start(1)] + str(body['file_count']) + value[count.end(1):]
        path.write_text(value, encoding='utf-8', newline='\n')
    receipt = dict(delivery_inputs_sha256=checksum, file_count=body['file_count'],
                   receiver_port=18788, monitor_port=18787,
                   transport={name: hashlib.sha256((HERE/'transport'/name).read_bytes()).hexdigest()
                              for name in ('local_client.py', 'remote_receiver.py', 'finish_delivery_once.py', 'monitor.py', 'index.html')})
    (HERE/'transport/TRANSPORT_MANIFEST.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
