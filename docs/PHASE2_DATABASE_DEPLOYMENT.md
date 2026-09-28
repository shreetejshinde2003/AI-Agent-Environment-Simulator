# Phase 2 operational database and deployment

## Local SQLite

From `backend/`, leave `DATABASE_URL` unset to use `sqlite:///./simulator.db`,
or set another explicit `sqlite:///` path. No local PostgreSQL installation is
required. Application startup creates schema version 2 and indexes. The
operational database stores system state, not the six benchmark HR record sets.

When opening a version 1 SQLite database, startup first validates every old
snapshot and creates a timestamped `.v1.*.db` backup. It then archives the old
three tables as `*_v1_archive`, imports their records into the new schema and
sets `PRAGMA user_version=2`. Keep the backup and archive until you verify the
new database. Migration never deletes V1 data. An invalid or unversioned legacy
database stops startup for manual inspection. V1 snapshots have no benchmark ID
or newly introduced metric fields; those remain unset rather than invented.

## Railway PostgreSQL

The production backend uses a private Railway PostgreSQL service. Bind
the backend service's `DATABASE_URL` to that service's connection URL
using Railway's private variable reference. Acceptable schemes are
`postgres://`, `postgresql://` and `postgresql+psycopg://`; the app uses psycopg
3. Do not paste credentials into source, docs, logs or the browser. Existing
server-side `GROQ_API_KEY`, model values and CORS configuration remain unchanged.

On startup the backend creates version 2 tables, foreign keys and indexes under
a PostgreSQL advisory transaction lock. The schema version is checked; unknown
versions fail startup instead of being silently changed. Database state is
durable only if the Railway PostgreSQL service itself is retained and backed up.
An application volume is **not** required for operational database records with
PostgreSQL. It **is** needed, or an equivalent private file/object source, if
benchmark JSON files must survive backend deployments. The six files are not
committed and are not downloaded from Drive at runtime.

The backend starts with local SQLite if `DATABASE_URL` is missing; on Railway
that fallback is not durable on an ephemeral filesystem. The production backend
has `DATABASE_URL` configured for Railway PostgreSQL. No credentials are committed.

## Production verification — 2026-09-29

Deployed commit: `ef27951`. Production path: Vercel frontend → Railway FastAPI
backend → Railway PostgreSQL. One real five-agent simulation completed and appeared
in Simulation History. After the Railway backend was restarted/redeployed, the
same simulation remained available with completed status, graph state, timestamps,
duration, token usage and final result. This verifies the live PostgreSQL
connection and durable operational persistence across a **backend** restart. It
does not establish survival of deletion or loss of the PostgreSQL service itself.

The six benchmark JSON files have not been verified as provisioned in production.
They remain separate from the operational PostgreSQL database.

## Switching and limitations

Changing `DATABASE_URL` switches databases; it does not automatically copy
records between SQLite and PostgreSQL. Preserve the SQLite file and backup,
then use a separately reviewed export/import procedure before cutover. Do not
delete the old file or deploy a connection change expecting prior runs to appear
automatically. V1 snapshots can be migrated **in place only on SQLite**; no
automatic cross-engine transfer or downgrade is implemented.

Run one backend worker. The five-agent execution is still an in-process
BackgroundTask, not a distributed job queue. Concurrent workers may race over
startup recovery of queued/running tasks. The shared workspace has no login or
per-user authorization; avoid exposing confidential HR data through uploads.
