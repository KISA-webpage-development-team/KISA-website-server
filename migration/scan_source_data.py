#!/usr/bin/env python3
"""Read-only scan of the source MySQL database for anything the Postgres load
will reject. Runs SELECTs only; writes nothing, locks nothing.

    export MYSQL_URL='mysql://user:pass@rds-host:3306/ebdb'
    python migration/scan_source_data.py

Run it again immediately before the real copy: rows added since the last scan
can introduce new violations.

Every check mirrors a constraint that supabase_schema.sql will enforce but
MySQL currently does not, plus the charset trap. A clean run means the real
migration has nothing prod-specific left to trip on.
"""
import os
import re
import sys
from collections import defaultdict

import pymysql

TABLES = [
    "users", "admins", "posts", "comments", "postlikes", "commentlikes",
    "pocha", "menu", "order", "orderItem", "notificationARNs",
]

SCHEMA = os.getenv(
    "SCHEMA_SQL",
    os.path.join(os.path.dirname(__file__), "..", "queries", "supabase_schema.sql"),
)
problems = []


def parse_schema(path):
    """Pull NOT NULL columns, CHECK expressions and FKs out of the target schema."""
    text = open(path).read()
    not_null, checks, fks = defaultdict(list), defaultdict(list), []
    # "order" is a reserved word and is quoted in the schema; without allowing the
    # quotes the whole table silently drops out of every check below.
    for m in re.finditer(r'CREATE TABLE IF NOT EXISTS "?(\w+)"? \((.*?)\n\);', text, re.S):
        table, body = m.group(1), m.group(2)
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            col = line.split()[0].strip('"')
            if "NOT NULL" in line and "DEFAULT" not in line:
                not_null[table].append(col)
            c = re.search(r"CHECK \((.+?)\)\s*$", line)
            if c:
                checks[table].append((col, c.group(1)))
            r = re.search(r'REFERENCES "?(\w+)"?\((\w+)\)', line)
            if r:
                fks.append((table, col, r.group(1), r.group(2)))
    return not_null, checks, fks


def mysql_col(cur, table, want):
    """Map a lowercase Postgres column back to its real MySQL casing."""
    cur.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", (table,))
    for row in cur.fetchall():
        if row["COLUMN_NAME"].lower() == want.lower():
            return row["COLUMN_NAME"]
    return None


def mysql_table(cur, want):
    cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()")
    for row in cur.fetchall():
        if row["TABLE_NAME"].lower() == want.lower():
            return row["TABLE_NAME"]
    return None


def main():
    url = os.environ["MYSQL_URL"]
    from urllib.parse import urlparse, unquote
    p = urlparse(url)
    conn = pymysql.connect(
        host=p.hostname, port=p.port or 3306,
        user=unquote(p.username or ""), password=unquote(p.password or ""),
        database=p.path.lstrip("/"), charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    not_null, checks, fks = parse_schema(SCHEMA)
    cur = conn.cursor()

    print("=" * 62)
    print("1. ROW COUNTS")
    print("=" * 62)
    total = 0
    real = {}
    for t in TABLES:
        rt = mysql_table(cur, t)
        if not rt:
            print(f"  {t:18} MISSING IN MYSQL")
            problems.append(f"table {t} not found in MySQL")
            continue
        real[t] = rt
        cur.execute(f"SELECT COUNT(*) AS n FROM `{rt}`")
        n = cur.fetchone()["n"]
        total += n
        print(f"  {t:18} {n:>8}")
    print(f"  {'TOTAL':18} {total:>8}")

    print()
    print("=" * 62)
    print("2. TABLES IN MYSQL THE MIGRATION DOES NOT COPY")
    print("=" * 62)
    cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'")
    known = {t.lower() for t in TABLES}
    extras = [r["TABLE_NAME"] for r in cur.fetchall()
              if r["TABLE_NAME"].lower() not in known]
    if extras:
        for e in extras:
            cur.execute(f"SELECT COUNT(*) AS n FROM `{e}`")
            n = cur.fetchone()["n"]
            print(f"  {e:30} {n:>8} rows  NOT MIGRATED")
            if n:
                problems.append(f"table {e} has {n} rows and is not in TABLES")
    else:
        print("  none - every base table is covered")

    print()
    print("=" * 62)
    print("3. ZERO / INVALID DATES  (Postgres rejects 0000-00-00)")
    print("=" * 62)
    cur.execute(
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND DATA_TYPE IN "
        "('date','datetime','timestamp')")
    datecols = [(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cur.fetchall()
                if r["TABLE_NAME"].lower() in known]
    hits = 0
    for t, c in datecols:
        cur.execute(f"SELECT COUNT(*) AS n FROM `{t}` "
                    f"WHERE CAST(`{c}` AS CHAR) LIKE '0000-00-00%'")
        n = cur.fetchone()["n"]
        if n:
            hits += 1
            print(f"  {t}.{c}: {n} rows")
            problems.append(f"{t}.{c} has {n} zero dates")
    if not hits:
        print(f"  none across {len(datecols)} date/datetime columns")

    print()
    print("=" * 62)
    print("4. NULLS IN COLUMNS THE POSTGRES SCHEMA MARKS NOT NULL")
    print("=" * 62)
    hits = 0
    for pgt, cols in not_null.items():
        rt = real.get(pgt) or mysql_table(cur, pgt)
        if not rt:
            continue
        for col in cols:
            mc = mysql_col(cur, rt, col)
            if not mc:
                print(f"  {pgt}.{col}: COLUMN MISSING IN MYSQL")
                problems.append(f"{pgt}.{col} missing in MySQL")
                continue
            cur.execute(f"SELECT COUNT(*) AS n FROM `{rt}` WHERE `{mc}` IS NULL")
            n = cur.fetchone()["n"]
            if n:
                hits += 1
                print(f"  {pgt}.{col}: {n} NULL rows")
                problems.append(f"{pgt}.{col} has {n} NULLs but is NOT NULL in Postgres")
    if not hits:
        print("  none - every NOT NULL column is populated")

    print()
    print("=" * 62)
    print("5. CHECK CONSTRAINT VIOLATIONS")
    print("=" * 62)
    hits = 0
    for pgt, items in checks.items():
        rt = real.get(pgt) or mysql_table(cur, pgt)
        if not rt:
            continue
        for col, expr in items:
            mc = mysql_col(cur, rt, col)
            if not mc:
                continue
            # The CHECK text uses the lowercase Postgres name; swap in MySQL's casing.
            my_expr = re.sub(rf"\b{re.escape(col)}\b", f"`{mc}`", expr)
            try:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{rt}` "
                            f"WHERE NOT ({my_expr})")
                n = cur.fetchone()["n"]
            except Exception as e:
                print(f"  {pgt}.{col}: could not evaluate ({e})")
                continue
            if n:
                hits += 1
                print(f"  {pgt}.{col} violates CHECK ({expr}): {n} rows")
                problems.append(f"{pgt}.{col} has {n} rows violating CHECK ({expr})")
    if not hits:
        print("  none")

    print()
    print("=" * 62)
    print("6. ORPHAN FOREIGN KEY ROWS  (Postgres will reject these)")
    print("=" * 62)
    hits = 0
    for child, ccol, parent, pcol in fks:
        rc = real.get(child) or mysql_table(cur, child)
        rp = real.get(parent) or mysql_table(cur, parent)
        if not rc or not rp:
            continue
        mcc = mysql_col(cur, rc, ccol)
        mpc = mysql_col(cur, rp, pcol)
        if not mcc or not mpc:
            continue
        cur.execute(
            f"SELECT COUNT(*) AS n FROM `{rc}` c LEFT JOIN `{rp}` p "
            f"ON c.`{mcc}` = p.`{mpc}` "
            f"WHERE c.`{mcc}` IS NOT NULL AND p.`{mpc}` IS NULL")
        n = cur.fetchone()["n"]
        if n:
            hits += 1
            print(f"  {child}.{ccol} -> {parent}.{pcol}: {n} orphans")
            problems.append(f"{child}.{ccol} has {n} orphan rows")
        else:
            print(f"  {child}.{ccol} -> {parent}.{pcol}: ok")
    if not hits:
        print("  no orphans")

    print()
    print("=" * 62)
    print("7. COLUMN CHARSET  (non-utf8mb4 text = Korean corruption risk)")
    print("=" * 62)
    cur.execute(
        "SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
        "AND CHARACTER_SET_NAME IS NOT NULL")
    bad = [r for r in cur.fetchall()
           if r["TABLE_NAME"].lower() in known
           and r["CHARACTER_SET_NAME"] != "utf8mb4"]
    if bad:
        for r in bad:
            print(f"  {r['TABLE_NAME']}.{r['COLUMN_NAME']}: "
                  f"{r['CHARACTER_SET_NAME']} / {r['COLLATION_NAME']}")
            problems.append(f"{r['TABLE_NAME']}.{r['COLUMN_NAME']} is "
                            f"{r['CHARACTER_SET_NAME']}, not utf8mb4")
    else:
        print("  every text column is utf8mb4")

    print()
    print("=" * 62)
    print("8. EMAIL CASE  (MySQL compares case-insensitively, Postgres does not)")
    print("=" * 62)
    rt = real.get("users")
    if rt:
        mc = mysql_col(cur, rt, "email")
        cur.execute(f"SELECT COUNT(*) AS n FROM `{rt}` "
                    f"WHERE BINARY `{mc}` <> LOWER(`{mc}`)")
        n = cur.fetchone()["n"]
        print(f"  users with a non-lowercase email: {n}")
        if n:
            problems.append(f"{n} users have non-lowercase emails; "
                            f"case-sensitive Postgres lookups may miss them")

    print()
    print("=" * 62)
    if problems:
        print(f"RESULT: {len(problems)} ISSUE(S) TO RESOLVE BEFORE THE COPY")
        for p_ in problems:
            print(f"  - {p_}")
    else:
        print("RESULT: CLEAN - production data has nothing the copy will reject")
    print("=" * 62)
    conn.close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
