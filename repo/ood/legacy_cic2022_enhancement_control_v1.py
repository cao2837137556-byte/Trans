"""One authorized PREPARE -> TRAIN_B -> TRAIN_C -> CHECK chain, zero retry.

The supervisor does not import a model or require an LLM to monitor it. Training
workers receive only a TRAIN descriptor and the immutable recipe, no CHECK cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "runs/mainline_docs/legacy_cic2022_p2_enhancement_small_recipe_v1_20260915.json"
HEAD = "4b28747b09480471e2bac1beb3a9badf27280efb"
PREPARE_PYTHON = ROOT.parents[1] / "supercompute_transfer/ckda_d1_local_runtime_20260814/.venv/Scripts/python.exe"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(str(temp), str(path))


def within(root, relative):
    root, path = Path(root).resolve(), (Path(root) / relative).resolve()
    require(path != root and root in path.parents, "PATH_OUTSIDE_EXPECTED_DIRECTORY")
    return path


class Status:
    def __init__(self, out):
        self.out, self.start, self.last = Path(out), time.monotonic(), {}

    def emit(self, value):
        self.last.update(value)
        self.last.update(updated_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=round(time.monotonic() - self.start, 3))
        atomic_json(self.out / "status.json", self.last)
        text = "# Legacy E3/P2 enhancement\n\nStatus: **{status}**\n\nStage: {stage}\n\nProgress: {done} / {total}\n\n".format(
            status=self.last.get("status", "RUNNING"), stage=self.last.get("stage", "PREFLIGHT"),
            done=self.last.get("done", 0), total=self.last.get("total", 0))
        text += "Elapsed: {} seconds\n\n".format(self.last["elapsed_seconds"])
        if "reason" in self.last:
            text += "Reason: " + str(self.last["reason"]) + "\n\n"
        text += "Completion: finalstatus.json. Results: evaluation/summary.json. No automatic retry.\n"
        temp = self.out / "status.md.tmp"
        temp.write_text(text, encoding="utf-8")
        os.replace(str(temp), str(self.out / "status.md"))
        with (self.out / "progress.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.last, ensure_ascii=False) + "\n")

    def finish(self, status, **extra):
        self.emit(dict(status=status, **extra))
        atomic_json(self.out / "finalstatus.json", self.last)


def verify_scope(path, authorized):
    require(authorized, "EXPLICIT_CHAIN_AUTHORIZATION_REQUIRED")
    scope = read_json(path)
    require(scope.get("schema") == "legacy-cic2022-enhancement-real-scope-v1", "SCOPE_SCHEMA")
    require(scope.get("execution_authorized") is True and bool(scope.get("authorization_basis")), "SCOPE_NOT_AUTHORIZED")
    require(scope["recipe_sha256"] == sha(RECIPE), "RECIPE_SHA")
    require(scope["retries"] == 0, "RETRY_POLICY")
    require(Path(scope["runtime"]["prepare"]["executable"]).resolve() == PREPARE_PYTHON.resolve(), "PREPARE_RUNTIME_PATH")
    require(Path(scope["runtime"]["train_check"]["executable"]).resolve() == Path(sys.executable).resolve(), "TRAIN_RUNTIME_PATH")
    for name, runtime in scope["runtime"].items():
        require(name in {"prepare", "train_check"}, "RUNTIME_ROLE")
        require(sha(runtime["executable"]) == runtime["executable_sha256"], "RUNTIME_EXECUTABLE_SHA")
        probe = subprocess.check_output([runtime["executable"], "-B", "-c",
            "import sys,json,importlib.metadata as m; print(json.dumps({'python':sys.version.split()[0], 'packages':{k:m.version(k) for k in sys.argv[1:]}}))"]
            + sorted(runtime["packages"]), cwd=str(ROOT), text=True)
        identity = json.loads(probe)
        require(identity == {"python": runtime["python"], "packages": runtime["packages"]}, "RUNTIME_VERSION_DRIFT")
    for relative, digest in scope["implementation_pins"].items():
        require(sha(within(ROOT, relative)) == digest, "IMPLEMENTATION_PIN:" + relative)
    required = {"repo/ood/legacy_cic2022_enhancement_control_v1.py", "repo/ood/legacy_cic2022_enhancement_prepare_v1.py",
                "repo/ood/legacy_cic2022_enhancement_train_v1.py", "repo/ood/legacy_cic2022_enhancement_evaluate_v1.py",
                "repo/ood/legacy_p2_supported_capability_ledger_v1.py"}
    require(required <= set(scope["implementation_pins"]), "IMPLEMENTATION_PIN_CLOSURE")
    extension = within(ROOT, scope["id_extension"]["path"])
    require(sha(extension) == scope["id_extension"]["sha256"], "ID_EXTENSION_SHA")
    id_scope = read_json(extension)
    require(id_scope.get("qualified") is True and int(id_scope["rows"]) > 0, "QUALIFIED_ID_REQUIRED")
    for args, expected in ((["rev-parse", "HEAD"], HEAD), (["branch", "--show-current"], "codex/exp-mainline")):
        actual = subprocess.check_output(["git"] + args, cwd=str(ROOT), text=True).strip()
        require(actual == expected, "GIT_IDENTITY")
    out = within(ROOT / "runs", scope["output_run_name"])
    require(not out.exists(), "OUTPUT_EXISTS_NO_RETRY")
    return scope, extension, out


def check_endpoints(b, c):
    require(b["status"] == c["status"] == "COMPLETE", "ENDPOINT_INCOMPLETE")
    for key in ("optimizer_updates", "row_exposures", "forward_batches", "initial_state_digest", "initial_dropout_rng_sha256",
                "final_dropout_rng_sha256", "first_update_forward_digests", "recipe_digest", "plan_digests", "old_features_digest", "new_features_digest"):
        require(b[key] == c[key], "MATCHED_ARMS:" + key)
    require(b["arm"] == "B" and c["arm"] == "C", "ENDPOINT_ARM_ORDER")


def run_child(arguments, log, status_file, status, python=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="27", PYTHONIOENCODING="utf-8", OMP_NUM_THREADS="4", MKL_NUM_THREADS="4")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with Path(log).open("xb") as output:
        child = subprocess.Popen([str(python or sys.executable), "-B", str(Path(__file__).resolve())] + arguments,
                                 cwd=str(ROOT), env=env, stdout=output, stderr=subprocess.STDOUT, creationflags=flags)
        status.emit(dict(child_pid=child.pid, status="RUNNING"))
        previous = None
        try:
            while child.poll() is None:
                if Path(status_file).exists():
                    raw = Path(status_file).read_bytes()
                    if raw != previous:
                        update = json.loads(raw.decode("utf-8"))
                        update.pop("elapsed_seconds", None)
                        update.pop("status", None)  # Worker completion is not entire-chain completion.
                        status.emit(update)
                        previous = raw
                time.sleep(1.0)
        finally:
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, check=False)
                else:
                    child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=5)
        detail = ""
        if child.returncode and Path(status_file).exists():
            terminal = read_json(status_file)
            detail = str(terminal.get("reason", terminal.get("error", "")))
        require(child.returncode == 0, "CHILD_FAILED_EXIT_" + str(child.returncode) + ":" + detail + ":" + str(log))


def notify_local(status, out):
    """Best-effort desktop balloon; notification failure never changes computation."""
    if os.name != "nt":
        return
    command = (
        "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
        "$notice = New-Object System.Windows.Forms.NotifyIcon; "
        "$notice.Icon = [System.Drawing.SystemIcons]::Information; $notice.Visible = $true; "
        "$notice.BalloonTipTitle = 'Paper04 E3/P2'; "
        "$notice.BalloonTipText = '" + ("Run complete. Open the saved status and result files." if status == "COMPLETE" else "Run stopped. Check status.json and worker logs. No retry was started.") + "'; "
        "$notice.ShowBalloonTip(5000); Start-Sleep -Seconds 6; $notice.Dispose()"
    )
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as error:
        atomic_json(Path(out) / "notification_error.json", {"reason": str(error), "computation_unchanged": True})


def run_chain(scope_path, authorized=False):
    scope, id_extension, out = verify_scope(scope_path, authorized)
    out.mkdir()  # Exclusive creation is the no-retry/duplicate-launch guard.
    status = Status(out)
    preservation = read_json(ROOT / "runs/legacy_cic2022_attack_acquisition_v1_20260915/unrelated_files_preservation.json")
    try:
        for row in preservation["files"]:
            require(sha(ROOT / row["path"]) == row["sha256"], "UNRELATED_FILE_DRIFT")
        atomic_json(out / "execution_scope.json", scope)
        status.emit(dict(status="RUNNING", stage="PREPARE", done=0, total=1, retries=0, supervisor_pid=os.getpid()))
        prepared = out / "prepared"
        run_child(["prepare-worker", "--recipe", str(RECIPE), "--out", str(prepared), "--id-extension", str(id_extension), "--authorized"],
                  out / "prepare.log", prepared / "status.json", status, python=PREPARE_PYTHON)
        manifest = read_json(prepared / "prepare_manifest.json")
        require(manifest.get("id_qualification", {}).get("qualified") is True and "id_cache" in manifest["artifacts"], "ID_NOT_PREPARED")
        train_manifest = within(prepared, manifest["training_manifest"])
        require(sha(train_manifest) == manifest["training_manifest_sha256"], "TRAIN_DESCRIPTOR_SHA")
        endpoints = {}
        for arm in ("B", "C"):
            stage_out = out / ("train_" + arm)
            status.emit(dict(stage="TRAIN_" + arm, done=0, total=200))
            run_child(["train-worker", "--recipe", str(RECIPE), "--training-manifest", str(train_manifest), "--out", str(stage_out), "--arm", arm, "--authorized"],
                      out / ("train_" + arm + ".log"), stage_out / "status.json", status)
            endpoints[arm] = read_json(stage_out / "checkpoint.json")
        check_endpoints(endpoints["B"], endpoints["C"])
        status.emit(dict(stage="CHECK", done=0, total=1))
        run_child(["check-worker", "--recipe", str(RECIPE), "--prepared", str(prepared), "--out", str(out / "evaluation"),
                   "--checkpoint-b", str(out / "train_B/checkpoint.npz"), "--checkpoint-c", str(out / "train_C/checkpoint.npz"), "--authorized"],
                  out / "check.log", out / "check_status.json", status)
        result = read_json(out / "evaluation/summary.json")
        require(result["status"] == "ENDPOINT_CHECK_COMPLETE", "CHECK_INCOMPLETE")
        for row in preservation["files"]:
            require(sha(ROOT / row["path"]) == row["sha256"], "UNRELATED_FILE_DRIFT")
        for folder in (out / "train_B", out / "train_C", out / "evaluation"):
            for line in (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                digest, relative = line.split(None, 1)
                require(sha(within(folder, relative.strip())) == digest, "FINAL_SEAL_MISMATCH")
        atomic_json(out / "final_verification.json", dict(status="PASS", matched_arms=True, result_seals=True,
                    ID_included=True, unrelated_files_preserved=8, scientific_verdict=result["contrasts"],
                    no_recalibration=True, retries=0, scope_sha256=sha(out / "execution_scope.json")))
        status.finish("COMPLETE", stage="COMPLETE", done=1, total=1, exit_code=0, engineering_verification="PASS", scientific_verdict=result["contrasts"])
        return out
    except BaseException as error:
        (out / "error_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        status.finish("STOP", reason=str(error), exit_code=1, retries=0)
        raise
    finally:
        if scope.get("desktop_notification", True):
            notify_local(status.last.get("status", "STOP"), out)


def training_worker(recipe_path, manifest_path, out, arm, authorized=False, *, synthetic=False):
    require(authorized or synthetic, "TRAIN_AUTHORIZATION_REQUIRED")
    import legacy_cic2022_enhancement_train_v1 as train
    import legacy_cic2022_enhancement_evaluate_v1 as evaluation
    import legacy_p2_supported_capability_ledger_v1 as ledger
    manifest_path = Path(manifest_path)
    manifest = read_json(manifest_path)
    require(set(manifest["artifacts"]) == {"old_cache", "new_train_cache", "reference_state"}, "TRAIN_DESCRIPTOR_ALLOWLIST")
    root = manifest_path.parent
    recipe = read_json(recipe_path)
    require(manifest["recipe_sha256"] == sha(recipe_path), "TRAIN_RECIPE_SHA")
    old_x, old_targets = evaluation.load_cache(root, manifest["artifacts"]["old_cache"], "OLD_REPLAY")
    new_x, new_targets = evaluation.load_cache(root, manifest["artifacts"]["new_train_cache"], "TRAIN")
    state = ledger.load_p2_state(evaluation.pinned(root, manifest["artifacts"]["reference_state"]))
    return train.train_arm(state, old_x, old_targets, new_x, new_targets, recipe, out, arm, synthetic=synthetic)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run"); run.add_argument("--scope", required=True); run.add_argument("--authorize-chain", action="store_true")
    validate = commands.add_parser("validate"); validate.add_argument("--scope", required=True); validate.add_argument("--authorize-chain", action="store_true")
    show = commands.add_parser("status"); show.add_argument("--out", required=True)
    for name in ("prepare-worker", "train-worker", "check-worker"):
        worker = commands.add_parser(name)
        worker.add_argument("--recipe", required=True); worker.add_argument("--out", required=True)
        worker.add_argument("--authorized", action="store_true")
        if name == "prepare-worker": worker.add_argument("--id-extension", required=True)
        elif name == "train-worker":
            worker.add_argument("--training-manifest", required=True); worker.add_argument("--arm", choices=["B", "C"], required=True)
        else:
            worker.add_argument("--prepared", required=True); worker.add_argument("--checkpoint-b", required=True); worker.add_argument("--checkpoint-c", required=True)
    args = parser.parse_args()
    if args.command == "run":
        run_chain(args.scope, args.authorize_chain)
    elif args.command == "validate":
        verify_scope(args.scope, args.authorize_chain)
        print("Scope/identity preflight PASS; no experiment started.")
    elif args.command == "status":
        path = Path(args.out) / "status.json"
        print(json.dumps(read_json(path) if path.exists() else {"status": "NOT_STARTED"}, ensure_ascii=False, indent=2))
    else:
        require(args.authorized, "WORKER_AUTHORIZATION_REQUIRED")
        if args.command == "prepare-worker":
            import legacy_cic2022_enhancement_prepare_v1 as prepare
            prepare.prepare(args.recipe, args.out, id_extension=args.id_extension)
        elif args.command == "train-worker":
            training_worker(args.recipe, args.training_manifest, args.out, args.arm, authorized=True)
        else:
            import legacy_cic2022_enhancement_evaluate_v1 as evaluation
            target = Path(args.out).parent / "check_status.json"
            evaluation.evaluate(args.recipe, args.prepared, args.checkpoint_b, args.checkpoint_c, args.out,
                                progress=lambda data: atomic_json(target, data))


if __name__ == "__main__":
    main()
