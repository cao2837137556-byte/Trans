"""Retrieve exactly the pinned saved inputs via the existing VS Code tunnel."""
import hashlib
import http.client
import json
from pathlib import Path
import socket
import struct
import tarfile

HERE = Path(__file__).resolve().parent
LIMIT = 512 * 1024**2


def exact(sock, count):
    data = b''
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise ConnectionError('incomplete SOCKS response')
        data += part
    return data


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def main():
    config = json.loads((HERE / '.private/transfer.json').read_text('utf-8'))
    request = json.loads((HERE / 'EXPORT_REQUEST.json').read_text('utf-8'))
    expected = {r['local_relative_path']: r for r in request['files']}
    assert len(expected) == len(request['files']) == 14
    assert not (HERE / 'retrieved').exists()
    sock = socket.create_connection(('127.0.0.1', config['socks_candidates'][0]), timeout=12)
    sock.sendall(b'\x05\x01\x00')
    assert exact(sock, 2) == b'\x05\x00'
    sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01' + struct.pack('!H', config['port']))
    head = exact(sock, 4)
    assert head[:3] == b'\x05\x00\x00'
    exact(sock, 4 if head[3] == 1 else 16 if head[3] == 4 else exact(sock, 1)[0])
    exact(sock, 2)
    sock.settimeout(60)
    conn = http.client.HTTPConnection('127.0.0.1', config['port'], timeout=60)
    conn.sock = sock
    conn.request('GET', '/' + config['token'] + '/bundle.tar', headers={'Connection': 'close'})
    response = conn.getresponse()
    assert response.status == 200
    total = int(response.getheader('Content-Length'))
    bundle_sha = response.getheader('X-Content-SHA256')
    assert 0 < total < LIMIT and len(bundle_sha) == 64
    part = HERE / 'bundle.tar.part'
    done = 0
    with part.open('xb') as stream:
        while True:
            chunk = response.read(4 * 1024**2)
            if not chunk:
                break
            done += len(chunk)
            assert done <= total
            stream.write(chunk)
            print('C2_TRANSFER ' + str(done) + '/' + str(total), flush=True)
    conn.close()
    assert done == total and sha(part) == bundle_sha
    final = HERE / 'bundle.tar'
    part.rename(final)
    with tarfile.open(final) as archive:
        members = archive.getmembers()
        assert len(members) == len(expected) + 1
        assert {m.name for m in members} == set(expected) | {'REMOTE_INPUT_INVENTORY.json'}
        inventory = json.load(archive.extractfile('REMOTE_INPUT_INVENTORY.json'))
        assert inventory['schema'] == request['schema']
        remote = {r['local_relative_path']: r for r in inventory['files']}
        assert set(remote) == set(expected)
        for name, item in expected.items():
            assert remote[name]['sha256'] == item['sha256']
            assert remote[name]['remote_relative_path'] == item['remote_relative_path']
        output = HERE / 'retrieved'
        output.mkdir()
        for member in members:
            destination = (output / member.name).resolve()
            assert member.isfile() and destination.is_relative_to(output.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, destination.open('xb') as target:
                while True:
                    chunk = source.read(4 * 1024**2)
                    if not chunk:
                        break
                    target.write(chunk)
            if member.name in expected:
                assert destination.stat().st_size == remote[member.name]['bytes']
                assert sha(destination) == expected[member.name]['sha256']
    receipt = dict(status='ALL_REMOTE_PINS_VERIFIED', arrays=7, files=14, bytes=total,
                   bundle_sha256=bundle_sha, export_request_sha256=sha(HERE / 'EXPORT_REQUEST.json'),
                   new_model_forwards=0, new_distances=0, new_raw_data_downloads=0)
    (HERE / 'RETRIEVAL_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
