"""Ordinary hidden-client sync with bounded lifetime and SSH-port recovery."""
import argparse
import http.client
import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading
import time

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import read, require, write
from status_bridge import reconcile


def exact(sock, count):
    value = bytearray()
    while len(value) < count:
        chunk = sock.recv(count - len(value))
        if not chunk:
            raise ConnectionError('SOCKS_CLOSED')
        value.extend(chunk)
    return bytes(value)


class Connection(http.client.HTTPConnection):
    def __init__(self, remote_port, socks_port):
        super().__init__('127.0.0.1', remote_port, timeout=15)
        self.socks_port = socks_port

    def connect(self):
        self.sock = socket.create_connection(('127.0.0.1', self.socks_port), timeout=15)
        self.sock.sendall(b'\x05\x01\x00')
        require(exact(self.sock, 2) == b'\x05\x00', 'SOCKS_AUTH')
        self.sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01' + struct.pack('!H', self.port))
        reply = exact(self.sock, 4)
        require(reply[:3] == b'\x05\x00\x00', 'SOCKS_REMOTE_UNAVAILABLE')
        length = {1: 4, 4: 16}.get(reply[3])
        if reply[3] == 3:
            length = exact(self.sock, 1)[0]
        require(length is not None, 'SOCKS_ADDRESS')
        exact(self.sock, length + 2)


def existing_port():
    """Use only a unique, already authenticated school-hpc SSH listener."""
    candidates = []
    for process in psutil.process_iter(['name', 'cmdline', 'pid']):
        try:
            command = process.info['cmdline'] or []
            if (process.info['name'] or '').lower() not in ('ssh', 'ssh.exe'):
                continue
            if 'school-hpc' not in command or not command or command[-1] != 'bash':
                continue
            ports = []
            for i, part in enumerate(command):
                if part == '-D' and i + 1 < len(command):
                    ports.append(command[i + 1])
                elif part.startswith('-D') and len(part) > 2:
                    ports.append(part[2:])
            if len(ports) != 1:
                continue
            value = ports[0]
            if ':' in value:
                host, value = value.rsplit(':', 1)
                if host != '127.0.0.1':
                    continue
            if value.isdecimal() and 0 < int(value) < 65536:
                candidates.append((process.pid, int(value)))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    try:
        listeners = {(c.pid, c.laddr.port) for c in psutil.net_connections('tcp')
                     if c.status == psutil.CONN_LISTEN and c.laddr.ip == '127.0.0.1'}
    except psutil.AccessDenied:
        return None
    candidates = [c for c in candidates if c in listeners]
    return candidates[0][1] if len(candidates) == 1 else None


def validate_bundle(value, job_id):
    if not (isinstance(value, dict) and value.get('schema') == 'paper04-dense-progress-bundle-v1'
            and value.get('job_id') == job_id and value.get('read_only') is True):
        raise ValueError('REMOTE_IDENTITY_MISMATCH')
    if set(value) != {'schema', 'job_id', 'observed_utc', 'progress', 'scheduler',
                      'read_only', 'automatic_retry'}:
        raise ValueError('BUNDLE_FIELDS')
    if not (isinstance(value['progress'], dict) and isinstance(value['scheduler'], dict)
            and value['scheduler'].get('job_id') == job_id):
        raise ValueError('SCHEDULER_BINDING')
    if value.get('automatic_retry') is not False:
        raise ValueError('REMOTE_RETRY_POLICY')
    try:
        from datetime import datetime
        stamp = datetime.fromisoformat(value['observed_utc'])
        if stamp.tzinfo is None:
            raise ValueError('BUNDLE_TIMESTAMP_TIMEZONE')
    except (TypeError, KeyError) as exc:
        raise ValueError('BUNDLE_TIMESTAMP') from exc
    return dict(value, progress=reconcile(value['progress'], value['scheduler']))


def fetch(config):
    connection = Connection(config['remote_port'], config['socks_port'])
    def abort():
        if connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()
    timer = threading.Timer(15, abort)
    timer.daemon = True
    timer.start()
    try:
        connection.request('GET', '/status/job_' + config['job_id'],
                           headers={'Authorization': 'Bearer ' + config['token']})
        response = connection.getresponse()
        if 400 <= response.status < 500:
            raise ValueError('HTTP_IDENTITY_OR_EXPIRED:' + str(response.status))
        if response.status != 200:
            raise ConnectionError('HTTP_TRANSPORT:' + str(response.status))
        length = int(response.getheader('Content-Length', '-1'))
        if not 0 <= length <= 1024**2:
            raise ValueError('BUNDLE_SIZE')
        payload = response.read(length + 1)
        if len(payload) != length:
            raise ValueError('BUNDLE_TRUNCATED')
        return validate_bundle(json.loads(payload), config['job_id'])
    finally:
        timer.cancel()
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-config', required=True)
    parser.add_argument('--cache', required=True)
    args = parser.parse_args()
    config = read(args.private_config)
    require('.private' in Path(args.private_config).parts, 'PRIVATE_CONFIG_PATH')
    require(isinstance(config.get('token'), str) and len(config['token']) >= 32, 'PRIVATE_TOKEN')
    require(str(config.get('job_id', '')).isdecimal(), 'JOB_ID')
    config['job_id'] = str(config['job_id'])
    require(int(config['job_id']) > 0, 'JOB_ID')
    for field in ('remote_port', 'socks_port'):
        require(type(config.get(field)) is int and 0 < config[field] < 65536, 'PRIVATE_PORT')
    cache = Path(args.cache)
    if (cache / 'bundle.json').exists():
        prior = validate_bundle(read(cache / 'bundle.json'), config['job_id'])
        if prior['progress'].get('status') in ('COMPLETE', 'EXCEPTION_STOP', 'BLOCKED'):
            return
    started, failures = time.monotonic(), 0
    while time.monotonic() - started < 86400:
        try:
            try:
                value = fetch(config)
            except (OSError, ConnectionError, RuntimeError):
                recovered = existing_port()
                if recovered is None or recovered == config['socks_port']:
                    raise
                candidate = dict(config, socks_port=recovered)
                value = fetch(candidate)  # same token, fixed job, schema before persistence
                config = candidate
                write(args.private_config, config)
            write(cache / 'bundle.json', value)
            write(cache / 'sync.json', dict(status='OK', updated_epoch=time.time(),
                job_id=config['job_id'], ai_polling=False, experiment_retry=False))
            failures = 0
            if value['progress'].get('status') in ('COMPLETE', 'EXCEPTION_STOP', 'BLOCKED'):
                return
            time.sleep(5)
        except (ValueError, KeyError) as exc:
            write(cache / 'sync.json', dict(status='IDENTITY_STOP', reason=str(exc),
                updated_epoch=time.time(), job_id=config['job_id'], ai_polling=False,
                experiment_retry=False))
            raise
        except (OSError, ConnectionError, RuntimeError) as exc:
            failures += 1
            write(cache / 'sync.json', dict(status='UNKNOWN', reason=type(exc).__name__,
                updated_epoch=time.time(), job_id=config['job_id'],
                ai_polling=False, experiment_retry=False, failures=failures))
            time.sleep(min(60, 5 * 2**min(failures-1, 4)))
    write(cache / 'sync.json', dict(status='LIFETIME_EXPIRED', updated_epoch=time.time(),
        job_id=config['job_id'], ai_polling=False, experiment_retry=False))


if __name__ == '__main__':
    main()
