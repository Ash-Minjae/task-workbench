import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path


@dataclass
class Table:
    name: str
    sha256: str
    columns: list
    rows: list
    blank_lines: int = 0


def read_table(path, delimiter=None, encoding="utf-8-sig", raw=None):
    path = Path(path)
    if raw is None:
        raw = path.read_bytes()
    separator = delimiter if delimiter is not None else ("\t" if path.suffix.lower() == ".tsv" else ",")
    if len(separator) != 1 or separator in "\r\n":
        raise ValueError("Delimiter must be one character other than a newline")
    reader = csv.reader(io.StringIO(raw.decode(encoding), newline=""), delimiter=separator, strict=True)
    columns = next(reader, None)
    if not columns or any(not name.strip() for name in columns):
        raise ValueError("CSV needs a nonblank header for every column")
    if len(set(columns)) != len(columns):
        raise ValueError("CSV has duplicate column names")
    rows = []
    blanks = 0
    for row in reader:
        if not row:
            blanks += 1
            continue
        if len(row) != len(columns):
            raise ValueError(f"CSV line {reader.line_num}: expected {len(columns)} fields, found {len(row)}")
        rows.append(tuple(row))
    return Table(path.name, hashlib.sha256(raw).hexdigest(), columns, rows, blanks)


def column_indexes(table, names):
    missing = [name for name in names if name not in table.columns]
    if missing:
        raise ValueError("Unknown columns: " + ", ".join(missing))
    return [table.columns.index(name) for name in names]


def number(value):
    text = value.strip()
    if not text or len(text) > 4096 or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
        return None
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    if not result.is_finite() or abs(result.as_tuple().exponent) > 1000 or len(result.as_tuple().digits) > 2000:
        return None
    return result


def exact_sum(values):
    if not values:
        return Decimal(0)
    digits_left = max(1, max(value.adjusted() + 1 for value in values))
    scale = max(0, -min(value.as_tuple().exponent for value in values))
    with localcontext() as ctx:
        ctx.prec = digits_left + scale + len(str(len(values))) + 2
        return sum(values, Decimal(0))


def numeric_summary(raw_values):
    values = []
    missing = invalid = negative = 0
    for raw in raw_values:
        if not raw.strip():
            missing += 1
            continue
        value = number(raw)
        if value is None:
            invalid += 1
        else:
            values.append(value)
            negative += value < 0
    total = str(exact_sum(values)) if values or not raw_values else None
    return {"valid_count": len(values), "missing_count": missing, "invalid_count": invalid,
            "negative_count": negative, "valid_value_sum": total,
            "min": str(min(values)) if values else None, "max": str(max(values)) if values else None}


def key_counts(table, keys):
    indexes = column_indexes(table, keys)
    counts = Counter()
    missing = 0
    for row in table.rows:
        key = tuple(row[index] for index in indexes)
        if any(not value.strip() for value in key):
            missing += 1
        else:
            counts[key] += 1
    return counts, missing


def table_summary(table, numeric=(), keys=()):
    indexes = column_indexes(table, numeric)
    result = {"input": {"name": table.name, "sha256": table.sha256}, "row_count": len(table.rows),
              "columns": table.columns, "blank_lines_skipped": table.blank_lines,
              "missing": {name: sum(not row[i].strip() for row in table.rows) for i, name in enumerate(table.columns)},
              "duplicate_row_excess": sum(count - 1 for count in Counter(table.rows).values()),
              "numeric": {name: numeric_summary([row[i] for row in table.rows]) for name, i in zip(numeric, indexes)}}
    if keys:
        counts, missing = key_counts(table, keys)
        result["keys"] = {"columns": list(keys), "missing_rows": missing,
                          "duplicate_groups": sum(count > 1 for count in counts.values()),
                          "duplicate_excess": sum(count - 1 for count in counts.values())}
    return result


def emit(payload, output=None):
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        with Path(output).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)


def reject_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON key: {name}")
        result[name] = value
    return result


def parse_json(text):
    try:
        return json.loads(text,
                          parse_constant=reject_constant, parse_float=Decimal, object_pairs_hook=unique_object)
    except InvalidOperation as error:
        raise ValueError("JSON number exceeds the supported decimal range") from error


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def utf8_console():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
