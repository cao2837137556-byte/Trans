"""Single-attempt, byte-budgeted official downloads. No model or raw decoding."""
import argparse
import hashlib
import http.cookiejar
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / 'runs/legacy_normal_supplement_research_v1_20260917'
RUN = ROOT / 'runs/legacy_normal_supplement_acquisition_v1_20260917'
BASE = 'https://cicresearch.ca/IOTDataset/CIC_IOT_Dataset2022/'
MAGICS = {b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4', b'\x4d\x3c\xb2\xa1', b'\xa1\xb2\x3c\x4d', b'\x0a\x0d\x0d\x0a'}


def dump(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def publish(state):
    state['updated_epoch'] = time.time()
    dump(RUN / 'download_status.json', state)
    text = ('# 多日正常材料获取状态\n\n状态：{status}\n\n当前文件：{current_file}\n\n'
            '累计接收：{total_received_bytes:,} / {byte_cap:,} 字节\n\n'
            '本次文件接收：{current_received_bytes:,} 字节\n\n'
            '已完整获取：{completed_files} / 7\n\n停止原因：{reason}\n\n'
            '这里只记录原始下载；完整下载不等于材料验收或模型训练完成。\n').format(**state)
    tmp = RUN / 'STATUS.md.tmp'
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(RUN / 'STATUS.md')


def receive(response, fout, remaining, update):
    """Never request/read more body bytes than the remaining cap; no retries."""
    size, digest, prefix = 0, hashlib.sha256(), b''
    while size < remaining:
        chunk = response.read(min(256 * 1024, remaining - size))
        if not chunk:
            if prefix not in MAGICS:
                raise RuntimeError('PCAP_MAGIC_MISMATCH_OR_EMPTY')
            return size, digest.hexdigest()
        fout.write(chunk)
        digest.update(chunk)
        size += len(chunk)
        update(size)
        if len(prefix) < 4:
            # Read real file prefix; do not mistake a later chunk for the magic.
            prefix = (prefix + chunk)[:4]
        if len(prefix) == 4 and prefix not in MAGICS:
            raise RuntimeError('PCAP_MAGIC_MISMATCH')
    # EOF cannot be established without an additional read. Keep as partial.
    raise RuntimeError('BYTE_CAP_REACHED_COMPLETENESS_UNCONFIRMED')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=int, required=True)
    args = ap.parse_args()
    scope = json.loads((RESEARCH / 'proposed_acquisition_scope.json').read_text(encoding='utf-8'))
    if args.index not in range(7):
        raise RuntimeError('Index outside named scope')
    RUN.mkdir(exist_ok=True)
    (RUN / 'raw').mkdir(exist_ok=True)
    attempt = RUN / ('%02d_attempt.json' % args.index)
    if attempt.exists():
        raise RuntimeError('Attempt already exists; automatic retry forbidden')
    prior = []
    for i in range(args.index):
        prior.append(json.loads((RUN / ('%02d_receipt.json' % i)).read_text(encoding='utf-8')))
        check = json.loads((RUN / ('%02d_summary.json' % i)).read_text(encoding='utf-8'))
        if check['status'] != 'RAW_CHECK_COMPLETE':
            raise RuntimeError('Previous file raw check incomplete')
    used = sum(x['bytes'] for x in prior)
    cap = scope['proposed_total_raw_byte_limit']
    if used >= cap:
        raise RuntimeError('Budget exhausted')
    item = scope['files'][args.index]
    destination = RUN / 'raw' / Path(item['file']).name
    partial = destination.with_suffix(destination.suffix + '.partial')
    if destination.exists() or partial.exists():
        raise RuntimeError('Refuse existing raw destination')
    state = dict(status='CONNECTING', current_file=item['file'], total_received_bytes=used,
                 byte_cap=cap, current_received_bytes=0, completed_files=args.index, reason='',
                 raw_check_complete=False, no_training=True, retry_count=0)
    dump(attempt, dict(file=item, started_epoch=time.time(), byte_budget_remaining=cap-used,
                       source_scope_sha256=hashlib.sha256((RESEARCH/'proposed_acquisition_scope.json').read_bytes()).hexdigest(),
                       authorization='User: 可以，授权. Named7file acquisition and raw qualification; no training.',
                       script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    publish(state)
    try:
        # Identity supplied by the authorized operator over stdin; never saved.
        identity = json.loads(sys.stdin.readline())
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        opener.addheaders = [('User-Agent', 'Mozilla/5.0'), ('Accept-Encoding', 'identity')]
        with opener.open(BASE, timeout=60) as page:
            html = page.read(400000).decode('utf-8', 'replace')
        if 'action="insert.php"' not in html:
            raise RuntimeError('Official registration endpoint changed')
        registration = urllib.request.Request(BASE+'insert.php', data=urllib.parse.urlencode(identity).encode('utf-8'))
        with opener.open(registration, timeout=60) as result:
            result.read(400000)
        del identity, registration
        last = [0.0]
        def update(n):
            state['current_received_bytes'] = n
            state['total_received_bytes'] = used+n
            if time.monotonic()-last[0] >= 5:
                publish(state)
                last[0] = time.monotonic()
        with opener.open(item['url'], timeout=60) as response:
            headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in
                       ('content-type','content-length','content-disposition','transfer-encoding','last-modified','etag')}
            dump(RUN / ('%02d_headers.json' % args.index), dict(status=response.status, headers=headers, url=response.url))
            if response.status != 200 or 'text/html' in headers.get('content-type','').lower():
                raise RuntimeError('HTTP_OR_CONTENT_TYPE_MISMATCH')
            if Path(item['file']).name not in headers.get('content-disposition',''):
                raise RuntimeError('ATTACHMENT_IDENTITY_MISMATCH')
            length = headers.get('content-length')
            if length is not None and int(length) > cap-used:
                raise RuntimeError('DECLARED_SIZE_EXCEEDS_REMAINING_BUDGET')
            state['status'] = 'DOWNLOADING'
            publish(state)
            with partial.open('xb') as fout:
                size, digest = receive(response, fout, cap-used, update)
            if length is not None and size != int(length):
                raise RuntimeError('CONTENT_LENGTH_MISMATCH')
        partial.replace(destination)
        dump(RUN / ('%02d_receipt.json' % args.index), dict(file=item['file'], local_path=str(destination),
             bytes=size, sha256=digest, transport_eof=True, completed_epoch=time.time(),
             raw_format_integrity_verified=False, source_published_hash_available=False))
        state.update(status='DOWNLOADED_PENDING_RAW_CHECK', completed_files=args.index+1)
        publish(state)
        print(json.dumps(state,ensure_ascii=False))
    except BaseException as exc:
        state.update(status='STOPPED_NO_RETRY', reason=type(exc).__name__+': '+str(exc))
        if partial.exists():
            state['current_received_bytes']=partial.stat().st_size
            state['total_received_bytes']=used+partial.stat().st_size
        publish(state)
        raise


if __name__ == '__main__':
    main()
