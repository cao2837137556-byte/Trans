"""N2 explicit real gate, one worker, Windows job limits and read-only status."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import issue27frontend_inheritance_n2_support_v1 as s


def runtime_pins(pins):
    root = Path(pins["runtime_root"])
    s.require(Path(sys.executable).resolve() == (root / "python.exe").resolve(), "PYTHON_EXECUTABLE_DRIFT")
    observed = {}
    for name, expected in pins["runtime_file_sha256"].items():
        actual = s.sha_file(root / name)
        s.require(actual == expected, "RUNTIME_FILE_DRIFT")
        observed[name] = actual
    return observed


def code_pins(root=s.ROOT):
    return {name: s.sha_file(root / name) for name in s.CODE + (s.CORE,)}


def acceptance(root=s.ROOT):
    folder = root / s.IMPLEMENTATION
    sums = s.manifest((folder / "SHA256SUMS").read_bytes())
    s.require("synthetic_acceptance.json" in sums and "synthetic_tests.json" in sums, "ACCEPTANCE_MANIFEST")
    for name, expected in sums.items():
        s.require(s.sha_file(folder / name) == expected, "ACCEPTANCE_MEMBER_DRIFT")
    receipt = json.loads((folder / "synthetic_acceptance.json").read_text(encoding="utf-8"))
    s.require(receipt["status"] == "N2_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS"
              and receipt["code_pins"] == code_pins(root)
              and receipt["protocol_sha256"] == s.DESIGN_SHA and receipt["input_pins_sha256"] == s.PINS_SHA
              and receipt["real_numeric_access"] == 0 and receipt["tests_run"] >= 30
              and len(receipt["powershell_parser_checks"]) == 2
              and all(p["exit_code"] == 0 for p in receipt["powershell_parser_checks"]),
              "IMPLEMENTATION_ACCEPTANCE_DRIFT")
    return receipt


class Job:
    def __init__(self, process, memory_limit):
        s.require(os.name == "nt", "WINDOWS_JOB_REQUIRED")
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", ctypes.c_ulong), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_ulong),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_ulong), ("SchedulingClass", ctypes.c_ulong)]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self.kernel.CreateJobObjectW.restype = ctypes.c_void_p
        self.kernel.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
        self.kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        s.require(bool(self.handle), "JOB_CREATE_FAILED")
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2108
        info.BasicLimitInformation.ActiveProcessLimit = 1
        info.ProcessMemoryLimit = memory_limit
        try:
            s.require(self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)),
                      "JOB_LIMIT_FAILED")
            s.require(self.kernel.AssignProcessToJobObject(self.handle, ctypes.c_void_p(int(process._handle))),
                      "JOB_ASSIGN_FAILED")
        except Exception:
            self.close()
            raise

    def terminate(self):
        s.require(self.kernel.TerminateJobObject(self.handle, 124), "JOB_TERMINATE_FAILED")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def atomic_status(path, value):
    data = s.json_bytes(value)
    s.require(len(data) <= 65536, "CONTROL_RECEIPT_SIZE")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def directory_bytes(folder):
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())


def wait_gate(output):
    deadline = time.monotonic() + 30
    while not (output / "worker_gate.json").exists():
        s.require(time.monotonic() < deadline, "WORKER_GATE_TIMEOUT")
        time.sleep(0.05)
    gate = json.loads((output / "worker_gate.json").read_text(encoding="utf-8"))
    s.require(gate["worker_pid"] == os.getpid() and gate["parent_pid"] == os.getppid(), "WORKER_GATE_IDENTITY")
    return gate


def supervise(command, output, caps=None, started=None, environment=None, synthetic=False, preflight=None):
    limits = dict(s.CAPS if caps is None else caps)
    started = time.monotonic() if started is None else started
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    process, job, stop, peak = None, None, None, 0
    try:
        atomic_status(output / "attempt.json", {"started_monotonic": started, "parent_pid": os.getpid(),
                                                "synthetic": synthetic, "caps": limits, "restarts": 0})
        if preflight is not None:
            preflight()
        s.require(time.monotonic() - started < limits["wall_seconds"] - min(2, limits["wall_seconds"] * 0.05),
                  "GLOBAL_WALL_STOP")
        process = subprocess.Popen(command, cwd=str(s.ROOT), env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        job = Job(process, limits["memory_bytes"])
        atomic_status(output / "worker_gate.json", {"worker_pid": process.pid, "parent_pid": os.getpid(),
                                                   "started_monotonic": started})
        last_update = -float("inf")
        while process.poll() is None:
            now = time.monotonic()
            if now - started >= limits["wall_seconds"] - min(2, limits["wall_seconds"] * 0.05):
                stop = "GLOBAL_WALL_STOP"
            try:
                peak = max(peak, s.peak_memory(process.pid))
            except s.Stop:
                if process.poll() is None:
                    raise
            if peak > limits["memory_bytes"]:
                stop = "GLOBAL_MEMORY_STOP"
            size = directory_bytes(output)
            if size > limits["output_bytes"] - limits["reserve_bytes"]:
                stop = "GLOBAL_OUTPUT_STOP"
            if stop:
                job.terminate()
                break
            if now - last_update >= 1:
                phase = "VERIFYING_INPUTS"
                for name, label in (("selected_uid_range_attachment.json", "ASSEMBLING_FIXED_CANDIDATE"),
                                    ("assembled_state_before_decode.json", "SINGLE_DEV_FORWARD"),
                                    ("development_measurements.json", "SEALING")):
                    if (output / name).exists():
                        phase = label
                atomic_status(output / "live_status.json", {"status": "RUNNING", "phase": phase,
                              "pid": process.pid, "elapsed_seconds": now - started,
                              "peak_memory_bytes": peak, "output_bytes": size, "synthetic": synthetic})
                last_update = now
            time.sleep(0.1)
        process.wait(timeout=10)
    except Exception as exc:
        stop = str(exc) if isinstance(exc, s.Stop) else "SUPERVISOR_" + type(exc).__name__
        if isinstance(exc, OSError):
            stop += "_WINERROR_" + str(getattr(exc, "winerror", None)) + "_ERRNO_" + str(exc.errno)
    finally:
        if process is not None and process.poll() is None:
            if job is not None:
                job.terminate()
            else:
                process.kill()
            process.wait(timeout=10)
        if job is not None:
            job.close()
    verdict = {"status": "N2_ENGINEERING_STOP", "reason": stop or "WORKER_TERMINAL_MISSING"}
    terminal = output / "worker_terminal.json"
    if stop is None and process is not None and process.returncode == 0 and terminal.is_file():
        try:
            s.require(terminal.stat().st_size < limits["reserve_bytes"] // 2, "WORKER_TERMINAL_SIZE")
            receipt = json.loads(terminal.read_text(encoding="utf-8"))
            verdict = validate_worker(receipt, output, limits)
            peak = max(peak, receipt.get("resource", {}).get("peak_memory_bytes", 0))
        except Exception as exc:
            verdict = {"status": "N2_ENGINEERING_STOP", "reason": str(exc) if isinstance(exc, s.Stop)
                       else "WORKER_TERMINAL_INVALID_" + type(exc).__name__}
    elif stop is None and process is not None and process.returncode != 0:
        verdict["reason"] = "WORKER_EXIT_" + str(process.returncode)
    if directory_bytes(output) > limits["output_bytes"] - limits["reserve_bytes"]:
        verdict = {"status": "N2_ENGINEERING_STOP", "reason": "GLOBAL_OUTPUT_STOP"}
    if peak > limits["memory_bytes"]:
        verdict = {"status": "N2_ENGINEERING_STOP", "reason": "GLOBAL_MEMORY_STOP"}
    if time.monotonic() - started > limits["wall_seconds"]:
        verdict = {"status": "N2_ENGINEERING_STOP", "reason": "GLOBAL_WALL_STOP"}
    # Hash payloads before declaring completion; sealing is part of the total budget.
    members = {path.relative_to(output).as_posix(): s.sha_file(path)
               for path in sorted(output.rglob("*")) if path.is_file()
               and path.name not in {"SHA256SUMS", "supervisor_terminal.json"}}
    if time.monotonic() - started > limits["wall_seconds"]:
        verdict = {"status": "N2_ENGINEERING_STOP", "reason": "GLOBAL_WALL_STOP"}
    atomic_status(output / "supervisor_terminal.json", {"verdict": verdict, "elapsed_seconds": time.monotonic() - started,
                  "peak_memory_bytes": peak, "output_bytes_before_seal": directory_bytes(output),
                  "worker_exit_code": None if process is None else process.returncode,
                  "synthetic": synthetic, "worker_count": int(process is not None), "restarts": 0,
                  "enforcement": "Windows job: one process, committed-memory limit, kill-on-close; 0.1 s external polling"})
    members["supervisor_terminal.json"] = s.sha_file(output / "supervisor_terminal.json")
    with (output / "SHA256SUMS").open("xb") as stream:
        stream.write("".join(sha + "  " + name + "\n" for name, sha in sorted(members.items())).encode("ascii"))
    return verdict


def validate_worker(receipt, output, limits):
    verdict = receipt["verdict"]
    s.require(isinstance(verdict, dict) and verdict.get("status") in s.STATUSES, "WORKER_TERMINAL_SCHEMA")
    if verdict["status"] not in s.SCIENTIFIC:
        return verdict
    s.require(verdict.get("complete") is True and verdict.get("targets") == 5206
              and verdict.get("contexts") == 4323 and verdict.get("F5_eligible") is False
              and verdict.get("deployment") is False and verdict.get("inheritance") == "NOT_PROVED"
              and verdict.get("K") == "NOT_AUTHORIZED", "WORKER_COMPLETE_SCHEMA")
    counts = receipt["resource"]["counts"]
    for key, value in counts.items():
        s.require(key in limits and value <= limits[key] and value >= 0, "WORKER_ACTION_CAP")
    for key in ("loads", "head_decodes", "assemblies", "passes", "batches", "contexts", "targets"):
        s.require(counts.get(key) == s.CAPS[key], "WORKER_ACTION_COUNTS")
    required = {"runtime_receipt.json", "selected_uid_range_attachment.json", "verified_input_receipt.json",
                "historical_witness_identity.json", "assembled_state_before_decode.json",
                "final_old_development_reference.json", "assembled_state_after_forward.json",
                "all_target_predictions.json", "development_measurements.json", "access_receipt.json"}
    hashes = receipt["output_hashes"]
    s.require(set(hashes) == required, "WORKER_OUTPUT_SET")
    for name, sha in hashes.items():
        s.relative_name(name)
        s.require(s.sha_file(output / name) == sha, "WORKER_OUTPUT_HASH")
    def read(name):
        return json.loads((output / name).read_text(encoding="utf-8"))
    result = read("development_measurements.json")
    s.require(all(result[k] == v for k, v in verdict.items()), "WORKER_RESULT_AGREEMENT")
    ranges = read("selected_uid_range_attachment.json")
    s.require(counts["events"] == counts["decoded_events"] == ranges["selected_events"] > 0,
              "WORKER_EVENT_COUNTS")
    s.require(read("assembled_state_before_decode.json")["assembled_state"]
              == read("assembled_state_after_forward.json")["assembled_state"], "WORKER_STATE_CHANGED")
    return verdict


def status(output):
    output = Path(output)
    if not output.exists():
        return {"status": "NOT_STARTED"}
    for name in ("supervisor_terminal.json", "worker_terminal.json", "live_status.json", "attempt.json"):
        path = output / name
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {"source": name, "status": "STATUS_RECEIPT_UNREADABLE_DO_NOT_RESTART", "final": False}
            final = False
            if name == "supervisor_terminal.json" and (output / "SHA256SUMS").is_file():
                try:
                    members = s.manifest((output / "SHA256SUMS").read_bytes())
                    s.require(name in members and all(s.sha_file(output / member) == sha
                              for member, sha in members.items()), "FINAL_SEAL_DRIFT")
                    final = True
                except (OSError, s.Stop, ValueError):
                    return {"status": "FINAL_SEAL_INVALID_DO_NOT_RESTART", "final": False}
            return {**value, "source": name, "final": final}
    return {"status": "INCOMPLETE_ATTEMPT_DO_NOT_RESTART"}


def readiness():
    pins = s.frozen_design()
    observed_runtime = runtime_pins(pins)
    receipt = acceptance()
    s.require(receipt["runtime_file_sha256"] == observed_runtime, "ACCEPTED_RUNTIME_DRIFT")
    return pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("status", "check-readiness", "run-real", "worker"))
    parser.add_argument("--authorization")
    args = parser.parse_args()
    output = s.ROOT / s.REAL_OUTPUT
    if args.mode == "status":
        print(json.dumps(status(output)), flush=True)
        return
    if args.mode == "check-readiness":
        readiness()
        s.require(not output.exists(), "REAL_ATTEMPT_ALREADY_EXISTS")
        print(json.dumps({"status": "READY_FOR_SEPARATELY_AUTHORIZED_REAL_N2", "real_numeric_access": 0}), flush=True)
        return
    s.require(args.authorization == s.AUTHORIZATION, "EXPLICIT_REAL_N2_AUTHORIZATION_REQUIRED")
    started = time.monotonic()
    if args.mode == "worker":
        gate = wait_gate(output)
        try:
            pins = readiness()
            import issue27frontend_inheritance_n2_runner_v1 as runner
            runtime = runner.configure_runtime()
            runner.real_worker(output, pins, runtime, gate["started_monotonic"])
        except Exception as exc:
            if not (output / "worker_terminal.json").exists():
                atomic_status(output / "worker_terminal.json", {"verdict": {"status": "N2_ENGINEERING_STOP",
                              "reason": str(exc) if isinstance(exc, s.Stop) else "WORKER_STARTUP_" + type(exc).__name__}})
        return
    environment = dict(os.environ, PYTHONHASHSEED="2705", OMP_NUM_THREADS="4", MKL_NUM_THREADS="4",
                       PYTHONDONTWRITEBYTECODE="1", TORCH_FORCE_WEIGHTS_ONLY_LOAD="1")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "worker", "--authorization", s.AUTHORIZATION]
    verdict = supervise(command, output, started=started, environment=environment, preflight=readiness)
    print(json.dumps(verdict), flush=True)


if __name__ == "__main__":
    main()
