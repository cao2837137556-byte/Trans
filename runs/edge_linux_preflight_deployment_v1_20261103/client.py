"""Bounded file transfer through the user's existing VS Code SOCKS tunnel.

This module never starts or authenticates an SSH connection. The private token
stays in a local ignored file and is never written to progress or exceptions.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path, PurePosixPath
import socket
import struct
import tarfile
import time
import uuid

HERE = Path(__file__).resolve().parent
MAX_CHUNK = 4 * 1024**2
MAX_RESULT = 128 * 1024**2
KEYS = ('archive', 'NORMAL', 'HTTP', 'UDP')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for payload in iter(lambda: stream.read(MAX_CHUNK), b''):
            digest.update(payload)
    return digest.hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def exact(sock, count):
    chunks = []
    left = count
    while left:
        chunk = sock.recv(left)
        if not chunk:
            raise ConnectionError('EXISTING_TUNNEL_CLOSED')
        chunks.append(chunk)
        left -= len(chunk)
    return b''.join(chunks)


def connect(config, timeout):
    """Connect only to the already established local SOCKS listener."""
    port = int(config['socks_port'])
    destination = int(config.get('remote_port', 18817))
    need(1 <= port <= 65535 and 1 <= destination <= 65535, 'PORT_RANGE')
    sock = socket.create_connection(('127.0.0.1', port), timeout=timeout)
    try:
        sock.sendall(b'\x05\x01\x00')
        need(exact(sock, 2) == b'\x05\x00', 'EXISTING_SOCKS_PROTOCOL')
        sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01' + struct.pack('!H', destination))
        reply = exact(sock, 4)
        if reply[:3] != b'\x05\x00\x00':
            raise ConnectionError('REMOTE_RECEIVER_NOT_REACHABLE')
        need(reply[3] in (1, 3, 4), 'SOCKS_ADDRESS_TYPE')
        count = 4 if reply[3] == 1 else 16 if reply[3] == 4 else exact(sock, 1)[0]
        exact(sock, count)
        exact(sock, 2)
        return sock
    except BaseException:
        sock.close()
        raise


def request(route, body=b'', headers=None, *, timeout=30):
    need(route in ('state', 'prepare', 'submit', 'results')
         or route in tuple('upload/' + key for key in KEYS), 'ACTION_NOT_ALLOWED')
    config = read(HERE / '.private/connection.json')
    token = config['token']
    need(isinstance(token, str) and len(token) >= 32 and token.isalnum(), 'PRIVATE_TOKEN_SCHEMA')
    timeout = max(.1, min(float(timeout), 900))
    connection = http.client.HTTPConnection('127.0.0.1', int(config.get('remote_port', 18817)), timeout=timeout)
    connection.sock = connect(config, timeout)
    connection.sock.settimeout(timeout)
    try:
        connection.request('GET' if route in ('state', 'results') else 'POST',
                           '/' + token + '/' + route, body=body, headers=headers or {})
        response = connection.getresponse()
        if response.status != 200:
            # No remote text or request URL is copied into logs: either could
            # include transport credentials. Safe status is enough to diagnose.
            response.read(4096)
            raise ValueError('REMOTE_ACTION_HTTP_%s:%s' % (response.status, route))
        if route == 'results':
            return connection, response
        value = json.loads(response.read())
        connection.close()
        return value
    except BaseException:
        connection.close()
        raise


def file_specs():
    value = read(HERE / 'DELIVERY.json')['files']
    need(set(value) == set(KEYS), 'DELIVERY_FOUR_PINNED_FILES')
    for key, item in value.items():
        need(type(item['bytes']) is int and item['bytes'] > 0
             and isinstance(item['sha256'], str) and len(item['sha256']) == 64,
             'DELIVERY_FILE_PIN:' + key)
    return value


def validate_local_files(progress=lambda *args, **kwargs: None):
    specs = file_specs()
    for key, spec in specs.items():
        path = Path(spec['path'])
        progress('LOCAL_PIN_CHECK', file=key)
        need(path.is_file() and path.stat().st_size == spec['bytes']
             and sha(path) == spec['sha256'], 'LOCAL_FILE_PIN:' + key)
    return specs


def remote_file(state, key, spec):
    item = state['files'][key]
    need(item['bytes'] == spec['bytes'] and item['sha256'] == spec['sha256'],
         'REMOTE_FILE_IDENTITY:' + key)
    need(type(item['offset']) is int and 0 <= item['offset'] <= spec['bytes'], 'REMOTE_OFFSET:' + key)
    need(not item.get('complete') or item['offset'] == spec['bytes'], 'REMOTE_COMPLETE_OFFSET:' + key)
    return item


def upload_files(specs, progress=lambda *args, **kwargs: None, *, action=request):
    state = action('state')
    total = sum(v['bytes'] for v in specs.values())
    initial = sum(remote_file(state, key, spec)['offset'] for key, spec in specs.items())
    started = time.monotonic()
    for key in KEYS:
        spec = specs[key]
        current = remote_file(state, key, spec)
        failures = 0
        with Path(spec['path']).open('rb') as stream:
            while not current.get('complete'):
                offset = current['offset']
                need(offset < spec['bytes'], 'FULL_FILE_NOT_VERIFIED:' + key)
                stream.seek(offset)
                payload = stream.read(min(MAX_CHUNK, spec['bytes'] - offset))
                try:
                    value = action('upload/' + key, payload,
                                   {'X-Offset': str(offset),
                                    'X-Chunk-SHA256': hashlib.sha256(payload).hexdigest()}, timeout=90)
                    # Receiver can return the file entry or a complete state.
                    current = remote_file(value, key, spec) if 'files' in value else remote_file({'files': {key: value}}, key, spec)
                    failures = 0
                except (OSError, http.client.HTTPException):
                    failures += 1
                    need(failures <= 3, 'TRANSFER_RETRY_LIMIT:' + key)
                    state = action('state')
                    current = remote_file(state, key, spec)
                state['files'][key] = current
                done = sum(remote_file(state, k, s)['offset'] for k, s in specs.items())
                progress('UPLOADING', file=key, file_done_bytes=current['offset'],
                         file_total_bytes=spec['bytes'], done_bytes=done, total_bytes=total,
                         bytes_per_second=max(0, done-initial) / max(.001, time.monotonic()-started))
    return state


def safe_members(archive):
    members = archive.getmembers()
    names = [m.name for m in members]
    need(len(names) == len(set(names)), 'RESULT_DUPLICATE_PATH')
    need(sum(m.size for m in members) <= MAX_RESULT, 'RESULT_EXPANDED_LIMIT')
    for member in members:
        path = PurePosixPath(member.name)
        need(member.isfile() or member.isdir(), 'RESULT_REGULAR_FILE_OR_DIRECTORY_ONLY')
        need(member.name and '\\' not in member.name and not path.is_absolute()
             and '..' not in path.parts and ':' not in member.name, 'RESULT_PATH_ESCAPE')
        need(path.suffix.lower() not in ('.pcap', '.pcapng', '.sqlite', '.db'), 'RESULT_NO_RAW_OR_DATABASE')
    return members


def validate_result_directory(folder):
    folder = Path(folder)
    manifests = list(folder.rglob('RESULT_MANIFEST.json'))
    if manifests:
        need(len(manifests) == 1, 'RESULT_MANIFEST_UNIQUE')
        manifest = read(manifests[0])
        base = manifests[0].parent
        items = manifest.get('files', manifest)
        for name, pin in items.items():
            if not isinstance(pin, dict) or 'sha256' not in pin:
                continue
            target = (base / name).resolve()
            need(target.is_relative_to(base.resolve()) and target.is_file(), 'RESULT_MANIFEST_SCOPE')
            need(sha(target) == pin['sha256'] and ('bytes' not in pin or target.stat().st_size == pin['bytes']),
                 'RESULT_MEMBER_PIN:' + name)
    deliveries = list(folder.rglob('DELIVERY_RESULT.json'))
    if len(deliveries) != 1:
        # A scheduler kill can leave valid logs without the final worker file.
        # Save those bytes as failure evidence; never infer PASS from Slurm.
        return dict(linux_actual_preflight_pass=False,
                    delivery_status='MISSING_FINAL_RECEIPT' if not deliveries else 'AMBIGUOUS_FINAL_RECEIPTS',
                    real_slice_status=None, strict_shape_probe_status=None,
                    formal_external_evaluation_started=False, full_execution_ready=False)
    delivery = read(deliveries[0])
    real = deliveries[0].parent / 'real_slice/RESULT.json'
    probe = deliveries[0].parent / 'real_slice/STRICT_SHAPE_PROBE_SUMMARY.json'
    actual = read(real) if real.is_file() else {}
    probes = read(probe) if probe.is_file() else {}
    passed = (delivery.get('status') == 'LINUX_PREFLIGHT_PASS'
              and actual.get('status') == 'SAME_RUNTIME_REAL_SLICE_E2E_PASS'
              and actual.get('final_linux_runtime_gate_pass') is True
              and probes.get('status') == 'PASS')
    return dict(linux_actual_preflight_pass=passed,
                delivery_status=delivery.get('status'),
                real_slice_status=actual.get('status'), strict_shape_probe_status=probes.get('status'),
                formal_external_evaluation_started=False, full_execution_ready=False)


def retrieve_results(progress=lambda *args, **kwargs: None, *, action=request):
    final = HERE / 'retrieved'
    if final.exists():
        return validate_result_directory(final)
    archive_path = HERE / 'results.tar'
    if not archive_path.exists():
        connection, response = action('results', timeout=90)
        temporary = HERE / 'results.part'
        try:
            size = int(response.getheader('X-Content-Total-Bytes'))
            expected = response.getheader('X-Content-SHA256')
            need(0 < size <= MAX_RESULT and len(expected or '') == 64, 'RESULT_TRANSFER_HEADER')
            need(int(response.getheader('Content-Length')) == size, 'RESULT_CONTENT_LENGTH')
            written = 0
            with temporary.open('wb') as stream:
                while written < size:
                    payload = response.read(min(MAX_CHUNK, size-written))
                    need(bool(payload), 'RESULT_EARLY_EOF')
                    stream.write(payload)
                    written += len(payload)
                    progress('RETRIEVING', done_bytes=written, total_bytes=size)
            need(sha(temporary) == expected, 'RESULT_TRANSFER_SHA')
            temporary.replace(archive_path)
            write(HERE / 'RESULT_TRANSFER_RECEIPT.json', dict(bytes=size, sha256=expected, verified=True))
        finally:
            connection.close()
    binding = read(HERE / 'RESULT_TRANSFER_RECEIPT.json')
    need(archive_path.stat().st_size == binding['bytes'] and sha(archive_path) == binding['sha256'],
         'SAVED_RESULT_TRANSFER_PIN')
    staging = HERE / ('retrieved.partial_' + uuid.uuid4().hex[:10])
    staging.mkdir(exist_ok=False)
    with tarfile.open(archive_path, 'r:') as archive:
        for member in safe_members(archive):
            target = staging / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('xb') as out:
                    for payload in iter(lambda: source.read(MAX_CHUNK), b''):
                        out.write(payload)
    receipt = validate_result_directory(staging)
    staging.rename(final)
    write(HERE / 'RETRIEVAL_RECEIPT.json', dict(receipt, retrieved_utc=utc(),
                                               archive_sha256=binding['sha256']))
    return receipt
