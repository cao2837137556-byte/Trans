"""No network: archive identity and traversal rejection checks."""
import hashlib
import io
import tarfile
import unittest
from receiver import validate_members


def archive(items):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as out:
        for name, content, kind in items:
            info = tarfile.TarInfo(name); info.type = kind; info.size = len(content)
            out.addfile(info, io.BytesIO(content))
    data.seek(0)
    return tarfile.open(fileobj=data, mode='r:')


class DeliveryTests(unittest.TestCase):
    def test_exact_file(self):
        with archive([('prepared/ref.json', b'ok', tarfile.REGTYPE)]) as a:
            self.assertEqual(len(validate_members(a, {'prepared/ref.json': dict(bytes=2, sha256=hashlib.sha256(b'ok').hexdigest())})), 1)

    def test_bad_hash_rejected_before_install(self):
        with archive([('x', b'ok', tarfile.REGTYPE)]) as a:
            with self.assertRaisesRegex(ValueError, 'PIN'): validate_members(a, {'x': dict(bytes=2, sha256='0'*64)})

    def test_traversal_rejected_even_when_listed(self):
        with archive([('../x', b'', tarfile.REGTYPE)]) as a:
            with self.assertRaisesRegex(ValueError, 'RELATIVE'): validate_members(a, {'../x': dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest())})

    def test_symbolic_link_rejected(self):
        with archive([('x', b'', tarfile.SYMTYPE)]) as a:
            with self.assertRaisesRegex(ValueError, 'REGULAR'): validate_members(a, {'x': dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest())})

    def test_extra_or_duplicate_member_rejected(self):
        with archive([('x', b'', tarfile.REGTYPE), ('x', b'', tarfile.REGTYPE)]) as a:
            with self.assertRaisesRegex(ValueError, 'ALLOWLIST'): validate_members(a, {'x': dict(bytes=0, sha256=hashlib.sha256(b'').hexdigest())})


if __name__ == '__main__': unittest.main()
