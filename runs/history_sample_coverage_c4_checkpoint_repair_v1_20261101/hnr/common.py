"""Shared serialization, identity, and frozen experiment constants."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import sys

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
OOD = ROOT / 'repo/ood'
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))
VERSION = 'history-sample-coverage-c4-v1-20261101'
SALT = 'well-hist-r2-20261031'
TARGETS = {
    'NETATMO': dict(owner='70:ee:50:18:34:43', display_name='Netatmo Camera', reference_end_us=1485907186758350, bank_end_frame=3766102, first_dev_time_us=1485907201277175, packets=4967010),
    'TP_LINK': dict(owner='50:c7:bf:00:56:39', display_name='TP Link',
                    reference_end_us=1480856333261023, bank_end_frame=66004,
                    first_dev_time_us=1486357446065969, packets=79773),
    'WEMO_POWER': dict(owner='ec:1a:59:79:f4:89', display_name='WEMO Power',
                       reference_end_us=1484092799863312, bank_end_frame=3430150,
                       first_dev_time_us=1484092851673414, packets=4273643),
    'SAMSUNG': dict(owner='00:16:6c:ab:6b:88', display_name='Samsung',
                    reference_end_us=1490054396682107, bank_end_frame=4419000,
                    first_dev_time_us=1490054401482691, packets=5880402),
}
for _r in TARGETS.values():
    _r.update(partition='EXTERNAL_ARCHIVAL_EVALUATION',
              device='unsw-attack-traces-2018:' + _r['owner'])
HEIM = dict(owner='44:01:bb:ec:10:4a', partition='DEV', device='HeimVision Camera')
REF_CAP = 4096
DEV_CAP = 4096
LAMBDA = .25
PAIR_LIMIT = 1000000000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                    sort_keys=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_rows(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if str(path).endswith('.gz'):
        raw = path.open('wb')
        stream = io.TextIOWrapper(gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0), encoding='utf-8')
    else:
        raw = None
        stream = path.open('wt', encoding='utf-8')
    with stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=True, allow_nan=False,
                                    separators=(',', ':')) + '\n')
    if raw is not None:
        raw.close()
