"""Meaningful metadata-only failures: tampered bytes and path escape rejected."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('edge_verify_package_tested', HERE / 'verify_package.py')
verify_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_module)


class PackageTests(unittest.TestCase):
    def test_tampered_same_size_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = root / 'head.bin'
            item.write_bytes(b'abc')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(dict(files={'head.bin':dict(bytes=3,sha256=verify_module.sha(item))})))
            self.assertEqual(verify_module.verify(root, manifest)['files'], 1)
            item.write_bytes(b'abd')
            with self.assertRaisesRegex(ValueError, 'PACKAGE_BYTE_PIN'):
                verify_module.verify(root, manifest)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'package'
            root.mkdir()
            outside = Path(temp) / 'outside.bin'
            outside.write_bytes(b'x')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(dict(files={'../outside.bin':dict(bytes=1,sha256=verify_module.sha(outside))})))
            with self.assertRaisesRegex(ValueError, 'PACKAGE_PATH_OR_MISSING'):
                verify_module.verify(root, manifest)


if __name__ == '__main__':
    unittest.main()
