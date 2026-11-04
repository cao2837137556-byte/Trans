"""An explicit engineering waiver is never an independent-review PASS."""
import json
from pathlib import Path
from checkpoint import require, sha


def require_review_decision(card, auth, root):
    review = card.get('independent_review', {})
    if review.get('status') == 'PASS':
        return
    require(review.get('status') == 'USER_WAIVED' and auth.get('review_waived') is True,
            'ENGINEERING_INDEPENDENT_REVIEW_REQUIRED')
    spec = review.get('waiver', {})
    name = spec.get('path', '')
    root = Path(root).resolve()
    path = root/name
    require(name and not Path(name).is_absolute() and '..' not in Path(name).parts
            and not path.is_symlink() and path.resolve().is_relative_to(root), 'WAIVER_PATH')
    require(spec.get('sha256') == sha(path)
            and card.get('artifact_pins', {}).get(name) == spec['sha256']
            and auth.get('review_waiver_sha256') == spec['sha256'], 'WAIVER_BINDING')
    value = json.loads(path.read_text(encoding='utf-8'))
    require(value.get('status') == 'USER_WAIVED'
            and value.get('scope') == 'EDGE_FORMAL_WORKER_ENGINEERING_GATE'
            and value.get('independent_review_performed') is False
            and value.get('formal_evaluation_authorized') is False
            and bool(value.get('user_quote')) and bool(value.get('execution_quote')), 'WAIVER_SCOPE')
