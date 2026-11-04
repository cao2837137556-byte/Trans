import copy
from pathlib import Path
import tempfile
import unittest
from checkpoint import atomic_json, sha
from review_authorization import require_review_decision


class WaiverTests(unittest.TestCase):
    def test_bound_waiver_and_no_fake_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root/'waiver.json'
            atomic_json(path, dict(status='USER_WAIVED', scope='EDGE_FORMAL_WORKER_ENGINEERING_GATE',
                independent_review_performed=False, formal_evaluation_authorized=False,
                user_quote='explicit waiver', execution_quote='explicit execution'))
            card = dict(independent_review=dict(status='USER_WAIVED', waiver=dict(path='waiver.json', sha256=sha(path))),
                        artifact_pins={'waiver.json': sha(path)})
            auth = dict(review_waived=True, review_waiver_sha256=sha(path))
            require_review_decision(card, auth, root)
            self.assertEqual(card['independent_review']['status'], 'USER_WAIVED')
            for altered in ({}, dict(auth, review_waived=False), dict(auth, review_waiver_sha256='wrong')):
                with self.assertRaises(ValueError): require_review_decision(card, altered, root)
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'WAIVER_BINDING'): require_review_decision(card, auth, root)

    def test_pending_review_still_blocked(self):
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_REVIEW'):
            require_review_decision(dict(independent_review=dict(status='PENDING')), dict(review_waived=True), Path.cwd())

    def test_actual_pass_still_supported(self):
        require_review_decision(dict(independent_review=dict(status='PASS')), {}, Path.cwd())
