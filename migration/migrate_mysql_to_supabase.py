#!/usr/bin/env python3
"""Copy the KISA relational data from AWS RDS MySQL into Supabase Postgres.

Assumes queries/supabase_schema.sql has already been applied to the target.
Copies data only: it never creates or drops tables.

    pip install PyMySQL psycopg2-binary
    export MYSQL_URL='mysql://user:pass@rds-host:3306/ebdb'
    export DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres'
    python migrate_mysql_to_supabase.py --dry-run     # counts only, writes nothing
    python migrate_mysql_to_supabase.py               # copy
    python migrate_mysql_to_supabase.py --truncate    # wipe target tables first

Postgres folds unquoted identifiers to lowercase, so MySQL's camelCase column
names are lowercased on the way in. Which columns are booleans is read from the
target's own catalog rather than hardcoded, so MySQL TINYINT 0/1 lands as real
booleans without a list that can drift from the schema.
"""
import argparse
import os
import sys
from urllib.parse import urlparse, unquote

import pymysql
import psycopg2
import psycopg2.extras

# Parent tables first: every table's foreign keys point only at tables above it.
TABLES = [
    "users",
    "admins",
    "posts",
    "comments",
    "postlikes",
    "commentlikes",
    "pocha",
    "menu",
    "order",
    "orderItem",
    "notificationARNs",
]

# Identity columns whose sequence must be advanced past the copied ids, or the
# next INSERT collides with an existing primary key.
SEQUENCES = [
    ("posts", "postid"),
    ("comments", "commentid"),
    ("pocha", "pochaid"),
    ("menu", "menuid"),
    ('"order"', "orderid"),
    ("orderitem", "orderitemid"),
]

BATCH = 1000


def pg_ident(table):
    """order is a reserved word in Postgres and must stay quoted."""
    name = table.lower()
    return '"order"' if name == "order" else name


def mysql_ident(table):
    return f"`{table}`"


def connect_mysql(url):
    p = urlparse(url)
    if not p.hostname or not p.path.lstrip("/"):
        sys.exit(f"MYSQL_URL is missing host or database: {url!r}")
    return pymysql.connect(
        host=p.hostname,
        port=p.port or 3306,
        user=unquote(p.username or ""),
        password=unquote(p.password or ""),
        database=p.path.lstrip("/"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def boolean_columns(pg, table):
    """Ask the target which columns are boolean, so no hardcoded list can drift."""
    with pg.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND data_type = 'boolean'",
            (table.lower(),),
        )
        return {row[0] for row in cur.fetchall()}


def target_columns(pg, table):
    with pg.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table.lower(),),
        )
        return {row[0] for row in cur.fetchall()}


def to_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (bytes, bytearray)):          # MySQL BIT(1)
        return value not in (b"\x00", b"")
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes", "y")
    return bool(value)


def copy_table(my, pg, table, dry_run):
    src = mysql_ident(table)
    dst = pg_ident(table)

    with my.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM {src}")
        total = cur.fetchone()["n"]

    if dry_run:
        print(f"  {table:18} {total:>7} rows (dry run, nothing written)")
        return total, 0

    bools = boolean_columns(pg, table)
    available = target_columns(pg, table)

    with my.cursor() as cur:
        cur.execute(f"SELECT * FROM {src}")
        first = cur.fetchmany(BATCH)
        if not first:
            print(f"  {table:18} {0:>7} rows")
            return 0, 0

        columns = [c.lower() for c in first[0].keys()]
        missing = [c for c in columns if c not in available]
        if missing:
            sys.exit(
                f"{table}: source has columns the target lacks: {missing}. "
                "Apply the current supabase_schema.sql before migrating."
            )

        collist = ", ".join(f'"{c}"' for c in columns)
        sql = f"INSERT INTO {dst} ({collist}) VALUES %s"

        written = 0
        batch = first
        with pg.cursor() as out:
            while batch:
                rows = [
                    tuple(
                        to_bool(row[key]) if key.lower() in bools else row[key]
                        for key in row
                    )
                    for row in batch
                ]
                psycopg2.extras.execute_values(out, sql, rows, page_size=BATCH)
                written += len(rows)
                batch = cur.fetchmany(BATCH)

    print(f"  {table:18} {written:>7} rows")
    return total, written


def reset_sequences(pg):
    with pg.cursor() as cur:
        for table, column in SEQUENCES:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                f"COALESCE((SELECT max({column}) FROM {table}), 1))"
            )
            print(f"  {table:18} {column} -> {cur.fetchone()[0]}")


def verify(my, pg):
    ok = True
    for table in TABLES:
        with my.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {mysql_ident(table)}")
            src = cur.fetchone()["n"]
        with pg.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {pg_ident(table)}")
            dst = cur.fetchone()[0]
        match = "ok" if src == dst else "MISMATCH"
        if src != dst:
            ok = False
        print(f"  {table:18} mysql={src:<7} postgres={dst:<7} {match}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count rows, write nothing")
    ap.add_argument("--truncate", action="store_true", help="empty target tables first")
    args = ap.parse_args()

    mysql_url = os.getenv("MYSQL_URL")
    pg_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not mysql_url or not pg_url:
        sys.exit("set MYSQL_URL and DATABASE_URL (or SUPABASE_DB_URL)")

    my = connect_mysql(mysql_url)
    pg = psycopg2.connect(pg_url)
    # One transaction for the whole copy: a failure halfway leaves the target
    # untouched rather than half-populated.
    pg.autocommit = False

    try:
        if args.truncate and not args.dry_run:
            print("truncating target tables")
            with pg.cursor() as cur:
                names = ", ".join(pg_ident(t) for t in TABLES)
                cur.execute(f"TRUNCATE {names} RESTART IDENTITY CASCADE")

        print("copying")
        for table in TABLES:
            copy_table(my, pg, table, args.dry_run)

        if args.dry_run:
            pg.rollback()
            print("\ndry run complete, nothing written")
            return 0

        print("\nresetting sequences")
        reset_sequences(pg)
        pg.commit()

        print("\nverifying row counts")
        if not verify(my, pg):
            print("\nFAILED: row counts differ")
            return 1
        print("\nmigration complete")
        return 0
    except Exception:
        pg.rollback()
        raise
    finally:
        my.close()
        pg.close()


if __name__ == "__main__":
    sys.exit(main())
