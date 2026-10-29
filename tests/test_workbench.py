import csv
import hashlib
import json
import subprocess
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from artifactcheck import check_artifacts, validate_contract
from common import Table, numeric_summary, number, read_json, read_table
from tablecheck import check_table, compare_tables


def table(text, suffix=".csv"):
    with patch.object(Path, "read_bytes", return_value=text.encode("utf-8")):
        return read_table(Path("input" + suffix))


class TableTests(unittest.TestCase):
    def test_bom_quoted_newline_and_unicode(self):
        data = table('\ufeffid,note,value\n1,"가,나\n다",0.10\n')
        self.assertEqual(data.rows, [("1", "가,나\n다", "0.10")])

    def test_tsv_and_blank_physical_lines(self):
        data = table("id\tvalue\n\na\t2\n", ".tsv")
        self.assertEqual(data.rows, [("a", "2")])
        self.assertEqual(data.blank_lines, 1)

    def test_invalid_csv_is_rejected(self):
        for text in ("", "id,id\n1,2\n", "id,\n1,2\n", "id,value\n1\n", 'id,value\n1,"open'):
            with self.subTest(text=text), self.assertRaises((ValueError, csv.Error)):
                table(text)

    def test_decimal_totals_are_exact(self):
        result = numeric_summary(["10000000000000000000000000000.10", "0.20"])
        self.assertEqual(result["valid_value_sum"], "10000000000000000000000000000.30")
        self.assertEqual(numeric_summary(["0.1", "0.2"])["valid_value_sum"], "0.3")

    def test_unsupported_numeric_values(self):
        for value in ("NaN", "Infinity", "1_000", "1,000", "$2", "1e1001", "١٢"):
            with self.subTest(value=value):
                self.assertIsNone(number(value))
        self.assertEqual(number(" -1.25e2 "), Decimal("-125"))

    def test_missing_and_invalid_values_are_not_zero(self):
        result = numeric_summary(["", "bad", "  "])
        self.assertIsNone(result["valid_value_sum"])
        self.assertEqual(result["missing_count"], 2)
        self.assertEqual(result["invalid_count"], 1)
        self.assertEqual(numeric_summary([])["valid_value_sum"], "0")

    def test_checks_need_explicit_constraints(self):
        with self.assertRaises(ValueError):
            check_table(table("id\na\n"))

    def test_required_key_and_numeric_failures(self):
        data = read_table(ROOT / "practice" / "raw.csv")
        result = check_table(data, required=["amount"], keys=["order_id"], numeric=["amount"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["keys"]["duplicate_excess"], 1)
        self.assertEqual(result["numeric"]["amount"]["invalid_count"], 1)
        self.assertEqual(result["missing"]["amount"], 1)

    def test_numeric_nullable_and_nonnegative_are_separate_policies(self):
        data = table("id,amount\na,\nb,-1\n")
        self.assertTrue(check_table(data, numeric=["amount"])["passed"])
        self.assertFalse(check_table(data, required=["amount"])["passed"])
        self.assertFalse(check_table(data, nonnegative=["amount"])["passed"])

    def test_composite_keys_preserve_identifiers(self):
        data = table("id,line\n01,a\n1,a\n01,b\n")
        self.assertTrue(check_table(data, keys=["id", "line"])["passed"])
        self.assertFalse(check_table(table("id\na\n \n"), keys=["id"])["passed"])

    def test_empty_data_requires_explicit_zero_rows(self):
        data = table("id\n")
        self.assertFalse(check_table(data, required=["id"])["passed"])
        self.assertTrue(check_table(data, expect_rows=0)["passed"])
        with self.assertRaises(ValueError):
            check_table(data, expect_rows=-1)

    def test_unknown_column_is_not_a_pass(self):
        with self.assertRaises(ValueError):
            check_table(table("id\na\n"), required=["typo"])

    def test_real_fixture_comparison(self):
        before = read_table(ROOT / "practice" / "raw.csv")
        after = read_table(ROOT / "practice" / "candidate.csv")
        result = compare_tables(before, after, numeric=["amount"], keys=["order_id"], groups=["region"])
        self.assertEqual(result["row_multiset"], {"removed": 3, "added": 0, "unchanged": 4})
        self.assertEqual(result["numeric_delta"]["amount"], "-200.20")
        west = next(item for item in result["groups"] if item["group"]["region"] == "West")
        self.assertEqual(west["numeric_before"]["amount"]["invalid_count"], 1)
        self.assertEqual(west["numeric_before"]["amount"]["missing_count"], 1)
        self.assertEqual(Decimal(west["numeric_delta"]["amount"]), Decimal(0))

    def test_removed_and_added_groups(self):
        result = compare_tables(table("group,value\na,2\n"), table("group,value\nb,3\n"), numeric=["value"], groups=["group"])
        self.assertEqual([item["numeric_delta"]["value"] for item in result["groups"]], ["-2", "3"])

    def test_delta_keeps_more_than_28_digits(self):
        before = table("n\n10000000000000000000000000000.10\n")
        after = table("n\n10000000000000000000000000000.30\n")
        self.assertEqual(compare_tables(before, after, numeric=["n"])["numeric_delta"]["n"], "0.20")

    def test_updated_row_does_not_remove_its_key(self):
        result = compare_tables(table("id,n\na,1\n"), table("id,n\na,2\n"), numeric=["n"], keys=["id"])
        self.assertEqual(result["row_multiset"]["removed"], 1)
        self.assertEqual(result["key_multiset"], {"removed": 0, "added": 0})

    def test_invalid_side_has_no_numeric_delta(self):
        result = compare_tables(table("n\nbad\n"), table("n\n2\n"), numeric=["n"])
        self.assertIsNone(result["numeric_delta"]["n"])

    def test_header_order_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            compare_tables(table("a,b\n1,2\n"), table("b,a\n2,1\n"))


class FileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = ROOT / "work" / ("tests-" + uuid.uuid4().hex[:10])
        cls.work.mkdir(parents=True)
        (cls.work / "valid.json").write_text('{"summary": 1}', encoding="utf-8")
        (cls.work / "valid.csv").write_text("id,value\na,1\n", encoding="utf-8")
        (cls.work / "empty.txt").write_text("", encoding="utf-8")

    def test_declared_artifacts_pass(self):
        contract = {"artifacts": [
            {"path": "valid.json", "kind": "json", "required_keys": ["summary"]},
            {"path": "valid.csv", "kind": "csv", "columns": ["id"], "min_rows": 1}]}
        self.assertTrue(check_artifacts(self.work, contract)["passed"])

    def test_artifact_hash_tracks_the_validated_content(self):
        paths = (self.work / "content-a.txt", self.work / "content-b.txt")
        for path, text in zip(paths, ("A", "B")):
            path.write_text(text, encoding="utf-8")
        hashes = []
        for path in paths:
            report = check_artifacts(self.work, {"artifacts": [{"path": path.name, "kind": "file"}]})
            info = report["checks"][0]
            self.assertEqual(info["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            hashes.append(info["sha256"])
        self.assertNotEqual(*hashes)

    def test_missing_empty_and_wrong_content_fail(self):
        for item in ({"path": "missing", "kind": "file"}, {"path": "empty.txt", "kind": "file"},
                     {"path": "valid.csv", "kind": "json"},
                     {"path": "valid.json", "kind": "json", "required_keys": ["missing"]},
                     {"path": "valid.csv", "kind": "csv", "columns": ["missing"]}):
            with self.subTest(item=item):
                self.assertFalse(check_artifacts(self.work, {"artifacts": [item]})["passed"])

    def test_invalid_contracts_are_rejected(self):
        cases = [{}, {"artifacts": []}, {"artifacts": [{"path": "x", "kind": []}]},
                 {"artifacts": [{"path": "x", "kind": "file", "min_bytes": True}]},
                 {"artifacts": [{"path": "x", "kind": "csv", "min_rows": 2, "max_rows": 1}]},
                 {"artifacts": [{"path": "x", "kind": "json", "required_keys": "name"}]},
                 {"artifacts": [{"path": "x", "kind": "file", "min_byte": 2}]},
                 {"artifacts": [{"path": "x", "kind": "json", "types": {"x": "typo"}}]}]
        for contract in cases:
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                validate_contract(contract)

    def test_json_declared_types_and_missing_fields(self):
        item = {"path": "valid.json", "kind": "json", "types": {"summary": "number"}}
        self.assertTrue(check_artifacts(self.work, {"artifacts": [item]})["passed"])
        for types in ({"summary": "array"}, {"missing": "string"}):
            self.assertFalse(check_artifacts(self.work, {"artifacts": [{**item, "types": types}]})["passed"])
        path = self.work / "boolean.json"
        path.write_text('{"summary":true}', encoding="utf-8")
        self.assertFalse(check_artifacts(self.work, {"artifacts": [{**item, "path": "boolean.json"}]})["passed"])

    def test_path_escape_and_aliases_are_rejected(self):
        for path in ("../outside", "a/../../outside", "C:\\outside", "\\\\server\\share\\file", "/outside"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_contract({"artifacts": [{"path": path, "kind": "file"}]})
        with self.assertRaises(ValueError):
            validate_contract({"artifacts": [{"path": "a/./x", "kind": "file"}, {"path": "a/x", "kind": "file"}]})

    def test_resolved_escape_is_rejected(self):
        outside = self.work.parent / "outside.txt"
        with patch("artifactcheck.Path.resolve", side_effect=[self.work, outside]):
            with self.assertRaises(ValueError):
                check_artifacts(self.work, {"artifacts": [{"path": "link", "kind": "file"}]})

    def test_json_duplicates_and_nonfinite_values_are_rejected(self):
        for i, text in enumerate(('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}')):
            path = self.work / f"bad-{i}.json"
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_json(path)
        path = self.work / "large.json"
        path.write_text('{"a":1e9999}', encoding="utf-8")
        self.assertTrue(read_json(path)["a"].is_finite())

    def cli(self, tool, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools" / tool), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", timeout=15)

    def test_cli_exit_codes_and_input_preservation(self):
        path = ROOT / "practice" / "raw.csv"
        original = hashlib.sha256(path.read_bytes()).hexdigest()
        observed = self.cli("tablecheck.py", "inspect", path, "--numeric", "amount")
        failed = self.cli("tablecheck.py", "check", path, "--key", "order_id")
        misconfigured = self.cli("tablecheck.py", "check", path)
        self.assertEqual(observed.returncode, 0, observed.stderr)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertFalse(json.loads(failed.stdout)["passed"])
        self.assertEqual(misconfigured.returncode, 2)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), original)

    def test_oversized_json_number_does_not_abort_later_checks(self):
        path = self.work / "oversized.json"
        path.write_text('{"value":1e999999999999999999999999}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_json(path)
        report = check_artifacts(self.work, {"artifacts": [
            {"path": "oversized.json", "kind": "json"}, {"path": "valid.json", "kind": "json"}]})
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["checks"]), 2)
        self.assertTrue(report["checks"][1]["passed"])
        result = self.cli("artifactcheck.py", path, "--workspace", self.work)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))

    def test_existing_report_is_not_overwritten(self):
        output = self.work / "keep.json"
        output.write_text("keep this", encoding="utf-8")
        result = self.cli("tablecheck.py", "inspect", self.work / "valid.csv", "--output", output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep this")

    def test_cli_artifact_contract_exit_codes(self):
        contract = self.work / "contract.json"
        contract.write_text(json.dumps({"artifacts": [{"path": "valid.json", "kind": "json"}]}), encoding="utf-8")
        self.assertEqual(self.cli("artifactcheck.py", contract, "--workspace", self.work).returncode, 0)
        contract.write_text(json.dumps({"artifacts": [{"path": "missing.json", "kind": "json"}]}), encoding="utf-8")
        self.assertEqual(self.cli("artifactcheck.py", contract, "--workspace", self.work).returncode, 1)
        contract.write_text('{"artifacts":[]}', encoding="utf-8")
        self.assertEqual(self.cli("artifactcheck.py", contract, "--workspace", self.work).returncode, 2)


if __name__ == "__main__":
    unittest.main()
