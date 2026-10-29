import argparse
import csv
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path, PurePosixPath, PureWindowsPath

from common import emit, parse_json, read_table, utf8_console


def validate_contract(contract):
    if not isinstance(contract, dict) or set(contract) != {"artifacts"}:
        raise ValueError("Contract must contain only an artifacts list")
    items = contract["artifacts"]
    if not isinstance(items, list) or not items:
        raise ValueError("Contract needs at least one artifact")
    seen = set()
    options = {"file": {"path", "kind", "min_bytes"},
               "json": {"path", "kind", "min_bytes", "required_keys", "types"},
               "csv": {"path", "kind", "min_bytes", "columns", "min_rows", "max_rows"}}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str) or item["kind"] not in options:
            raise ValueError("Every artifact needs a supported kind: file, json, csv")
        if set(item) - options[item["kind"]]:
            raise ValueError("Unknown artifact option")
        path = item.get("path")
        if not isinstance(path, str) or not path.strip() or "\x00" in path:
            raise ValueError("Artifact path must be a nonblank relative path")
        windows = PureWindowsPath(path)
        if Path(path).is_absolute() or windows.drive or windows.root:
            raise ValueError("Artifact path cannot be absolute")
        normalized = path.replace("\\", "/")
        normalized = str(PurePosixPath(normalized))
        if ".." in normalized.split("/") or normalized in seen:
            raise ValueError("Artifact paths cannot traverse parents or repeat")
        seen.add(normalized)
        for field in ("min_bytes", "min_rows", "max_rows"):
            if field in item and (type(item[field]) is not int or item[field] < 0):
                raise ValueError(f"{field} must be a nonnegative integer")
        if item.get("min_rows", 0) > item.get("max_rows", float("inf")):
            raise ValueError("min_rows cannot exceed max_rows")
        for field in ("columns", "required_keys"):
            if field in item and (not isinstance(item[field], list) or
                                  any(not isinstance(name, str) or not name.strip() for name in item[field])):
                raise ValueError(f"{field} must be a list of nonblank strings")
        if "types" in item:
            types = item["types"]
            names = {"object", "array", "string", "number", "boolean", "null"}
            if not isinstance(types, dict) or any(not isinstance(key, str) or not key.strip() or
                                                  not isinstance(value, str) or value not in names for key, value in types.items()):
                raise ValueError("types must map top-level field names to supported JSON types")
    return items


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, Decimal)):
        return "number"
    return {dict: "object", list: "array", str: "string"}[type(value)]


def check_artifacts(workspace, contract):
    root = Path(workspace).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Workspace must be a directory")
    items = validate_contract(contract)
    checks = []
    seen = set()
    for item in items:
        relative = item["path"].replace("\\", "/")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Artifact resolves outside the workspace")
        if path in seen:
            raise ValueError("Multiple artifacts resolve to the same file")
        seen.add(path)
        problems = []
        info = {"path": relative, "kind": item["kind"]}
        if not path.is_file():
            problems.append("missing_file")
        else:
            raw = path.read_bytes()
            size = len(raw)
            info["bytes"] = size
            info["sha256"] = hashlib.sha256(raw).hexdigest()
            if size < item.get("min_bytes", 1):
                problems.append("file_too_small")
            try:
                if item["kind"] == "json":
                    payload = parse_json(raw.decode("utf-8-sig"))
                    if "required_keys" in item or "types" in item:
                        if not isinstance(payload, dict):
                            problems.append("json_object_required")
                        else:
                            required = list(dict.fromkeys([*item.get("required_keys", []), *item.get("types", {})]))
                            missing = [name for name in required if name not in payload]
                            if missing:
                                info["missing_keys"] = missing
                                problems.append("missing_json_keys")
                            mismatched = {name: {"expected": expected, "actual": json_type(payload[name])}
                                          for name, expected in item.get("types", {}).items()
                                          if name in payload and json_type(payload[name]) != expected}
                            if mismatched:
                                info["type_mismatches"] = mismatched
                                problems.append("wrong_json_types")
                elif item["kind"] == "csv":
                    table = read_table(path, raw=raw)
                    info["rows"] = len(table.rows)
                    if set(item.get("columns", [])) - set(table.columns):
                        problems.append("missing_csv_columns")
                    if len(table.rows) < item.get("min_rows", 0) or len(table.rows) > item.get("max_rows", float("inf")):
                        problems.append("row_count_out_of_range")
            except (ValueError, UnicodeError, csv.Error) as error:
                problems.append("invalid_content")
                info["error"] = str(error)
        checks.append({**info, "passed": not problems, "problems": problems})
    return {"checks": checks, "passed": all(item["passed"] for item in checks)}


def main(argv=None):
    utf8_console()
    parser = argparse.ArgumentParser(description="Check explicitly declared output files and formats.")
    parser.add_argument("contract")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        raw_contract = Path(args.contract).read_bytes()
        contract = parse_json(raw_contract.decode("utf-8-sig"))
        report = check_artifacts(args.workspace, contract)
        report["contract"] = {"name": Path(args.contract).name, "sha256": hashlib.sha256(raw_contract).hexdigest()}
        emit(report, args.output)
        return 0 if report["passed"] else 1
    except (OSError, ValueError, UnicodeError) as error:
        sys.stderr.write(json.dumps({"error": str(error)}, ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
