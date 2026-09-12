"""Shared fixtures for the API tests.

The tests run the real Flask app against a real Postgres database, so they
need one: set TEST_DATABASE_URL to a scratch database (for example a local
`postgres:17` container). The database is wiped and rebuilt from
queries/supabase_schema.sql at the start of the session, so it must never be
a database that holds data anyone cares about.
"""
import json
import os
import pathlib
import sys

import jwt
import psycopg2
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TEST_SECRET_KEY = "test-secret-key"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"

# Production-shaped hosts are refused outright: the session fixture drops the
# public schema of whatever database it is pointed at.
_REFUSED_HOSTS = ("supabase.co", "supabase.com", "amazonaws.com")

if TEST_DATABASE_URL and any(host in TEST_DATABASE_URL for host in _REFUSED_HOSTS):
    raise RuntimeError("TEST_DATABASE_URL points at a hosted database; use a scratch database")

# server.model reads DATABASE_ENGINE at import time and config.py loads .env
# without overriding existing variables, so these must be set before the
# import below.
os.environ["DATABASE_ENGINE"] = "postgres"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "postgresql://unset"
os.environ["SECRET_KEY"] = TEST_SECRET_KEY
os.environ["FLASK_ENV"] = "development"
os.environ["DB_POOL_WAIT"] = "5"

import server  # noqa: E402
import server.model  # noqa: E402

TABLES = [
    "notificationarns", "orderitem", '"order"', "menu", "pocha",
    "commentlikes", "postlikes", "comments", "posts", "admins", "users",
]


@pytest.fixture(scope="session")
def database():
    """A fresh schema for the whole session; yields an autocommit connection."""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    connection = psycopg2.connect(TEST_DATABASE_URL)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cursor.execute((ROOT / "queries" / "supabase_schema.sql").read_text())
    yield connection
    connection.close()


@pytest.fixture
def db(database):
    """Empty tables (identities reset) and an autocommit connection for fixtures."""
    with database.cursor() as cursor:
        cursor.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
    return database


@pytest.fixture
def client():
    server.application.config["TESTING"] = True
    return server.application.test_client()


@pytest.fixture
def auth():
    """auth(email) -> headers carrying a token the API accepts for that user."""
    def headers(email):
        token = jwt.encode({"id": email}, TEST_SECRET_KEY, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    return headers


@pytest.fixture
def query_log(monkeypatch):
    """Every SQL statement the request layer executes, in order.

    Counts calls to server.model.Cursor.execute; the pool's connection probe
    bypasses that method and is not counted.
    """
    executed = []
    original = server.model.Cursor.execute

    def recording(self, sql, argsdict):
        executed.append(" ".join(sql.split()))
        return original(self, sql, argsdict)

    monkeypatch.setattr(server.model.Cursor, "execute", recording)
    return executed


@pytest.fixture
def golden():
    """golden(name, body) asserts the response body matches tests/golden/<name>.json.

    Run with UPDATE_GOLDEN=1 to (re)write the files instead of comparing.
    """
    def check(name, body):
        path = GOLDEN_DIR / f"{name}.json"
        if isinstance(body, (dict, list)):
            body = json.dumps(body, sort_keys=True).encode()
        if os.getenv("UPDATE_GOLDEN"):
            path.write_bytes(body)
            return
        assert path.exists(), f"missing golden file {path}; run with UPDATE_GOLDEN=1"
        assert body == path.read_bytes(), f"response differs from {path.name}"
    return check


@pytest.fixture
def pocha_scenario(db):
    """Two pochas, three users, and orders that exercise every branch of the
    pocha read endpoints. Identity columns restart at 1, so ids are fixed:

    menu 1 Kimbap (food, not immediate)  menu 2 Soju (drink, immediate, age check)
    menu 3 Cola (drink, immediate)       menu 4 Ramen (pocha 2)

    order 1 admin, pocha 1, paid          order 2 student, pocha 1, paid
    order 3 student, pocha 1, cart        order 4 student, pocha 2, paid
    order 5 other, pocha 1, empty cart

    Order items are inserted interleaved across orders so that response
    ordering is exercised, not just membership.
    """
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (email, fullname, bornyear, bornmonth, borndate, major, gradyear) VALUES
                ('admin@example.com',   'Admin User',   2000, 1, 1, 'CS', 2026),
                ('student@example.com', 'Student User', 2001, 2, 2, 'EE', 2027),
                ('other@example.com',   'Other User',   2002, 3, 3, 'ME', 2028);
            INSERT INTO admins (email) VALUES ('admin@example.com');
            INSERT INTO pocha (startdate, enddate, title, description) VALUES
                ('2026-09-01', '2026-09-30', 'Test Pocha',  'the pocha under test'),
                ('2026-10-01', '2026-10-31', 'Other Pocha', 'must never leak into pocha 1 responses');
            INSERT INTO menu (namekor, nameeng, category, price, stock, isimmediateprep, parentpochaid, agecheckrequired) VALUES
                ('김밥', 'Kimbap', 'food',  5.0,  20, false, 1, false),
                ('소주', 'Soju',   'drink', 12.5, 10, true,  1, true),
                ('콜라', 'Cola',   'drink', 2.0,  30, true,  1, false),
                ('라면', 'Ramen',  'food',  7.0,  5,  false, 2, false);
            INSERT INTO "order" (email, parentpochaid, ispaid) VALUES
                ('admin@example.com',   1, true),
                ('student@example.com', 1, true),
                ('student@example.com', 1, false),
                ('student@example.com', 2, true),
                ('other@example.com',   1, false);
            INSERT INTO orderitem (status, quantity, parentorderid, menuid) VALUES
                ('pending',   1, 1, 1),
                ('pending',   1, 2, 1),
                ('preparing', 2, 1, 2),
                ('ready',     1, 2, 3),
                ('closed',    1, 1, 1),
                ('pending',   1, 1, 1),
                ('closed',    3, 2, 2),
                ('pending',   1, 3, 1),
                ('pending',   1, 3, 1),
                ('pending',   2, 3, 2),
                ('pending',   1, 4, 4);
        """)
    return db


@pytest.fixture
def bulletin_scenario(db):
    """Posts, comments and likes that exercise the board, comment and profile
    listings. Identity columns restart at 1, so ids are fixed:

    posts 1-6 student, 7-12 admin: community, not announcements (3 anonymous)
    post 13 and 15: community announcements   post 14: another board
    comments on post 1: 1 (children 3 (child 4), 5) and 2; comment 6 on post 2

    Timestamps are fixed so responses are reproducible.
    """
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (email, fullname, bornyear, bornmonth, borndate, major, gradyear) VALUES
                ('admin@example.com',   'Admin User',   2000, 1, 1, 'CS', 2026),
                ('student@example.com', 'Student User', 2001, 2, 2, 'EE', 2027),
                ('other@example.com',   'Other User',   2002, 3, 3, 'ME', 2028);
            INSERT INTO admins (email) VALUES ('admin@example.com');
            INSERT INTO posts (type, email, title, text, isannouncement, fullname, readcount, anonymous, created)
            SELECT 'community',
                   CASE WHEN i <= 6 THEN 'student@example.com' ELSE 'admin@example.com' END,
                   'Post ' || i, '<p>body ' || i || '</p>', false,
                   CASE WHEN i <= 6 THEN 'Student User' ELSE 'Admin User' END,
                   i * 3, i = 3, timestamp '2026-09-01 00:00:00' + i * interval '1 hour'
            FROM generate_series(1, 12) AS i;
            INSERT INTO posts (type, email, title, text, isannouncement, fullname, readcount, anonymous, created) VALUES
                ('community', 'admin@example.com', 'Notice A', '<p>notice</p>', true,  'Admin User', 40, false, '2026-09-02 00:00:00'),
                ('job',       'other@example.com', 'Job post', '<p>job</p>',    false, 'Other User', 0,  false, '2026-09-02 01:00:00'),
                ('community', 'admin@example.com', 'Notice B', '<p>notice</p>', true,  'Admin User', 41, false, '2026-09-02 02:00:00');
            INSERT INTO postlikes (email, postid) VALUES
                ('admin@example.com', 1), ('student@example.com', 1), ('other@example.com', 1),
                ('student@example.com', 12);
            INSERT INTO comments (email, postid, text, iscommentofcomment, parentcommentid, anonymous, secret, created) VALUES
                ('student@example.com', 1, 'top level one',      false, 0, false, false, '2026-09-03 00:00:00'),
                ('admin@example.com',   1, 'top level two',      false, 0, false, false, '2026-09-03 00:01:00'),
                ('other@example.com',   1, 'reply to one',       true,  1, true,  false, '2026-09-03 00:02:00'),
                ('student@example.com', 1, 'reply to the reply', true,  3, false, true,  '2026-09-03 00:03:00'),
                ('admin@example.com',   1, 'second reply to one', true, 1, false, false, '2026-09-03 00:04:00'),
                ('student@example.com', 2, 'on another post',    false, 0, false, false, '2026-09-03 00:05:00');
            INSERT INTO commentlikes (email, commentid) VALUES
                ('admin@example.com', 1), ('other@example.com', 1), ('student@example.com', 3);
        """)
    return db
