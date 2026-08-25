# RDS MySQL to Supabase Postgres data migration

Copies the eleven KISA tables from AWS RDS MySQL into a Supabase Postgres project
that already has `server/queries/supabase_schema.sql` applied. Data only — it never
creates or drops tables.

## Prerequisites

Apply the fixed schema first. The migration assumes `price double precision` and
naive `timestamp` columns; the original `numeric(8, 2)` / `timestamptz` version
breaks the Flask app at runtime.

```
pip install PyMySQL psycopg2-binary
```

**Charset matters.** Read MySQL over a utf8mb4 connection or Korean text arrives
double-encoded (`김민준` becomes `ê¹€ë¯¼ì¤€`). The script sets `charset="utf8mb4"`
on its own connection. If you take a `mysqldump` route instead, pass
`--default-character-set=utf8mb4` on both dump and restore — this is the single
easiest way to silently corrupt every Korean name, title, and menu item.

## Running it

```
export MYSQL_URL='mysql://user:pass@rds-host:3306/ebdb'
export DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres'

python migrate_mysql_to_supabase.py --dry-run     # counts only, writes nothing
python migrate_mysql_to_supabase.py               # copy
python migrate_mysql_to_supabase.py --truncate    # wipe target tables first, then copy
```

Use port `6543` (the transaction pooler), not `5432`.

The whole copy runs in one transaction, so a failure halfway leaves the target
untouched rather than half-populated. `--truncate` is for re-running against a
scratch project; never point it at anything you care about.

## What it handles

- **Column names** — Postgres folds unquoted identifiers to lowercase, so MySQL's
  `bornYear` is written as `bornyear`. The Flask `Cursor` maps them back to
  camelCase on read.
- **Booleans** — MySQL `TINYINT` 0/1 becomes a real Postgres `boolean`. Which
  columns are boolean is read from the target's `information_schema` rather than a
  hardcoded list, so it cannot drift from the schema.
- **`order`** — a reserved word in Postgres, quoted everywhere.
- **Insert order** — parents before children, so foreign keys always resolve.
- **Sequences** — identity sequences are advanced past the copied ids. Without this
  the next insert collides with an existing primary key.

## Verifying

```
python test/verify_migration.py
```

Compares every column of every row between source and target, normalising only the
differences the migration is meant to introduce. Row counts alone prove nothing.

## Test results (2026-08-24)

Run against MySQL 8.0 and Postgres 16 containers, with fixture data covering Korean
text, emoji, apostrophes, NULLs, both boolean values, and non-contiguous auto-increment
ids (500 / 88 / 9000):

- 11/11 tables, row counts match
- 182/182 column values match
- sequences land on 501 / 89 / 13 / 41 / 301 / 9001 — next insert on every identity
  table succeeds with no primary key collision
- Korean, emoji (`🎉`), apostrophes, and NULLs preserved
- the real Flask app on `DATABASE_ENGINE=postgres` passes **40/40 DB-backed routes**
  against the migrated data

## Not covered

- Volume. The fixture is small; run `--dry-run` against production first to see real
  counts, and expect the copy to take proportionally longer. Batches are 1000 rows.
- Downtime. This is a one-shot copy, not replication. Writes to MySQL after the copy
  starts are not picked up — take the app down or accept a write freeze during cutover.
- S3/CloudFront images and SNS endpoints are untouched; they stay on AWS.
