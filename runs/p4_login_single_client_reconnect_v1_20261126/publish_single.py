"""Publish the new run's source, small receipts and paper handoff in an isolated index."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from single_inputs import HERE
from publish_reconnect import BRANCH, FLAGS
from single_results import HANDOFF, NAMES
from sources import identity, save

REPO = HERE.parent.parent
SOURCE = ("METHOD.md","single_protocol.py","collect_single.py","single_inputs.py","evaluate_single.py",
          "run_single.py","single_results.py","publish_single.py","status_single.py")
INITIAL = ("REGISTRATION.json","PREFLIGHT.json")
FINAL = (*INITIAL,*NAMES,"ACCEPTANCE.json","SHA256SUMS")


def copy_receipts(evidence,final=False):
    received = HERE/"received"
    received.mkdir(exist_ok=True)
    for name in FINAL if final else INITIAL:
        src,dst = evidence/name,received/name
        dst.write_bytes(src.read_bytes())
        assert identity(dst)==identity(src)


def push(live,doc=None):
    files = [*(HERE/name for name in SOURCE),*(HERE/"received"/name for name in (FINAL if doc else INITIAL))]
    if doc:
        assert doc==REPO/"runs/mainline_docs/collab"/HANDOFF
        files.append(doc)
    assert all(p.stat().st_size<=512*1024 for p in files)
    paths = [p.relative_to(REPO).as_posix() for p in files]
    message = "Accept Paper04 rotated single-client reconnect stress" if doc else "Freeze Paper04 rotated single-client reconnect plan"
    env = dict(os.environ,GIT_TERMINAL_PROMPT="0")
    for retry in range(3):
        with TemporaryDirectory(prefix="single-index-",dir=live) as step:
            env["GIT_INDEX_FILE"] = str(Path(step)/"index")

            def git(*args,check=True):
                return subprocess.run(["git",*args],cwd=REPO,env=env,check=check,capture_output=True,
                                      text=True,encoding="utf8",timeout=35)

            base = git(*FLAGS,"ls-remote","--exit-code","--heads","origin",BRANCH).stdout.split()[0]
            if git("cat-file","-e",base+"^{commit}",check=False).returncode:
                git(*FLAGS,"fetch","--no-tags","--no-write-fetch-head","origin",BRANCH)
            git("read-tree",base)
            git("-c","core.autocrlf=false","add","-f","--",*paths)
            staged = git("diff","--cached","--name-only",base).stdout.splitlines()
            assert set(staged).issubset(paths)
            git("-c","core.whitespace=cr-at-eol","diff","--cached","--check",base)
            for path in paths:
                assert git("rev-parse",":"+path).stdout==git("hash-object","--no-filters","--",path).stdout
            commit = base
            if staged:
                tree = git("write-tree").stdout.strip()
                commit = git("commit-tree",tree,"-p",base,"-m",message).stdout.strip()
                git("update-ref","refs/codex/paper04/single-client-reconnect-20261126",commit)
                sent = git(*FLAGS,"push","origin",f"{commit}:{BRANCH}",check=False)
                if sent.returncode:
                    head = git(*FLAGS,"ls-remote","--exit-code","--heads","origin",BRANCH).stdout.split()[0]
                    if head!=base and retry<2:
                        continue
                    raise RuntimeError(sent.stderr.strip())
            assert git(*FLAGS,"ls-remote","--exit-code","--heads","origin",BRANCH).stdout.split()[0]==commit
            save(live/"BACKUP_STATUS.json",dict(status="PASS",commit=commit,files=paths,message=message))
            print("Verified",commit,flush=True)
            return
    raise RuntimeError("Mainline branch advanced during every scoped publish.")


if __name__=="__main__":
    root = Path(sys.argv[1])
    copy_receipts(root/"evidence")
    push(root/"live")
