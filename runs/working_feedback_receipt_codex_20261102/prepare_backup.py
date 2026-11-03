"""Build an explicit small-file backup inventory; never load scientific arrays."""
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").splitlines()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = {"AGENTS.md", ".gitignore", ".gitattributes",
             (OUT / "LARGE_ARTIFACT_MANIFEST_INDEX.json").relative_to(ROOT).as_posix()}
    for name in ("repo", "scripts"):
        for item in git("ls-files", "--others", "--exclude-standard", name):
            if Path(item).suffix in {".py", ".json", ".ps1", ".sh", ".slurm"}:
                paths.add(item)
    for path in (ROOT / "runs/mainline_docs").rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".sha256", ".txt", ".py", ".csv"}:
            paths.add(path.relative_to(ROOT).as_posix())
    inventory = OUT / "git_inventory/PRUNED_SMALL_ARTIFACT_CANDIDATES.json"
    candidates = json.loads(inventory.read_text(encoding="utf-8-sig"))["pruned_candidates"]
    supplemental = OUT / "git_inventory/SUPPLEMENTAL_CANDIDATES.json"
    if not supplemental.exists():
        raise RuntimeError("Supplemental coverage review must finish first")
    extra = json.loads(supplemental.read_text(encoding="utf-8-sig"))
    candidates += extra["candidates"]
    excluded = []
    for row in candidates:
        item = row["path"]
        # User terminal commands and mutable progress/readback mirrors are not source receipts.
        if Path(item).name.startswith(("RUN_", "START_")) or Path(item).name in {
            "HTTP_RECEIPT.json", "PROGRESS.json", "TERMINAL_REMOTE_READBACK.json"
        }:
            excluded.append(item)
        else:
            paths.add(item)
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".md", ".sha256"}:
            if path.name not in {"SMALL_ARTIFACT_CANDIDATES.json", "SELECTED_FILES.json",
                                 "STAGED_VERIFICATION.json", "PUSH_VERIFICATION.json"}:
                paths.add(path.relative_to(ROOT).as_posix())
    # Preserve unrelated existing tracked modifications; only the two mainline docs are in scope.
    tracked = set(git("ls-files"))
    modified = set(git("diff", "--name-only"))
    unrelated = sorted(x for x in modified if not x.startswith("runs/mainline_docs/")
                       and x not in {"AGENTS.md", ".gitignore", ".gitattributes"})
    paths -= set(unrelated)
    changed = sorted(x for x in paths if x not in tracked or x in modified
                     or x in {".gitignore", ".gitattributes"})
    (OUT / "stage_paths.txt").write_text("\n".join(changed) + "\n", encoding="utf-8", newline="\n")
    # Pin exact bytes for newly versioned files and the two changed handoff docs.
    attributes = ROOT / ".gitattributes"
    marker = "# BEGIN mainline exact-byte backup 20261102"
    before = attributes.read_text(encoding="utf-8").split(marker)[0].rstrip()
    lines = [marker, "# SHA-sealed sources/receipts must survive checkout without EOL conversion.",
             "/.gitignore text eol=lf"]
    for item in changed:
        if item not in {".gitignore", ".gitattributes"}:
            lines.append("/" + item + " -text")
    attributes.write_text(before + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    # Keep the runs default-deny policy; admit small file types only in reviewed packages.
    ignore = ROOT / ".gitignore"
    marker = "# BEGIN reviewed mainline small-artifact backup 20261102"
    before = ignore.read_text(encoding="utf-8").split(marker)[0].rstrip()
    dirs = sorted({x.split("/")[1] for x in paths if x.startswith("runs/")
                   and not x.startswith("runs/mainline_docs/")})
    lines = [marker]
    for directory in dirs:
        prefix = "/runs/" + directory
        lines += ["!" + prefix + "/", prefix + "/**", "!" + prefix + "/**/"]
        lines += ["!" + prefix + "/**/*" + ext for ext in
                  (".py", ".json", ".md", ".sha256", ".slurm", ".sh", ".txt")]
        lines.append("!" + prefix + "/**/*SHA256SUMS")
    lines += ["# Heavy/private inputs remain local; only digest receipts belong in this backup."]
    lines += ["*." + ext for ext in ("pcap", "pcapng", "cap", "npy", "npz", "pt", "pth", "ckpt",
                                    "sqlite", "sqlite3", "db", "zip", "tar", "gz", "f32le", "pkl")]
    lines += [".private/", "/_hpc_upload/", "/_hpc_pullback/", "/tmp/", "/.claude/settings.local.json",
              "/runs/**/staged_root/", "/runs/**/retrieved/", "/runs/**/transport/",
              "/runs/**/user_supplied/", "/runs/**/RUN_IN_HPC_TERMINAL.txt"]
    ignore.write_text(before + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    # Existing manifests retain scientific large-file identity; no GB-scale rehash is implied.
    manifests = []
    for item in sorted(paths):
        if Path(item).suffix not in {".json", ".sha256"} or "working_feedback_receipt" in item:
            continue
        path = ROOT / item
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"\.(?:npz|npy|pcapng?|pt|pth|sqlite|tar|gz)\b", content, re.I) and re.search(r"[0-9a-f]{64}", content):
            manifests.append({"path": item, "bytes": path.stat().st_size, "sha256": digest(path)})
    fixture = ROOT / "repo/ood/fixtures/continuous_scope_v3/udp_first_and_last.pcapng"
    omitted = {"status": "DIGEST_INDEX_ONLY_NOT_BINARY_BACKUP",
               "manifest_scope": "Selected existing receipts containing large-artifact paths and SHA256 values",
               "verification": "Receipt bytes rehashed now; their large referenced files were not rehashed in this task",
               "not_exhaustive_all_historical_artifacts": True, "existing_manifests": manifests,
               "newly_hashed_small_omitted_fixture": {"path": fixture.relative_to(ROOT).as_posix(),
                                                     "bytes": fixture.stat().st_size, "sha256": digest(fixture)}}
    (OUT / "LARGE_ARTIFACT_MANIFEST_INDEX.json").write_text(json.dumps(omitted,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    changed.append((OUT / "LARGE_ARTIFACT_MANIFEST_INDEX.json").relative_to(ROOT).as_posix())
    changed = sorted(set(changed))
    (OUT / "stage_paths.txt").write_text("\n".join(changed)+"\n",encoding="utf-8",newline="\n")
    report = {"status": "PREPARED_NOT_STAGED", "paths": changed,
              "files": [{"path": x, "bytes": (ROOT/x).stat().st_size, "sha256": digest(ROOT/x)} for x in changed],
              "preserved_unrelated_modifications": unrelated, "excluded_readback_or_terminal": excluded,
              "categories": dict(Counter(x.split('/')[0] for x in changed))}
    (OUT / "SELECTED_FILES.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"selected":len(changed),"bytes":sum(x["bytes"] for x in report['files']),
                      "unrelated_preserved":len(unrelated),"manifest_files":len(manifests)}))


if __name__ == "__main__":
    main()
