"""N1 implementation acceptance: pinned runtime, synthetic tests and file seals."""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

import issue27frontend_inheritance_n1_support_v1 as s
import issue27frontend_inheritance_n1_control_v1 as control


def parse_powershell():
    result = []
    for name in s.CODE:
        if not name.endswith(".ps1"):
            continue
        path = str(s.ROOT / name).replace("'", "''")
        command = "$n1Tokens=$null; $n1Errors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('" + path + "',[ref]$n1Tokens,[ref]$n1Errors); if ($n1Errors.Count) { $n1Errors | Out-String | Write-Output; exit 1 }"
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        parsed = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        result.append({"path": name, "exit_code": parsed.returncode})
        s.require(parsed.returncode == 0, "POWERSHELL_PARSE_FAILED")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-acceptance", action="store_true", required=True)
    parser.parse_args()
    pins = s.frozen_design()
    runtime_hashes = control.runtime_pins(pins)
    codes = control.code_pins()
    output = s.ROOT / s.IMPLEMENTATION
    s.require(not (output / "synthetic_acceptance.json").exists(), "ACCEPTANCE_ALREADY_SEALED")
    output.mkdir(parents=True, exist_ok=True)
    parse_receipt = parse_powershell()
    import issue27frontend_inheritance_n1_tests_v1 as tests
    report = tests.run_suite()
    s.require(control.code_pins() == codes, "CODE_CHANGED_DURING_ACCEPTANCE")
    writer = s.Writer(output, s.Budget())
    sequence = 1
    while (output / ("checks/check_%03d.json" % sequence)).exists():
        sequence += 1
    writer.json("checks/check_%03d.json" % sequence, {"report": report, "code_pins": codes,
                                                   "runtime_file_sha256": runtime_hashes})
    if report["status"] != "PASS":
        print(json.dumps({"status": "N1_SYNTHETIC_ACCEPTANCE_FAILED", "tests_run": report["tests_run"],
                          "receipt": "checks/check_%03d.json" % sequence}), flush=True)
        return 1
    test_sha = writer.json("synthetic_tests.json", report)
    writer.json("synthetic_acceptance.json", {
        "status": "N1_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS", "protocol_sha256": s.DESIGN_SHA,
        "input_pins_sha256": s.PINS_SHA, "code_pins": codes, "runtime_file_sha256": runtime_hashes,
        "runtime": report["runtime"], "synthetic_tests_sha256": test_sha,
        "tests_run": report["tests_run"], "powershell_parser_checks": parse_receipt,
        "real_numeric_access": 0, "real_execution_authorized": False,
        "real_lp_calls": 0, "real_model_forwards": 0, "real_checkpoint_tensor_loads": 0,
        "optimizer_or_backward_steps": 0, "resource_pilots": 0,
        "stage": "IMPLEMENTATION_AND_SYNTHETIC_ONLY", "inheritance": "NOT_PROVED"})
    sums = {path.relative_to(output).as_posix(): s.sha_file(path)
            for path in sorted(output.rglob("*")) if path.is_file() and path.name != "SHA256SUMS"}
    writer.write("SHA256SUMS", "".join(sha + "  " + name + "\n" for name, sha in sorted(sums.items())).encode("ascii"))
    control.acceptance()
    print(json.dumps({"status": "N1_IMPLEMENTATION_SYNTHETIC_ACCEPTANCE_PASS", "tests_run": report["tests_run"],
                      "powershell_parser_checks": len(parse_receipt), "real_numeric_access": 0}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
