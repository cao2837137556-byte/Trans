"""Resource budget and immutable-stage boundaries."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import common as c


class CommonTests(unittest.TestCase):
    def test_output_budget_includes_sibling_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stage = base/'evaluation'
            stage.mkdir()
            (base/'retained_fit.bin').write_bytes(b'0'*20)
            guard = c.Guard(stage, budget_folder=base)
            guard.output_limit = 10
            with self.assertRaisesRegex(ValueError, 'RESOURCE_OUTPUT_LIMIT'):
                guard.check(force=True, stage='fixture')
            self.assertTrue((base/'retained_fit.bin').exists())
            self.assertFalse((stage/'status.json').exists())

    def test_seal_rejects_additional_file_and_fresh_retains_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = c.fresh(Path(tmp)/'stage')
            c.write(folder/'identity.json', {'value': 1})
            c.seal(folder)
            (folder/'extra').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError, 'SEAL_EXTRA_OR_MISSING_FILES'):
                c.verify_seal(folder)
            with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_EXISTS'):
                c.fresh(folder)
            self.assertEqual(c.read(folder/'identity.json'), {'value': 1})


if __name__ == '__main__':
    unittest.main()
