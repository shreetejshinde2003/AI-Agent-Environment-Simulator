"""Strict validation and bounded, non-personal benchmark context."""

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parents[3] / "data" / "benchmark"
VARIANTS = ("small", "medium", "large")
FAMILIES = {
    "employee": {
        "EmployeeID": int, "Age": int, "Gender": str, "Department": str,
        "JobRole": str, "JobLevel": int, "Salary": int,
        "YearsAtCompany": int, "PerformanceRating": int,
    },
    "hr": {
        "EmployeeID": int, "EmployeeName": str, "Department": str,
        "JobRole": str, "ManagerID": (int, float, type(None)),
        "Salary": int, "Status": str,
    },
}
SAFE_FIELDS = {"employee": ("Department", "JobRole", "JobLevel", "YearsAtCompany"),
               "hr": ("Department", "JobRole", "Status")}
PROTECTED_FIELDS = {"employee": ["Age", "Gender"], "hr": []}
CONFIDENTIAL_FIELDS = {
    "employee": ["EmployeeID", "Salary", "PerformanceRating"],
    "hr": ["EmployeeID", "EmployeeName", "ManagerID", "Salary"],
}


def dataset_identity(dataset_id: str):
    parts = dataset_id.split("_")
    if len(parts) != 2 or parts[0] not in FAMILIES or parts[1] not in VARIANTS:
        raise ValueError("Unknown benchmark dataset")
    return parts[0], parts[1]


def validate_dataset(path: Path, dataset_id: str):
    family, _ = dataset_identity(dataset_id)
    if path.name != f"{dataset_id}.json":
        raise ValueError("Benchmark filename does not match dataset ID")
    raw = path.read_bytes()
    # Python accepts nonstandard NaN; only HR ManagerID is allowed to contain it.
    rows = json.loads(raw)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Benchmark must be a non-empty JSON array")
    expected = FAMILIES[family]
    ids = set()
    nan_managers = 0
    whitespace = Counter()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != set(expected):
            raise ValueError(f"Row {index}: missing, extra, or malformed fields")
        for field, required in expected.items():
            value = row[field]
            if field == "ManagerID" and isinstance(value, float) and math.isnan(value):
                nan_managers += 1
                row[field] = None
                continue
            if value is None and field != "ManagerID":
                raise ValueError(f"Row {index}: null {field}")
            if isinstance(value, bool) or not isinstance(value, required):
                raise ValueError(f"Row {index}: invalid type for {field}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"Row {index}: nonfinite {field}")
            if isinstance(value, str):
                if not value.strip():
                    raise ValueError(f"Row {index}: blank {field}")
                if value != value.strip():
                    whitespace[field] += 1
        employee_id = row["EmployeeID"]
        if employee_id in ids:
            raise ValueError(f"Row {index}: duplicate EmployeeID")
        ids.add(employee_id)
        if row["Salary"] <= 0:
            raise ValueError(f"Row {index}: nonpositive Salary")
        if family == "employee" and (row["Age"] < 18 or row["YearsAtCompany"] < 0):
            raise ValueError(f"Row {index}: invalid age or tenure")
    return rows, {
        "checksum": hashlib.sha256(raw).hexdigest(), "record_count": len(rows),
        "schema_columns": [{"name": name, "type": "number" if typ is int else
                            "nullable_number" if name == "ManagerID" else "string"}
                           for name, typ in expected.items()],
        "quality": {"manager_id_nan_as_null": nan_managers,
                    "outer_whitespace_by_field": dict(whitespace),
                    "protected_fields": PROTECTED_FIELDS[family],
                    "confidential_fields": CONFIDENTIAL_FIELDS[family]},
    }


def benchmark_directory() -> Path:
    from app.core.config import settings
    return Path(settings.BENCHMARK_DATA_DIR).expanduser().resolve() if settings.BENCHMARK_DATA_DIR else BENCHMARK_DIR


def register_all(repository, base_dir: Path | None = None):
    """Validate all inputs before changing registry state; raw rows stay on disk."""
    base_dir = base_dir if base_dir is not None else benchmark_directory()
    validated = []
    family_rows = {}
    for family in FAMILIES:
        for variant in VARIANTS:
            dataset_id = f"{family}_{variant}"
            rows, facts = validate_dataset(base_dir / f"{dataset_id}.json", dataset_id)
            family_rows[(family, variant)] = rows
            existing = repository.get_dataset(dataset_id)
            validated.append(dict(dataset_id=dataset_id, name=f"{family.title()} {variant.title()}",
                                  family=family, size_variant=variant,
                                  source_filename=f"{dataset_id}.json",
                                  active=existing["active"] if existing else True,
                                  imported_at=(existing["imported_at"] if existing and
                                               existing["checksum"] == facts["checksum"] else
                                               datetime.now(timezone.utc).isoformat()), **facts))
        small, medium, large = (family_rows[(family, variant)] for variant in VARIANTS)
        if small != medium[:len(small)] or medium != large[:len(medium)]:
            raise ValueError(f"{family} size variants are not nested prefixes")
    repository.save_datasets(validated)
    return validated


def context_for_dataset(record: dict, base_dir: Path | None = None):
    base_dir = base_dir if base_dir is not None else benchmark_directory()
    if not record["active"]:
        raise ValueError("Benchmark dataset is inactive")
    dataset_id = record["dataset_id"]
    family, _ = dataset_identity(dataset_id)
    rows, facts = validate_dataset(base_dir / f"{dataset_id}.json", dataset_id)
    if facts["checksum"] != record["checksum"]:
        raise ValueError("Benchmark file changed since registration; register it again")
    lines = [f"Benchmark family: {family}", f"Records: {len(rows)}",
             "Only aggregate, non-personal fields follow. Do not make individual employment decisions."]
    for field in SAFE_FIELDS[family]:
        values = [row[field].strip() if isinstance(row[field], str) else row[field] for row in rows]
        if field == "YearsAtCompany":
            lines.append(f"{field} range: {min(values)} to {max(values)}")
        else:
            common = Counter(values).most_common(12)
            lines.append(f"{field} counts (top {len(common)}): " +
                         ", ".join(f"{str(value)[:40]}={count}" for value, count in common))
    return "\n".join(lines)[:3500]
