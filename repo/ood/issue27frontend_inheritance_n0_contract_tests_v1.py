"""Synthetic N0 contract checks; never load real metadata or invoke inventory."""
from __future__ import annotations

import builtins
import csv
import gzip
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

IMPLEMENTATION = Path(__file__).with_name("issue27frontend_inheritance_n0_inventory_v1.py")
SPEC = importlib.util.spec_from_file_location("n0_contract_subject", IMPLEMENTATION)
n0 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n0)


def fixture(uid="fit-1", **changes):
    row = dict.fromkeys(n0.F1_COLUMNS, "synthetic")
    row.update(uid=uid, phase="fit", legal_fit="True", cross_phase_context="False")
    row.update(changes)
    return row


def encoded(rows, columns=None):
    columns = n0.F1_COLUMNS if columns is None else columns
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows([[row[name] for name in columns] if isinstance(row, dict) else row for row in rows])
    return buffer.getvalue().encode("utf-8")


def scan(blob, **options):
    audit = {}
    rows = n0.scan_csv(blob, n0.F1_COLUMNS, n0.F1_COLUMNS, audit, lambda: None, mixed=True, **options)
    return rows, audit


class N0ContractTests(unittest.TestCase):
    def stop(self, code):
        return self.assertRaisesRegex(n0.N0Stop, "^" + code + "$")

    def test_import_is_inert(self):
        isolated = importlib.util.module_from_spec(SPEC)
        with mock.patch.object(Path, "open", side_effect=AssertionError("file access")), \
                mock.patch.object(builtins, "open", side_effect=AssertionError("file access")):
            SPEC.loader.exec_module(isolated)

    def test_excluded_rows_access_selectors_only(self):
        for phase, cross in (("select", "False"), ("select", "True"), ("fit", "True")):
            row, accesses = fixture(phase=phase, legal_fit="False", cross_phase_context=cross), []
            def guarded(name):
                self.assertIn(name, n0.SELECTORS)
                accesses.append(name)
                return row[name]
            selectors, payload = n0.select_fit(guarded)
            self.assertEqual(set(accesses), set(n0.SELECTORS))
            self.assertEqual(selectors["phase"], phase)
            self.assertIsNone(payload)

    def test_contradictions_stop_before_payload(self):
        for values in ({"phase": "select"}, {"cross_phase_context": "True"}, {"legal_fit": "False"}):
            row, accesses = fixture(**values), []
            def guarded(name):
                self.assertIn(name, n0.SELECTORS)
                accesses.append(name)
                return row[name]
            with self.stop("SELECTOR_CONTRADICTION"):
                n0.select_fit(guarded)
            self.assertEqual(set(accesses), set(n0.SELECTORS))

    def test_selector_schema(self):
        for key, value, code in (("uid", "", "EMPTY_UID"), ("phase", "report", "PHASE_DRIFT"),
                                 ("legal_fit", "true", "SELECTOR_BOOL_DRIFT")):
            with self.stop(code):
                n0.select_fit(fixture(**{key: value}).__getitem__)

    def test_legal_projection(self):
        row = fixture()
        selectors, payload = n0.select_fit(row.__getitem__)
        self.assertEqual(selectors, {key: row[key] for key in n0.SELECTORS})
        self.assertEqual(payload, {key: row[key] for key in n0.F1_PAYLOAD})

    def test_csv_quoting_newline_and_excluded_sentinel(self):
        legal = fixture(source_group='source, "quoted"\ncontinued')
        excluded = fixture("select-2", phase="select", legal_fit="False", source_group="PRIVATE_SENTINEL")
        rows, audit = scan(gzip.compress(encoded([legal, excluded])), compressed=True)
        self.assertEqual(rows[0]["source_group"], legal["source_group"])
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps([rows, audit]))
        self.assertEqual((len(rows), audit["nonfit_research_rows_retained"]), (1, 0))
        self.assertEqual(audit["column_value_accesses"]["source_group"], 1)
        self.assertEqual(audit["column_value_accesses"]["uid"], 2)
        self.assertEqual(audit["nonfit_cells_transiently_tokenized"], len(n0.F1_PAYLOAD))

    def test_strict_headers(self):
        columns = list(n0.F1_COLUMNS)
        for header in (columns[:-1], columns + ["extra"], columns[:-1] + [columns[0]], columns[::-1]):
            with self.stop("CSV_HEADER_DRIFT"):
                scan(encoded([], header))

    def test_ragged_rows(self):
        row = [fixture()[key] for key in n0.F1_COLUMNS]
        for cells in (row[:-1], row + ["extra"]):
            with self.stop("CSV_ROW_WIDTH_DRIFT"):
                scan(encoded([cells]))

    def test_broken_csv_and_encoding_fail_closed(self):
        for suffix in (b'"unterminated\n', b'\xff\n'):
            with self.stop("N0_NEEDS_GOVERNED_EXPORT"):
                scan(encoded([]) + suffix)

    def test_duplicate_uids_include_excluded_rows(self):
        for second in (fixture(), fixture(phase="select", legal_fit="False")):
            with self.stop("DUPLICATE_UID"):
                scan(encoded([fixture(), second]))
        with self.stop("DUPLICATE_JOIN_KEY"):
            n0.unique([{"uid": "x"}, {"uid": "x"}], "uid")

    def test_manifest_paths_and_duplicates(self):
        sha = "a" * 64
        self.assertEqual(n0.parse_manifest((sha + "  nested/ok.json\n").encode()), {"nested/ok.json": sha})
        for name in ("../escape", "/absolute", "nested/../../escape"):
            with self.stop("MANIFEST_PATH_DRIFT"):
                n0.parse_manifest((sha + "  " + name + "\n").encode())
        with self.stop("MANIFEST_PATH_DRIFT"):
            n0.parse_manifest(((sha + "  repeated\n") * 2).encode())
        with self.stop("MANIFEST_SCHEMA_DRIFT"):
            n0.parse_manifest((sha + "  C:\\escape\n").encode())

    def test_input_identity_authorization_and_single_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture").write_bytes(b"synthetic")
            inputs = n0.Inputs(root, {"fixture": n0.digest(b"synthetic")}, n0.Budget(lambda: 0, lambda: 0))
            with self.stop("UNAUTHORIZED_OR_REPEAT_INPUT"):
                inputs.read("unauthorized")
            self.assertEqual(inputs.read("fixture"), b"synthetic")
            with self.stop("UNAUTHORIZED_OR_REPEAT_INPUT"):
                inputs.read("fixture")
            drift = n0.Inputs(root, {"fixture": "0" * 64}, n0.Budget(lambda: 0, lambda: 0))
            with self.stop("INPUT_IDENTITY_DRIFT"):
                drift.read("fixture")
            with mock.patch.dict(n0.CAPS, input_file_bytes=1), self.stop("INPUT_SIZE_STOP"):
                n0.Inputs(root, inputs.pins, inputs.budget).read("fixture")

    def test_resource_caps(self):
        times = iter([0, n0.CAPS["wall_seconds"] + 1])
        with self.stop("WALL_CAP_STOP"):
            n0.Budget(lambda: 0, lambda: next(times)).check()
        with self.stop("RAM_CAP_STOP"):
            n0.Budget(lambda: n0.CAPS["ram_bytes"] + 1, lambda: 0).check()
        budget = n0.Budget(lambda: 0, lambda: 0)
        budget.output_bytes = n0.CAPS["output_bytes"] + 1
        with self.stop("OUTPUT_CAP_STOP"):
            budget.check()
        for cap, code in (("physical_line_bytes", "LINE_CAP_STOP"),
                          ("decompressed_table_bytes", "DECOMPRESSED_CAP_STOP")):
            with mock.patch.dict(n0.CAPS, {cap: 1}), self.stop(code):
                scan(encoded([fixture()]))
        with self.stop("ROW_CAP_STOP"):
            scan(encoded([fixture()]), row_cap=0)

    def test_saved_census_serialized_categories(self):
        categories = {"train": {"A1C": 2, "B0N": 1}}
        contexts = {("train", "A1C"): {"a"}, ("train", "B0N"): {"b"}}
        saved = [{"nested_split": "train", "category": name, "targets": count, "contexts": "1"}
                 for name, count in (("a_protected_attack", "2"), ("b_benign", "1"))]
        n0.validate_saved_census(saved, categories, contexts)
        for changed in (saved[:1], saved + saved[:1], [dict(saved[0], targets="3"), saved[1]],
                        [dict(saved[0], category="A1C"), saved[1]]):
            with self.assertRaises(n0.N0Stop):
                n0.validate_saved_census(changed, categories, contexts)

    def test_scope_exact_identity(self):
        parent = {"u": {"nested_split": "train", "source_group": "source", "owner": "A", "context_key": "ctx"}}
        row = {"uid": "u", "split": "train", "source": "source", "owner": "A", "context": "ctx"}
        n0.validate_scope([row], parent)
        for changed in ([], [row, row], *[[dict(row, **{key: "drift"})] for key in row]):
            with self.assertRaises(n0.N0Stop):
                n0.validate_scope(changed, parent)

    def test_context_key_grammar(self):
        parts = ("source/member.jsonl", "a" * 64, "0")
        self.assertEqual(n0.parse_context_key("\x1f".join(parts)), parts)
        for value in ("member", "\x1f".join(("", parts[1], "0")), "\x1f".join((parts[0], "A" * 64, "0")),
                      "\x1f".join((parts[0], parts[1], "01")), "\x1f".join((*parts, "extra"))):
            with self.assertRaises(n0.N0Stop):
                n0.parse_context_key(value)


def main():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(N0ContractTests))
    receipt = {"pass": result.wasSuccessful() and result.testsRun > 0, "tests": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "synthetic_only": True,
               "implementation_sha256": n0.digest(IMPLEMENTATION.read_bytes()),
               "tests_sha256": n0.digest(Path(__file__).read_bytes()),
               "contract_sha256": n0.digest((n0.ROOT / n0.CONTRACT).read_bytes()), "real_metadata_reads": 0}
    output = n0.ROOT / n0.ACCEPTANCE
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(n0.json_bytes(receipt))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
