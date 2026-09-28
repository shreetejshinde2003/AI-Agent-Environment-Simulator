# Phase 2 dataset audit

Audited the six user-supplied local JSON arrays on 2026-09-28 before designing
storage. Counts are records, not application simulations. No employment outcome
should be inferred from protected attributes.

| File | Family | Rows | Columns | Null/missing | Duplicate EmployeeID | Dirty values |
|---|---|---:|---|---:|---:|---|
| employee_small.json | employee | 294 | EmployeeID, Age, Gender, Department, JobRole, JobLevel, Salary, YearsAtCompany, PerformanceRating | 0 | 0 | 0 leading/trailing string spaces |
| employee_medium.json | employee | 735 | Same nine columns | 0 | 0 | 0 leading/trailing string spaces |
| employee_large.json | employee | 1470 | Same nine columns | 0 | 0 | 0 leading/trailing string spaces |
| hr_small.json | hr | 62 | EmployeeID, EmployeeName, Department, JobRole, ManagerID, Salary, Status | 0 JSON nulls | 0 | 3 nonstandard NaN ManagerIDs; 42 trailing Department spaces; 17 EmployeeName spaces |
| hr_medium.json | hr | 155 | Same seven columns | 0 JSON nulls | 0 | 5 NaN ManagerIDs; 106 Department spaces; 39 EmployeeName spaces |
| hr_large.json | hr | 311 | Same seven columns | 0 JSON nulls | 0 | 8 NaN ManagerIDs; 209 Department spaces; 70 EmployeeName spaces; 1 JobRole space |

`NaN` is an invalid JSON numeric literal accepted by Python's permissive parser.
Treat it as missing ManagerID after explicit validation, never as a finite ID.
Every non-NaN ManagerID is an integral float. None appears as EmployeeID in its
respective file; manager links cannot be resolved within the sample.

| File | Categorical distinct counts (trimmed) | Numeric ranges (min–max) |
|---|---|---|
| employee_small | Department 3, JobRole 9, Gender 2, JobLevel 5, PerformanceRating 2 | EmployeeID 1–401, Age 19–59, Salary 1102–19999, YearsAtCompany 0–40 |
| employee_medium | Department 3, JobRole 9, Gender 2, JobLevel 5, PerformanceRating 2 | EmployeeID 1–1019, Age 18–60, Salary 1009–19999, YearsAtCompany 0–40 |
| employee_large | Department 3, JobRole 9, Gender 2, JobLevel 5, PerformanceRating 2 | EmployeeID 1–2068, Age 18–60, Salary 1009–19999, YearsAtCompany 0–40 |
| hr_small | Department 5, JobRole 17, Status 3 | EmployeeID 10001–10294, Salary 47211–170500 |
| hr_medium | Department 6, JobRole 24, Status 3 | EmployeeID 10001–10311, Salary 45069–250000 |
| hr_large | Department 6, JobRole 31 (32 raw), Status 3 | EmployeeID 10001–10311, Salary 45046–250000 |

All EmployeeID values are unique within each file. No row omits a declared
column, no JSON `null` occurs, and no duplicate full rows were found. The only
missing-like values are the HR ManagerID `NaN` counts above. Department,
JobRole, Gender, Status, JobLevel and PerformanceRating are categorical or
ordinal; salary, age and tenure are numeric. IDs and ManagerID are numeric
identifiers, not continuous measurements.

## Types and keys

Employee: EmployeeID, Age, JobLevel, Salary, YearsAtCompany, PerformanceRating
are integers; Gender, Department, JobRole are strings. Department (3 unique),
JobRole (9), Gender (2), JobLevel (5), and PerformanceRating (2) are
categorical/ordinal. EmployeeID is the only suitable record key within this
family. Ages are 18–60, salary values 1009–19999, tenure 0–40; no age below 18,
nonpositive salary, or tenure greater than age was found. Zero tenure occurs in
44 large records and can be valid. Rating has only values 3–4, so it may be
imbalanced; no outcome/ground-truth label was validated.

HR: EmployeeID and Salary are integers; ManagerID is float or NaN; EmployeeName,
Department, JobRole, Status are strings. Department has 6 categories in the
large file; JobRole has 32 raw spellings but 31 after trim; Status has 3.
EmployeeID is the record key. EmployeeName happened to be unique in these files
but is identifying and unsuitable as a durable key. Salary is not reliably
unique. Nonpositive salary, duplicate full rows, and blank strings were not found.

There is no within-family column/type conflict across size variants. The two
families have different schemas: only EmployeeID, Department, JobRole, Salary
overlap. EmployeeID ranges are disjoint (employee 1–2068; hr 10001–10311),
and cross-family comparisons should use a family-qualified key.

## Relationship between size variants

Within **each** family, small is an exact row-for-row prefix and subset of
medium, and medium is an exact prefix and subset of large. All shared IDs have
identical complete records. Employee overlaps: 294 small/medium, 735
medium/large. HR overlaps: 62 small/medium, 155 medium/large. The six files
are two source datasets, each with three nested size variants. Do not combine
size variants into one corpus or treat them as independent train/test splits:
doing so would leak identical records across splits.

## Benchmark strategy and safe context

Use one canonical large file per family. Use its small/medium prefixes for
cost/latency scaling only. For model evaluation, derive **disjoint** development
and test IDs from the large file with a recorded seed and family-qualified IDs;
do not use small as train and medium as test. Record dataset checksum, size,
task type, execution mode, model, latency, tokens and outcome per experiment.
Evaluation scores remain unset until a separate metric and ground truth exist.

Only send minimal, aggregated, task-relevant statistics to agents. Department,
JobRole, JobLevel, tenure, and Status can be used as carefully bounded
aggregates. Exclude or redact EmployeeID, ManagerID, EmployeeName, row-level
Salary, Age and Gender from LLM context. Age and Gender are protected/sensitive
for employment decisions; salary and names are confidential employee data.
PerformanceRating is an employment assessment and should not be used for
individual ranking or hiring decisions. Do not ask agents to make individual
employment decisions from these datasets.

Keep raw JSON **out of Git by default** because the HR family contains names,
salary and manager linkage. Provision the six files privately into
`data/benchmark/` on each authorized development/benchmark host; no Google
Drive link is needed at runtime. The application database stores registry
metadata and execution state, not full benchmark records. Only a bounded,
redacted/aggregated benchmark context should ever enter a run.
