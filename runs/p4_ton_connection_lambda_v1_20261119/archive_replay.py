"""Publish only the connection-replay source, frozen data card and verified small returns."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from pack import HERE, PRIVATE, RUNS, DOC, SRC, read

ROOT = RUNS.parent
REF = "refs/heads/codex/exp-mainline"
PUBLIC = (
    ".gitattributes",
    "README.md",
    "pack.py",
    "transport.py",
    "dashboard.py",
    "progress.html",
    "verify_local.py",
    "receive.py",
    "archive_replay.py",
    "CACHE_PINS.json",
    "PACKAGE_MANIFEST.json",
    "LOCAL_VALIDATION.json",
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
        check=check,
        timeout=60,
    )


def publish(phase):
    if phase == "freeze":
        paths = [HERE / n for n in (*SRC, *PUBLIC)] + [DOC]
        message = "Freeze cached ToN connection-level lambda diagnostic"
    else:
        dest = HERE / "received"
        assert read(dest / "LOCAL_ACCEPTANCE.json")["status"] == "PASS"
        names = [*read(dest / "RETURN.json")["files"], "RETURN.json", "LOCAL_ACCEPTANCE.json"]
        assert all(n == Path(n).name and n.endswith((".csv", ".json", ".md")) for n in names)
        paths = [dest / n for n in names] + [HERE / "INSTALL_READBACK.json"]
        message = "Accept cached ToN connection-level replay and paired counts"
    names = [p.relative_to(ROOT).as_posix() for p in paths]
    for attempt in range(3):
        try:
            adv = git(["ls-remote", "--exit-code", "origin", REF]).stdout.split()
            assert len(adv) == 2 and adv[1] == REF
            base = adv[0]
            if git(["cat-file", "-e", base + "^{commit}"], check=False).returncode:
                git(["fetch", "--quiet", "--no-tags", "--no-write-fetch-head", "origin", base])
            seal = (HERE / "PACKAGE_MANIFEST.json").relative_to(ROOT).as_posix()
            prior = git(["show", base + ":" + seal], check=False)
            if prior.returncode == 0 and json.loads(prior.stdout) != read(HERE / "PACKAGE_MANIFEST.json"):
                raise ValueError("PREVIOUS_CACHE_REPLAY_CONFLICT")
            with tempfile.TemporaryDirectory(prefix="archive-", dir=PRIVATE) as tmp:
                env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
                git(["read-tree", base], env)
                git(["add", "-f", "--", *names], env)
                changes = set(
                    filter(
                        None,
                        git(["diff", "--cached", "--name-only", "-z", base, "--"], env).stdout.split("\0"),
                    )
                )
                assert changes <= set(names)
                if not changes:
                    return base
                if phase == "results":
                    staged = {
                        x.split("\t")[1]: x.split()[1]
                        for x in git(["ls-files", "--stage", "-z", "--", *names], env).stdout.split("\0")
                        if x
                    }
                    assert all(
                        staged[k] == h
                        for k, h in zip(
                            names, git(["hash-object", "--no-filters", "--", *names], env).stdout.splitlines()
                        )
                    )
                tree = git(["write-tree"], env).stdout.strip()
                commit = git(["commit-tree", tree, "-p", base, "-m", message], env).stdout.strip()
            git(["push", "origin", commit + ":" + REF])
            return commit
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(2)


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["results"])
    print(publish(sys.argv[1]))
