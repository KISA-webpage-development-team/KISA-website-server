#!/usr/bin/env python3
"""Row-by-row comparison of the MySQL source against the migrated Postgres target.

Row counts prove nothing about values. This compares every row of every table,
normalising only the differences the migration is supposed to introduce:
lowercase column names, and TINYINT 0/1 becoming a real boolean.
"""
import os
import sys
from decimal import Decimal
from urllib.parse import urlparse, unquote

import pymysql
import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from migrate_mysql_to_supabase import TABLES, pg_ident, mysql_ident, boolean_columns  # noqa: E402

KEYS = {
    "users": ["email"], "admins": ["email"], "posts": ["postid"],
    "comments": ["commentid"], "postlikes": ["email", "postid"],
    "commentlikes": ["email", "commentid"], "pocha": ["pochaid"],
    "menu": ["menuid"], "order": ["orderid"], "orderItem": ["orderitemid"],
    "notificationARNs": ["email"],
}


def norm(value):
    """Collapse representational differences that are not data differences."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    return value


def main():
    p = urlparse(os.environ["MYSQL_URL"])
    my = pymysql.connect(
        host=p.hostname, port=p.port or 3306, user=unquote(p.username or ""),
        password=unquote(p.password or ""), database=p.path.lstrip("/"),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    pg = psycopg2.connect(os.environ["DATABASE_URL"])

    failures = []
    checked = 0

    for table in TABLES:
        bools = boolean_columns(pg, table)
        keys = KEYS[table]

        with my.cursor() as cur:
            cur.execute(f"SELECT * FROM {mysql_ident(table)}")
            src_rows = cur.fetchall()

        with pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM {pg_ident(table)}")
            dst_rows = {
                tuple(str(r[k]) for k in keys): dict(r) for r in cur.fetchall()
            }

        for src in src_rows:
            low = {k.lower(): v for k, v in src.items()}
            key = tuple(str(low[k]) for k in keys)
            dst = dst_rows.get(key)
            if dst is None:
                failures.append(f"{table} {key}: missing in postgres")
                continue
            for column, value in low.items():
                checked += 1
                expected = (value != 0) if (column in bools and value is not None) else value
                got = dst.get(column)
                if norm(expected) != norm(got):
                    failures.append(
                        f"{table} {key} col={column}: mysql={value!r} -> "
                        f"expected {expected!r}, postgres has {got!r}")

    print(f"compared {checked} column values across {len(TABLES)} tables")
    if failures:
        print(f"\n{len(failures)} MISMATCHES:")
        for f in failures:
            print("  ", f)
        return 1
    print("every value matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
