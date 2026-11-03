"""Upload, submit once, or retrieve one fixed C3 result through VS Code SOCKS."""
import argparse
import hashlib
import http.client
import io
import json
from pathlib import Path
import tarfile
from proxy_existing_tunnel import connect

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / 'history_normal_reference_c3_small_bank_v1_20261101'


def request(action, *, socks_port=None):
    config = json.loads((HERE / '.private/connection.json').read_text())
    port = socks_port or config['socks_port']
    conn = http.client.HTTPConnection('127.0.0.1', 18794, timeout=300)
    conn.sock = connect(port, 18794); conn.sock.settimeout(300)
    method = 'GET' if action in ('state', 'result') else 'POST'
    data = (HERE / 'bundle.tar').read_bytes() if action == 'upload' else b''
    conn.request(method, '/' + config['token'] + '/' + action, body=data)
    response = conn.getresponse(); body = response.read()
    if response.status != 200: raise RuntimeError(body.decode('utf-8', errors='replace'))
    if action != 'result':
        value = json.loads(body)
        (HERE / (action.upper() + '_RECEIPT.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return value
    expected = response.getheader('X-Content-SHA256')
    assert hashlib.sha256(body).hexdigest() == expected
    target = PACKAGE / 'retrieved'; assert not target.exists()
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:') as archive:
        members = archive.getmembers(); names = [m.name for m in members]
        assert len(names) == len(set(names))
        for m in members:
            p = Path(m.name)
            assert m.isfile() and not p.is_absolute() and '..' not in p.parts and '\\' not in m.name
            assert (target / p).resolve().is_relative_to(target.resolve())
            assert p.parts[0] == 'encoded' or (len(p.parts) == 1 and (m.name in ('ENCODE_RUNTIME.json','ENCODE_ATTEMPT.json','ENCODE_GUARD_ATTEMPT.json','ENCODE.log','STATUS.json') or (m.name.startswith('SLURM-') and m.name.endswith('.log'))))
        target.mkdir()
        for m in members:
            p = target / m.name; p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as f: f.write(archive.extractfile(m).read())
    value = dict(status='RETRIEVED', bytes=len(body), bundle_sha256=expected, files=names)
    (HERE / 'RETRIEVAL_RECEIPT.json').write_text(json.dumps(value, indent=2) + '\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['state','upload','preflight','submit','result']); parser.add_argument('--socks-port', type=int)
    args = parser.parse_args(); print(json.dumps(request(args.action, socks_port=args.socks_port), ensure_ascii=False), flush=True)
