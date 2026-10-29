import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal

from common import Table, column_indexes, emit, exact_sum, key_counts, read_table, table_summary, utf8_console


def inspect_table(table, numeric=(), keys=()):
    return {"command": "inspect", **table_summary(table, numeric, keys)}


def check_table(table, required=(), keys=(), numeric=(), nonnegative=(), expect_rows=None):
    if not (required or keys or numeric or nonnegative or expect_rows is not None):
        raise ValueError("Configure at least one check")
    if expect_rows is not None and expect_rows < 0:
        raise ValueError("Expected row count cannot be negative")
    columns = list(dict.fromkeys([*numeric, *nonnegative]))
    report = table_summary(table, columns, keys)
    checks = []
    if not table.rows and expect_rows != 0:
        checks.append({"name": "data_rows_present", "passed": False})
    for name, index in zip(required, column_indexes(table, required)):
        missing = sum(not row[index].strip() for row in table.rows)
        checks.append({"name": "required", "column": name, "missing_rows": missing, "passed": missing == 0})
    if keys:
        info = report["keys"]
        checks.append({"name": "complete_unique_key", **info,
                       "passed": info["missing_rows"] == 0 and info["duplicate_excess"] == 0})
    for name in columns:
        info = report["numeric"][name]
        checks.append({"name": "numeric_nonblank_values", "column": name,
                       "invalid_rows": info["invalid_count"], "passed": info["invalid_count"] == 0})
        if name in nonnegative:
            checks.append({"name": "nonnegative", "column": name,
                           "negative_rows": info["negative_count"], "passed": info["negative_count"] == 0})
    if expect_rows is not None:
        checks.append({"name": "row_count", "expected": expect_rows, "actual": len(table.rows),
                       "passed": len(table.rows) == expect_rows})
    return {"command": "check", **report, "checks": checks, "passed": all(item["passed"] for item in checks)}


def numeric_delta(before, after):
    result = {}
    for name in before:
        left = before[name]["valid_value_sum"]
        right = after[name]["valid_value_sum"]
        result[name] = str(exact_sum([Decimal(right), Decimal(left).copy_negate()])) if left is not None and right is not None else None
    return result


def compare_tables(before, after, numeric=(), keys=(), groups=()):
    if before.columns != after.columns:
        raise ValueError("Before and after must have identical headers in the same order")
    left = table_summary(before, numeric, keys)
    right = table_summary(after, numeric, keys)
    left_rows, right_rows = Counter(before.rows), Counter(after.rows)
    result = {"command": "compare", "before": left, "after": right,
              "row_count_delta": len(after.rows) - len(before.rows),
              "row_multiset": {"removed": sum((left_rows - right_rows).values()),
                               "added": sum((right_rows - left_rows).values()),
                               "unchanged": sum((left_rows & right_rows).values())},
              "numeric_delta": numeric_delta(left["numeric"], right["numeric"])}
    if keys:
        left_keys, _ = key_counts(before, keys)
        right_keys, _ = key_counts(after, keys)
        result["key_multiset"] = {"removed": sum((left_keys - right_keys).values()),
                                  "added": sum((right_keys - left_keys).values())}
    if groups:
        indexes = column_indexes(before, groups)
        buckets = []
        for table in (before, after):
            grouped_rows = defaultdict(list)
            for row in table.rows:
                grouped_rows[tuple(row[i] for i in indexes)].append(row)
            buckets.append(grouped_rows)
        grouped = []
        group_keys = sorted(buckets[0].keys() | buckets[1].keys())
        for key in group_keys:
            summaries = []
            for table, groups_by_key in zip((before, after), buckets):
                rows = groups_by_key.get(key, [])
                subset = Table(table.name, table.sha256, table.columns, rows)
                summaries.append(table_summary(subset, numeric))
            a, b = summaries
            grouped.append({"group": dict(zip(groups, key)), "rows_before": a["row_count"],
                            "rows_after": b["row_count"], "numeric_before": a["numeric"],
                            "numeric_after": b["numeric"], "numeric_delta": numeric_delta(a["numeric"], b["numeric"])})
        result["groups"] = grouped
    return result


def main(argv=None):
    utf8_console()
    parser = argparse.ArgumentParser(description="Inspect CSV/TSV data and check explicit constraints without changing inputs.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "check", "compare"):
        part = commands.add_parser(name)
        part.add_argument("file")
        if name == "compare":
            part.add_argument("after")
            part.add_argument("--group", action="append", default=[])
        part.add_argument("--numeric", action="append", default=[])
        part.add_argument("--key", action="append", default=[])
        part.add_argument("--delimiter")
        part.add_argument("--encoding", default="utf-8-sig")
        part.add_argument("--output")
        if name == "check":
            part.add_argument("--required", action="append", default=[])
            part.add_argument("--nonnegative", action="append", default=[])
            part.add_argument("--expect-rows", type=int)
    args = parser.parse_args(argv)
    try:
        table = read_table(args.file, args.delimiter, args.encoding)
        if args.command == "inspect":
            report = inspect_table(table, args.numeric, args.key)
        elif args.command == "check":
            report = check_table(table, args.required, args.key, args.numeric, args.nonnegative, args.expect_rows)
        else:
            after = read_table(args.after, args.delimiter, args.encoding)
            report = compare_tables(table, after, args.numeric, args.key, args.group)
        emit(report, args.output)
        return 1 if report.get("passed") is False else 0
    except (OSError, ValueError, csv.Error, UnicodeError, LookupError) as error:
        sys.stderr.write(json.dumps({"error": str(error)}, ensure_ascii=False) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
