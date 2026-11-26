"""Back up only this experiment's protocol, small receipts and handoff."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from frozen_assets import HERE
from sources import identity, save

REPO = HERE.parent.parent
BRANCH = "refs/heads/codex/exp-mainline"
FLAGS = ("-c","http.proxy=http://127.0.0.1:7897","-c","https.proxy=http://127.0.0.1:7897")
SOURCE = ("METHOD.md","protocol_reconnect.py","collect_reconnect.py","frozen_assets.py",
          "evaluate_reconnect.py","results_reconnect.py","reconnect_controller.py",
          "status_reconnect.py","benchmark_reconnect.py","publish_reconnect.py")
TABLES = ("REGISTRATION.json","PREFLIGHT.json","TABLE1_LEGAL_RECONNECT.csv","TABLE2_MATCHED_H60_MCNEMAR.csv",
          "ACCEPTANCE.json","RESULT_SUMMARY.json","RESULTS_FOR_PAPER.md","SHA256SUMS")


def copy_small(evidence,handoff=None):
    received = HERE/"received"
    received.mkdir(exist_ok=True)
    names = TABLES if handoff else TABLES[:2]
    for name in names:
        data = (evidence/name).read_bytes()
        target = received/name
        target.write_bytes(data)
        assert identity(target)==identity(evidence/name)
    paths = [*(HERE/name for name in SOURCE),*(received/name for name in names)]
    if handoff:
        paths.append(handoff)
    return paths


def push_backup(live,files,message):
    paths = [p.resolve().relative_to(REPO.resolve()).as_posix() for p in files]
    roots = ((HERE/"received").resolve(),(REPO/"runs/mainline_docs/collab").resolve())
    for f in files:
        p = f.resolve()
        assert p.name in SOURCE or p.name in TABLES or p.name=="20261126_paper04_v14_legal_reconnect_stress_handoff_codex.md"
        assert p.parent==HERE.resolve() or p.parent in roots
        assert p.stat().st_size<=512*1024
    env = dict(os.environ,GIT_TERMINAL_PROMPT="0")
    for retry in range(3):
        with tempfile.TemporaryDirectory(prefix="git-index-",dir=live) as place:
            env["GIT_INDEX_FILE"] = str(Path(place)/"isolated.index")
            def git(*args,check=True):
                return subprocess.run(["git",*args],cwd=REPO,env=env,check=check,
                                      capture_output=True,text=True,encoding="utf8",timeout=30)
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
            if not staged:
                commit = base
            else:
                tree = git("write-tree").stdout.strip()
                commit = git("commit-tree",tree,"-p",base,"-m",message).stdout.strip()
                git("update-ref","refs/codex/paper04/legal-reconnect-20261126",commit)
                published = git(*FLAGS,"push","origin",f"{commit}:{BRANCH}",check=False)
                if published.returncode:
                    head = git(*FLAGS,"ls-remote","--exit-code","--heads","origin",BRANCH).stdout.split()[0]
                    if head!=base and retry<2:
                        continue
                    raise RuntimeError(published.stderr.strip())
            assert git(*FLAGS,"ls-remote","--exit-code","--heads","origin",BRANCH).stdout.split()[0]==commit
            save(live/"BACKUP_STATUS.json",dict(status="PASS",commit=commit,files=paths,message=message))
            print("Verified",commit,flush=True)
            return
    raise RuntimeError("Remote branch kept advancing during the scoped backup.")


if __name__=="__main__":
    root = Path(sys.argv[1])
    files = copy_small(root/"evidence")
    push_backup(root/"live",files,"Freeze Paper04 v14 legal reconnect protocol and preflight")
