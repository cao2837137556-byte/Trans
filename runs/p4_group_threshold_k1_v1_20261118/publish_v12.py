"""Archive this study through its own Git index on D, preserving the shared checkout."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from pack_v12 import HERE, PRIVATE, RUNS, DOC, REMOTE_FILES, read

ROOT = RUNS.parent
REF = "refs/heads/codex/exp-mainline"
LOCAL = (
    ".gitattributes",
    "README.md",
    "EXTERNAL_ELIGIBILITY.md",
    "EXTERNAL_ACCESS.json",
    "ASSETS.json",
    "PACKAGE_MANIFEST.json",
    "LOCAL_VALIDATION.json",
    "pack_v12.py",
    "verify_local.py",
    "transport.py",
    "delivery_v12.py",
    "dashboard.py",
    "progress.html",
    "publish_v12.py",
)


def git(cmd, env=None, check=True):
    return subprocess.run(
        ["git", *cmd],
        cwd=ROOT,
        env=env,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=65,
    )


def publish(phase):
    if phase == "freeze":
        paths = [HERE / n for n in (*REMOTE_FILES, *LOCAL)] + [DOC]
        msg = "Freeze Paper04 grouped thresholds, nearest component replay and donor audit"
    else:
        dest = HERE / "received"
        receipt = read(dest / "LOCAL_ACCEPTANCE.json")
        if receipt["status"] != "PASS":
            raise ValueError("LOCAL_VERIFICATION_REQUIRED")
        names = list(read(dest / "RETURN.json")["files"]) + ["RETURN.json", "LOCAL_ACCEPTANCE.json"]
        if any(n != Path(n).name or not n.endswith((".json", ".md", ".csv")) for n in names):
            raise ValueError("SMALL_OUTPUTS_ONLY")
        paths = [dest / n for n in names] + [HERE / "INSTALL_READBACK.json"]
        msg = "Accept Paper04 grouped thresholds, nearest component replay and donor audit"
    names = [p.relative_to(ROOT).as_posix() for p in paths]
    for attempt in range(3):
        try:
            match = git(["ls-remote", "--exit-code", "origin", REF]).stdout.strip().split()
            if len(match) != 2 or match[1] != REF:
                raise ValueError("GIT_REF_IDENTITY")
            base = match[0]
            if git(["cat-file", "-e", base + "^{commit}"], check=False).returncode:
                git(["fetch", "--quiet", "--no-write-fetch-head", "--no-tags", "origin", base])
            sealpath = (HERE / "RULE_FREEZE.json").relative_to(ROOT).as_posix()
            saved = git(["show", base + ":" + sealpath], check=False)
            if saved.returncode == 0 and json.loads(saved.stdout) != read(HERE / "RULE_FREEZE.json"):
                raise ValueError("PRIOR_RULE_SEAL_CONFLICT")
            with tempfile.TemporaryDirectory(prefix="archive-", dir=PRIVATE) as td:
                env = dict(os.environ, GIT_INDEX_FILE=str(Path(td) / "index"))
                git(["read-tree", base], env)
                git(["add", "-f", "--", *names], env)
                changes = set(
                    filter(
                        None,
                        git(["diff", "--cached", "--name-only", "-z", base, "--"], env).stdout.split("\0"),
                    )
                )
                if not changes <= set(names):
                    raise ValueError("GIT_SCOPE")
                if phase == "results":
                    indexed = {
                        x.split("\t")[1]: x.split()[1]
                        for x in git(["ls-files", "--stage", "-z", "--", *names], env).stdout.split("\0")
                        if x
                    }
                    hashes = git(["hash-object", "--no-filters", "--", *names], env).stdout.splitlines()
                    if any(indexed[n] != h for n, h in zip(names, hashes)):
                        raise ValueError("ARCHIVED_BYTE_IDENTITY")
                if not changes:
                    return base
                tree = git(["write-tree"], env).stdout.strip()
                commit = git(["commit-tree", tree, "-p", base, "-m", msg], env).stdout.strip()
            git(["push", "origin", commit + ":" + REF])
            return commit
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(2 + attempt)


if __name__ == "__main__":
    if sys.argv[1:] not in (["freeze"], ["results"]):
        raise SystemExit("expected freeze or results")
    print(publish(sys.argv[1]))
