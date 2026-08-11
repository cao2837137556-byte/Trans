"""Apply the exact CKDA D0 Python-3.9 syntax compatibility patch to netFound."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path


UPSTREAM_FILE_SHA256 = "a70366ea775f2eeaabd2e6a00a44c2dfae1a199249a3688d5183866b8a4ed0ed"
TARGET_RELATIVE = Path("modules/netFoundModels.py")
OLD_BLOCK = '''    match problem_type:
        case "regression":
            loss_fct = nn.L1Loss()
            if num_labels == 1:
                loss = loss_fct(logits.squeeze(), (labels.squeeze().to(torch.float32)))
            else:
                loss = loss_fct(logits, labels)
        case "single_label_classification":
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, num_labels), labels)
        case "multi_label_classification":
            loss_fct = nn.BCEWithLogitsLoss()
            loss = loss_fct(logits, labels)
        case _:
            raise ValueError(f"Unknown problem type: {problem_type}")
'''
NEW_BLOCK = '''    if problem_type == "regression":
        loss_fct = nn.L1Loss()
        if num_labels == 1:
            loss = loss_fct(logits.squeeze(), (labels.squeeze().to(torch.float32)))
        else:
            loss = loss_fct(logits, labels)
    elif problem_type == "single_label_classification":
        loss_fct = nn.CrossEntropyLoss()
        loss = loss_fct(logits.view(-1, num_labels), labels)
    elif problem_type == "multi_label_classification":
        loss_fct = nn.BCEWithLogitsLoss()
        loss = loss_fct(logits, labels)
    else:
        raise ValueError(f"Unknown problem type: {problem_type}")
'''


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path = Path(path)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temp, path)


def assert_python39_tree(source_root: Path) -> int:
    count = 0
    for path in sorted(source_root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 9))
        count += 1
    if count == 0:
        raise RuntimeError("netFound Python source tree is empty")
    return count


def apply_patch(source_root: Path, audit_path: Path) -> dict[str, object]:
    target = source_root / TARGET_RELATIVE
    original_bytes = target.read_bytes()
    original_sha256 = sha256_bytes(original_bytes)
    if original_sha256 != UPSTREAM_FILE_SHA256:
        raise RuntimeError(
            f"netFound upstream source drift: expected={UPSTREAM_FILE_SHA256} actual={original_sha256}"
        )
    text = original_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if text.count(OLD_BLOCK) != 1:
        raise RuntimeError("netFound Python-3.9 compatibility target is not unique")
    patched = text.replace(OLD_BLOCK, NEW_BLOCK, 1)
    atomic_text(target, patched)
    parsed_files = assert_python39_tree(source_root)
    report: dict[str, object] = {
        "status": "CKDA_NETFOUND_PY39_COMPAT_PASS",
        "official_repo_commit": "b3ab5a3aa72640cc725ef207fb0145b039a57d35",
        "target_relative": TARGET_RELATIVE.as_posix(),
        "upstream_file_sha256": original_sha256,
        "patched_file_sha256": sha256_bytes(target.read_bytes()),
        "replacement_count": 1,
        "python39_ast_files": parsed_files,
        "semantic_change": "NONE_SYNTAX_EQUIVALENT_IF_ELIF",
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(audit_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source-root", required=True, type=Path)
    result.add_argument("--audit", required=True, type=Path)
    return result


def main() -> None:
    args = parser().parse_args()
    print(json.dumps(apply_patch(args.source_root, args.audit), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
