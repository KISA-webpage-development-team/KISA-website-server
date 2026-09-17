# Supabase migration handoff

Everything needed to finish moving the KISA relational database from AWS RDS
MySQL to Supabase Postgres and to decommission the RDS instance. Written for
someone picking this up with no prior context.

Last verified against production: 2026-08-25.

---

## 1. Goal and scope

Move the relational database off AWS RDS MySQL onto Supabase Postgres to cut the
AWS bill. Flask stays as the API layer. S3, CloudFront and SNS/APNS stay on AWS
and are not touched by any of this.

Eleven tables, 2,413 rows total as of 2026-08-25:

| Table | Rows | | Table | Rows |
|---|---:|---|---|---:|
| users | 295 | | pocha | 11 |
| admins | 9 | | menu | 123 |
| posts | 279 | | order | 496 |
| comments | 260 | | orderItem | 812 |
| postlikes | 89 | | notificationARNs | 7 |
| commentlikes | 32 | | **total** | **2,413** |

The dataset is small. The copy takes seconds, not minutes. Volume is not a risk
here and no batching or streaming strategy is needed beyond what already exists.

---

## 2. Current status

Done:

- Postgres adapter merged to `main` (PR #20).
- Pocha auth hardening merged to `main` (PR #21).
- Client sends the session token on pocha requests (client PR #228), **merged and
  deployed to Vercel production** on 2026-08-25 at 04:20 UTC, commit `9778360`.
- Migration tooling exists under `migration/`.
- Production data scanned against the target schema; four defects found and
  fixed in **PR #22, which is open and not yet merged**.

Not done:

- Server is **not deployed**. Elastic Beanstalk is still running
  `app-e4e3-260108_122422790940` from 2026-01-08. Neither PR #20 nor #21 is live.
- **No production Supabase project exists.** This is the hard blocker. Everything
  from section 6 onward is waiting on it.
- `migration/cleanup_before_migration.sql` has not been run.
- The amended schema has never been applied to a real Postgres instance.

---

## 3. How the adapter works

`server/model.py` decides the backend from one environment variable:

```
DATABASE_ENGINE = os.getenv("DATABASE_ENGINE", "mysql").lower()
```

Unset means MySQL, so merging and deploying the adapter changes nothing until
that variable is set. This is deliberate and is what makes a staged cutover
possible.

When set to `postgres`, `server/model.py` needs `DATABASE_URL` (or
`SUPABASE_DB_URL`) and a `Cursor` class translates between the two dialects:

- **Column case.** Postgres folds unquoted identifiers to lowercase, so MySQL's
  `bornYear` comes back as `bornyear`. `PG_KEY_MAP` maps them back to camelCase
  on read so API response shapes do not change. The map is derived from the
  single `CAMEL_COLUMNS` list; adding a column there is the only step needed.
- **Reserved words.** `` `order` `` is rewritten to `"order"`.
- **Insert ids.** MySQL's `lastrowid` has no Postgres equivalent, so
  `INSERT_RETURNING_COLUMNS` appends `RETURNING <pk>` to inserts on `posts`,
  `pocha`, `menu` and `order`.

Three fixes were needed to get the app green against Postgres and are already on
`main`: deriving `PG_KEY_MAP` from the camelCase list, converting
`boards.py` `isAnnouncement` from 0/1 to False/True, and using
`double precision` plus naive `timestamp` in the schema instead of
`numeric(8,2)` and `timestamptz`.

---

## 4. Infrastructure map

```
umichkisa-api.com  (Route53 zone Z08144033HJTU5OEOJW4Y)
    A ALIAS -> kisa-api.eba-jvmh92a5.us-east-2.elasticbeanstalk.com
                   |
            Elastic Beanstalk environment "KISA-api"  (id e-bxtm2zpybp)
            Python 3.11 on AL2023, us-east-2
                   |
                   +-- coupled RDS: awseb-e-bxtm2zpybp-stack-awsebrdsdatabase-7pth6zviixzm
                       mysql 8.0.45, db.t3.micro, MultiAZ, 20GB gp2, database "ebdb"

Frontend: Vercel, NEXT_PUBLIC_BACKEND_URL = https://umichkisa-api.com/api/v2
```

### The critical constraint

The RDS instance is **coupled to the Elastic Beanstalk environment**, confirmed
by both the instance name embedding the environment id `e-bxtm2zpybp` and the
environment config:

```
HasCoupledDatabase   true
DBDeletionPolicy     Snapshot
```

Elastic Beanstalk does not support removing a coupled database from a running
environment. The RDS instance cannot be deleted on its own while that
environment exists. **Terminating the environment to get rid of the database
would take the API down with it, because that environment is the API.**

The way out is blue/green: stand up a second environment with no coupled
database, move traffic to it, then terminate the old environment, which takes
its database with it. `DBDeletionPolicy: Snapshot` means a final snapshot is
taken automatically at that point.

### Configuration drift

Elastic Beanstalk's stored config no longer matches the live instance:

| | EB config says | Reality |
|---|---|---|
| Instance class | db.t3.small | db.t3.micro |
| Engine version | 8.0.35 | 8.0.45 |

Someone modified the RDS instance outside Elastic Beanstalk. Do not apply
configuration changes to the old environment: Elastic Beanstalk may try to
reconcile the database back to `db.t3.small`. Leave the old environment alone
until it is terminated.

### Cost note

The instance is MultiAZ, which doubles the database cost for a 2,413-row
dataset. Backup retention is 1 day and deletion protection is off. If the
migration slips, turning MultiAZ off is an immediate saving on its own. Take a
manual snapshot before the soak regardless, since one day of retention is thin.

---

## 5. Credentials

Nothing is committed and nothing belongs in this document.

**Production MySQL** credentials live in the Elastic Beanstalk environment, not
in any local `.env`. The repo's `.env` points at `127.0.0.1` and is useless for
this. Fetch them with:

```bash
aws elasticbeanstalk describe-configuration-settings \
  --application-name KISA-api --environment-name KISA-api \
  --profile eb-cli --region us-east-2 \
  --query "ConfigurationSettings[0].OptionSettings[?Namespace=='aws:elasticbeanstalk:application:environment' && (OptionName=='MYSQL_HOST'||OptionName=='MYSQL_USER'||OptionName=='MYSQL_PASSWORD')].[OptionName,Value]" \
  --output text
```

Database name is `ebdb`.

**Supabase** credentials come from the project dashboard once the project
exists.

### IPv6 gotcha

The direct connection host `db.<ref>.supabase.co` is AAAA-only. Machines without
an IPv6 route cannot reach it and the failure looks like a generic timeout. Use
the **session pooler** instead:

```
postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Port `6543`, not `5432`. This cost real time once already.

---

## 6. Prerequisites before cutover

1. **Merge PR #22.** Without it the copy fails on 197 comment rows and one user
   row. See section 9.
2. **Create the production Supabase project.** Pick the region closest to
   `us-east-2`.
3. **Apply the schema**, from `main` with #22 merged:
   ```bash
   psql "$DATABASE_URL" -f queries/supabase_schema.sql
   ```
4. **Deploy the server to the existing environment first**, on MySQL. See
   section 7. This separates the auth change from the database change so a
   failure has one obvious cause.

---

## 7. Deploy the server to the existing environment

The client is already deployed and sending tokens. The server is not yet
enforcing them, which is harmless. Deploying the server activates enforcement
(PR #21) and ships the inert Postgres adapter (PR #20). `DATABASE_ENGINE` stays
unset, so the database does not change.

### Deploy footgun, read before running anything

`.elasticbeanstalk/config.yml` sets `sc: git`, so **`eb deploy` ships the
committed HEAD of whatever branch is currently checked out**, not `main` and not
the working tree.

As of this writing the local `main` is diverged from `origin/main`: 2 commits
ahead, 31 behind. Deploying from it would ship two unmerged local commits and
neither PR #20 nor #21. Confirm before deploying:

```bash
git fetch origin
git status -sb          # expect "## main...origin/main" with no ahead/behind
git log -1 --oneline    # expect the merge commit for PR #21 or later
```

Resolve the divergence deliberately. The two local commits (a jobs pipeline
change and a Flask env fix) are unreviewed work; decide whether they become a PR
or get dropped. Do not simply force the branch without that decision.

Then:

```bash
eb deploy KISA-api
```

### Verify

Pocha endpoints must still work for a logged-in user, and must return 401
without a token. If pocha breaks for everyone, the client and server auth
versions are mismatched; roll back by redeploying the previous application
version from the Elastic Beanstalk console.

---

## 8. Cutover runbook

Blue/green, because of the coupled-database constraint in section 4. The API
stays up throughout, and the rollback is a single command.

### Step 1: create the green environment

Same application, **no coupled database**, with the Postgres variables set:

```bash
eb create KISA-api-green \
  --envvars DATABASE_ENGINE=postgres,DATABASE_URL=<supabase-session-pooler-url>
```

Copy every other environment variable across from `KISA-api`: `SECRET_KEY`,
`AWS_REGION`, `CLOUDFRONT_DISTRIBUTION_ID`, `CLOUDFRONT_URL`, `CLOUDINARY_*`,
`S3_BUCKET_NAME`, `WANTED_API_*`, `FLASK_ENV`, `PYTHONPATH`. Omit `MYSQL_*`.

Missing one of these will not fail at deploy time. It fails later, at the first
request that needs it.

### Step 2: freeze writes

The copy is one-shot, not replication. Writes to MySQL after the copy starts are
lost. The dataset is tiny so this window is a couple of minutes, but it must
exist.

### Step 3: scan, clean, copy

```bash
export MYSQL_URL='mysql://<user>:<pass>@<rds-host>:3306/ebdb'
export DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres'

# Re-run the scan. Rows added since 2026-08-25 can introduce new violations.
python migration/scan_source_data.py

# Retire the three dead references. Expect both counts to report 0.
mysql --default-character-set=utf8mb4 -h <rds-host> -u <user> -p ebdb \
      < migration/cleanup_before_migration.sql

python migration/migrate_mysql_to_supabase.py --dry-run
python migration/migrate_mysql_to_supabase.py
python migration/test/verify_migration.py
```

`--truncate` wipes the target first. It exists for re-running against a scratch
project. Never point it at anything that matters.

The whole copy runs in one transaction, so a failure halfway leaves the target
untouched rather than half-populated. Sequences are advanced past the copied ids
at the end; without that the next insert collides with an existing primary key.

**Charset.** The script sets `charset="utf8mb4"` on its own connection. If you
take a `mysqldump` route instead, pass `--default-character-set=utf8mb4` on both
dump and restore. This is the single easiest way to silently corrupt every
Korean name, title and menu item, and it does not announce itself.

### Step 4: verify green before any traffic

Hit the green environment on its own URL, not the production domain. All 40
DB-backed routes should pass. `verify_migration.py` compares every column of
every row; row counts alone prove nothing.

### Step 5: swap

```bash
aws elasticbeanstalk swap-environment-cnames \
  --source-environment-name KISA-api \
  --destination-environment-name KISA-api-green \
  --profile eb-cli --region us-east-2
```

The Route53 record is an A ALIAS to the Elastic Beanstalk CNAME, so swapping the
CNAMEs moves traffic with **no DNS edit, no ACM certificate change and no
propagation wait**. Unfreeze writes.

### Step 6: soak

One to two weeks. The old environment and its RDS instance sit untouched the
whole time. **Rollback is swapping the CNAMEs back**, which is the same command
with the two names exchanged.

Watch for the email-case issue in section 9.

---

## 9. Defects found in production data

Found by running `migration/scan_source_data.py` against production. Fixed in
PR #22 unless noted.

**A. `comments.parentcommentid` foreign key, 197 rows.** The schema declared a
self-referencing foreign key that MySQL never had. The API stores `0` for a
top-level comment as a sentinel. The correlation is exact: 197 rows have
`parentCommentId = 0` and `isCommentOfComment = 0`; 63 have a real parent and
`isCommentOfComment = 1`. `server/api/bulletin/comment.py` passes the client's
value straight through, so with the constraint in place every new top-level
comment would fail on insert too, not just the load. Foreign key dropped.

**B. `users.bornmonth` / `borndate` CHECK, 1 row.** `umichkisa@gmail.com` is the
KISA organisation account, an admin with 110 posts, and stores `0` for its
birthday because it is not a person. CHECK relaxed to allow 0.

**C. `order.email` orphan, 1 row.** Order 188 with 3 items belongs to a deleted
account. Nulled by `cleanup_before_migration.sql`, which is what the schema's own
`ON DELETE SET NULL` should have left behind.

**D. `notificationARNs.email` orphans, 2 rows.** APNS device tokens for deleted
accounts. Deleted by `cleanup_before_migration.sql`, since that column is a
primary key and cannot be nulled.

**E. Three users have non-lowercase emails. Not fixed, watch during the soak.**
MySQL compares case-insensitively and Postgres does not, and there is no email
normalisation anywhere in the codebase. Emails arrive from the Google OAuth
claim so they most likely match the stored case exactly, and pre-emptively
changing the auth path is not warranted. If a user cannot log in after cutover,
this is the first thing to check, and a one-line `UPDATE` on that row fixes it.

Clean as of 2026-08-25: zero dates, NOT NULL violations, and non-utf8mb4 text
columns are all zero.

### Note on the scanner

Its table regex did not allow the quoted `"order"` identifier, so that table and
its 496 rows silently dropped out of every check. Fixed in PR #22. If you extend
the scanner, remember that a check which silently covers nothing is worse than
no check.

---

## 10. Decommissioning RDS

Only after the soak passes.

1. Take a **manual final snapshot** and confirm it completes. Backup retention is
   only 1 day, so do not rely on the automated backups.
2. Consider a local `mysqldump --default-character-set=utf8mb4` kept outside AWS.
3. Terminate the old environment:
   ```bash
   eb terminate KISA-api
   ```
   `DBDeletionPolicy: Snapshot` means Elastic Beanstalk takes another final
   snapshot before deleting the instance. Billing for the instance stops here.
4. Optionally rename `KISA-api-green` for clarity. The CNAME already carries
   production traffic, so this is cosmetic.

Snapshot storage costs a few dollars a month and is worth keeping for a while.

Do **not** try to stop the RDS instance as a cost measure instead: a stopped RDS
instance restarts automatically after 7 days.

---

## 11. Open questions

- Which Supabase region and plan. The free tier pauses inactive projects, which
  is not acceptable for production.
- What to do with the two unreviewed commits on the local `main` (section 7).
- Whether the pocha auth enforcement from PR #21 has been exercised against a
  real logged-in session, or only against the test suite.
- Nothing migrates the S3 or CloudFront assets, and nothing needs to. Confirm
  that is still the intent before terminating anything.
