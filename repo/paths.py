import os
import subprocess
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
ROOT_DIR = REPO_DIR.parent
DATA_DIR = ROOT_DIR
OUTPUT_DIR = ROOT_DIR
TRACKED_RUNS_DIR = ROOT_DIR / "runs"


def _git_stdout(*args: str) -> str:
    completed = subprocess.run(
        list(args),
        cwd=str(ROOT_DIR),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _iter_worktrees() -> list[tuple[Path, str | None]]:
    text = _git_stdout("git", "worktree", "list", "--porcelain")
    entries: list[tuple[Path, str | None]] = []
    worktree_path: Path | None = None
    branch_ref: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if raw.startswith("worktree "):
            if worktree_path is not None:
                entries.append((worktree_path, branch_ref))
            worktree_path = Path(raw.split(" ", 1)[1]).resolve()
            branch_ref = None
            continue
        if raw.startswith("branch "):
            branch_ref = raw.split(" ", 1)[1]
            continue
        if line == "" and worktree_path is not None:
            entries.append((worktree_path, branch_ref))
            worktree_path = None
            branch_ref = None
    if worktree_path is not None:
        entries.append((worktree_path, branch_ref))
    return entries


def _resolve_artifact_runs_dir() -> Path:
    env_runs_root = os.environ.get("KITNET_RUNS_ROOT")
    if env_runs_root:
        return Path(env_runs_root).expanduser().resolve()

    env_worktree_root = os.environ.get("KITNET_ARTIFACT_WORKTREE_ROOT")
    if env_worktree_root:
        return (Path(env_worktree_root).expanduser().resolve() / "runs")

    root = ROOT_DIR.resolve()
    if root.drive.upper() == "D:":
        return root / "runs"

    try:
        worktrees = _iter_worktrees()
        branch_name = _git_stdout("git", "branch", "--show-current")
        branch_refs: list[str] = []
        if branch_name:
            branch_refs.append(f"refs/heads/{branch_name}")
        if root.name == "kitnet-exp-mainline":
            branch_refs.append("refs/heads/codex/exp-mainline")

        for branch_ref in dict.fromkeys(branch_refs):
            for worktree_path, worktree_branch in worktrees:
                if (
                    worktree_branch == branch_ref
                    and worktree_path.drive.upper() == "D:"
                    and worktree_path.exists()
                ):
                    return worktree_path / "runs"

        root_parts = {part.lower() for part in root.parts}
        if ".codex" in root_parts and "worktrees" in root_parts:
            for worktree_path, _ in worktrees:
                if (
                    worktree_path.name == root.name
                    and worktree_path.drive.upper() == "D:"
                    and worktree_path.exists()
                ):
                    return worktree_path / "runs"
    except Exception:
        pass

    return root / "runs"


ARTIFACT_RUNS_DIR = _resolve_artifact_runs_dir()
