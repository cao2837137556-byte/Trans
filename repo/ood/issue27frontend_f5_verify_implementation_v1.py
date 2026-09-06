"""Seal Stage I from synthetic tests and the already measured, single pilot."""
import io
import json
import subprocess
import unittest
from pathlib import Path

import issue27frontend_f5_unified_student_v1 as core
import issue27frontend_f5_unified_student_runner_v1 as runner
import issue27frontend_f5_unified_student_contract_tests_v1 as core_tests
import issue27frontend_f5_unified_student_integration_tests_v1 as integration_tests


def main():
    destination = runner.IROOT / "stage_i_acceptance.json"
    core.require(not destination.exists(), "Stage I receipt already exists; changes require a versioned engineering revision")
    core.require(not runner.OUTPUT.exists(), "this verification must not be run over a real experiment")
    runtime = core.configure_runtime()
    pilot_path = runner.IROOT / "synthetic_resource_pilot.json"
    pilot = runner.read_json(pilot_path)
    core.require(pilot["pass"] and pilot["runtime"] == runtime, "pilot/runtime mismatch")
    baseline = subprocess.check_output(["git", "show", "117e43f:repo/ood/issue27frontend_f5_unified_student_v1.py"], cwd=runner.ROOT)
    import hashlib
    core.require(hashlib.sha256(baseline).hexdigest() == pilot["code_sha256"], "measured pilot source identity")
    kernel = runner.pilot_kernel_hash(baseline.decode("utf-8"))
    current = runner.pilot_kernel_hash(Path(core.__file__).read_text(encoding="utf-8"))
    core.require(kernel == current, "numerical pilot path changed; no silent pilot reuse")
    core.require(core.sha_file(runner.ROOT / core.PROTOCOL_REL) == core.PROTOCOL_SHA, "FROZEN drift")
    core.reseed()
    core.require(core.tensor_hash(core.Student().state_dict()) == pilot["initial_tensor_sha256"], "initialization changed")
    results = {}
    for name, module in (("core", core_tests), ("integration", integration_tests)):
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
        core.atomic_bytes(runner.IROOT / (name + "_final_tests.txt"), stream.getvalue().encode())
        print(stream.getvalue(), flush=True)
        core.require(result.wasSuccessful() and not result.skipped, name + " suite failed/skipped")
        results[name] = {"passed": result.testsRun, "total": result.testsRun,
                         "sha256": core.sha_file(runner.IROOT / (name + "_final_tests.txt"))}
    scripts = [runner.ROOT / "scripts/start_frontend_f5_local.ps1", runner.ROOT / "scripts/watch_frontend_f5_local.ps1"]
    expressions = []
    for path in scripts:
        literal = str(path).replace("'", "''")
        expressions.append("$e=$null; $t=$null; [System.Management.Automation.Language.Parser]::ParseFile('" + literal + "',[ref]$t,[ref]$e) | Out-Null; if($e.Count){throw ($e | Out-String)}")
    checked = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "; ".join(expressions)],
                             capture_output=True, text=True, cwd=runner.ROOT)
    core.require(checked.returncode == 0, "PowerShell parser failed: " + checked.stderr)
    receipt = {"status": "F5_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS", "date": "2026-09-06",
               "protocol_sha256": core.PROTOCOL_SHA, "code_pins": runner.code_pins(),
               "runtime": runtime, "suites": results, "total_tests": sum(v["total"] for v in results.values()),
               "pilot_sha256": core.sha_file(pilot_path), "pilot_numeric_path_sha256": kernel,
               "pilot_measured_source_commit": "117e43f", "pilot_repeated": False,
               "powershell_parsers_passed": 2, "real_feature_numeric_opens": 0,
               "real_teacher_numeric_opens": 0, "real_optimizer_steps": 0,
               "P_authorized": False, "T_authorized": False, "K_authorized": False,
               "scientific_verdict": None, "deployment_changed": False}
    core.atomic_json(destination, receipt)
    runner.write_manifest(runner.IROOT)
    print(json.dumps({"status": receipt["status"], "tests": receipt["total_tests"], "real_training_started": False}), flush=True)


if __name__ == "__main__":
    main()
