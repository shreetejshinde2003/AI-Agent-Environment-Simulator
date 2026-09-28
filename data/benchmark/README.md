# Local benchmark inputs

Provision `employee_small.json`, `employee_medium.json`, `employee_large.json`,
`hr_small.json`, `hr_medium.json`, and `hr_large.json` in this directory on
authorized hosts. The six raw files are ignored by Git because the HR family
contains names, salaries and manager links. They are not downloaded from
Google Drive at application runtime.

Run the backend dataset registration command documented in
[backend/README.md](../../backend/README.md) after provisioning. Registration stores only validated
metadata in the operational database; the raw records remain here.
