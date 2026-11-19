"""Publish just this run's frozen implementation or its verified small result files."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from pack_ton import HERE, RUNS, PRIVATE, DOC, SCIENCE
from common_ton import read, require

ROOT = RUNS.parent
REF = "refs/heads/codex/exp-mainline"
EXTRA = (
    ".gitattributes",
    "README.md",
    "inputs_ton.py",
    "owner_evidence.py",
    "transport_ton.py",
    "delivery_ton.py",
    "dashboard.py",
    "progress.html",
    "pack_ton.py",
    "archive_ton.py",
    "validate_ton.py",
    "FROZEN.json",
    "PACKAGE_MANIFEST.json",
    "LOCAL_VALIDATION.json",
    "LOCAL_SLICE.json",
    "IDENTITY_AND_PAIRING.md",
)


def git(args, env=None, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf8",
        errors="replace",
        timeout=65,
        check=check,
    )


def publish(phase):
    if phase == "freeze":
        paths = [HERE / n for n in (*SCIENCE, *EXTRA)] + [DOC]
        msg = "Freeze original v12 ToN password diagnostic and paired identity gates"
    else:
        d = HERE / "received"
        receipt = read(d / "LOCAL_ACCEPTANCE.json")
        require(receipt["status"] == "PASS", "LOCAL_ACCEPTANCE")
        names = [*read(d / "RETURN.json")["files"], "RETURN.json", "LOCAL_ACCEPTANCE.json"]
        require(
            all(n == Path(n).name and n.endswith((".csv", ".json", ".md")) for n in names),
            "SMALL_RESULTS_ONLY",
        )
        paths = [d / n for n in names] + [HERE / "INSTALL_READBACK.json"]
        msg = "Accept frozen ToN password inference and separate paired analyses"
    names = [p.relative_to(ROOT).as_posix() for p in paths]
    for attempt in range(3):
        try:
            advertised = git(["ls-remote", "--exit-code", "origin", REF]).stdout.split()
            require(len(advertised) == 2 and advertised[1] == REF, "REMOTE_REF")
            base = advertised[0]
            if git(["cat-file", "-e", base + "^{commit}"], check=False).returncode:
                git(["fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "origin", base])
            f = (HERE / "DIAGNOSTIC_CARD.json").relative_to(ROOT).as_posix()
            prior = git(["show", base + ":" + f], check=False)
            require(
                prior.returncode != 0 or json.loads(prior.stdout) == read(HERE / "DIAGNOSTIC_CARD.json"),
                "DIFFERENT_FROZEN_IDENTITY_POLICY",
            )
            with tempfile.TemporaryDirectory(prefix="archive-", dir=PRIVATE) as td:
                env = dict(os.environ, GIT_INDEX_FILE=str(Path(td) / "index"))
                git(["read-tree", base], env)
                git(["add", "-f", "--", *names], env)
                changed = set(
                    filter(
                        None,
                        git(["diff", "--cached", "--name-only", "-z", base, "--"], env).stdout.split("\0"),
                    )
                )
                require(changed <= set(names), "BACKUP_SCOPE")
                if phase == "results":
                    staged = {
                        v.split("\t")[1]: v.split()[1]
                        for v in git(["ls-files", "--stage", "-z", "--", *names], env).stdout.split("\0")
                        if v
                    }
                    hashes = git(["hash-object", "--no-filters", "--", *names], env).stdout.splitlines()
                    require(all(staged[n] == h for n, h in zip(names, hashes)), "ARCHIVED_BYTES")
                if not changed:
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
    require(sys.argv[1:] in (["freeze"], ["results"]), "BACKUP_PHASE")
    print(publish(sys.argv[1]))
