"""Pocha event rehearsal against production.

Creates a clearly marked throwaway pocha, menus and load-test users directly
in the database, drives the real event flow for N virtual users over HTTPS and
WebSocket while three admin sessions cycle order statuses on the dashboard,
records per-step latencies, then deletes everything it created and verifies
the row counts. Everything it creates is scoped to one pocha id and to emails
ending in @loadtest.invalid, and only those rows are deleted.

The database URL is obtained in memory from the Elastic Beanstalk environment
through the AWS CLI profile and is never written anywhere. SECRET_KEY is read
from .env to sign the virtual users' tokens.

Usage (from the server directory, after `pip install -r requirements.txt websocket-client`):
    venv/bin/python rehearsal/rehearsal.py 5 5        # dry run, 5 users
    venv/bin/python rehearsal/rehearsal.py 250 60     # the real one
Arguments: number of users, ramp-up seconds. Results append to
rehearsal/rehearsal_results.txt.
"""
import json
import random
import ssl
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import certifi
import jwt
import psycopg2
import websocket

HERE = Path(__file__).resolve().parent
N = int(sys.argv[1])
RAMP = float(sys.argv[2])
RESULTS = HERE / "rehearsal_results.txt"
BASE = "https://umichkisa-api.com"
ORIGIN = "https://www.umichkisa.com"
CTX = ssl.create_default_context(cafile=certifi.where())
DOMAIN = "loadtest.invalid"
ADMIN = f"loadtest-admin@{DOMAIN}"
SECRET = next(line.split("=", 1)[1].strip() for line in open(HERE.parent / ".env") if line.startswith("SECRET_KEY="))
AWS = ["aws", "--profile", "kisa-web-app-dev-1", "--region", "us-east-2"]
INSTANCE = "i-0090e24a6e085de58"
OK = (200, 201, 204, "ok")


def db_url():
    return subprocess.check_output(AWS + [
        "elasticbeanstalk", "describe-configuration-settings",
        "--application-name", "KISA-api", "--environment-name", "KISA-api-green",
        "--query", "ConfigurationSettings[0].OptionSettings[?Namespace=='aws:elasticbeanstalk:application:environment' && OptionName=='DATABASE_URL'].Value | [0]",
        "--output", "text"], text=True).strip()


def token(email):
    return jwt.encode({"id": email}, SECRET, algorithm="HS256")


# ---- metrics ----------------------------------------------------------------
latencies = {}
events = {"order-created": 0, "status-change": 0, "socket errors": 0}
lock = threading.Lock()


def record(step, status, seconds):
    with lock:
        latencies.setdefault(step, []).append((status, seconds))


def call(step, email, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": f"Bearer {token(email)}", "Origin": ORIGIN, "Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=60, context=CTX) as response:
            status, out = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, out = error.code, error.read()
    except Exception as error:
        status, out = type(error).__name__, b""
    record(step, status, time.time() - started)
    try:
        return status, json.loads(out) if out else None
    except Exception:
        return status, None


class Socket:
    """One Socket.IO client over WebSocket; answers pings and counts events."""

    def __init__(self, email, pocha_id=None):
        self.stop = False
        self.ok = False
        query = f"?EIO=4&transport=websocket&email={email}" + (f"&pochaId={pocha_id}" if pocha_id else "")
        started = time.time()
        try:
            self.ws = websocket.create_connection(f"wss://umichkisa-api.com/socket.io/{query}", origin=ORIGIN,
                                                  timeout=30, sslopt={"ca_certs": certifi.where()})
            self.ws.recv()
            self.ws.send("40" + json.dumps({"token": token(email)}))
            self.ok = self.ws.recv().startswith("40")
        except Exception:
            with lock:
                events["socket errors"] += 1
        record("socket connect", "ok" if self.ok else "fail", time.time() - started)
        if self.ok:
            threading.Thread(target=self.reader, daemon=True).start()

    def reader(self):
        self.ws.settimeout(5)
        while not self.stop:
            try:
                message = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                break
            if message == "2":
                self.ws.send("3")
            elif message.startswith("42"):
                name = json.loads(message[2:])[0]
                key = "order-created" if name == "order-created" else "status-change" if name.startswith("status-change") else None
                if key:
                    with lock:
                        events[key] += 1

    def close(self):
        self.stop = True
        try:
            self.ws.close()
        except Exception:
            pass


# ---- one virtual customer ---------------------------------------------------
def customer(i, pocha_id, menus):
    email = f"loadtest-{i:03}@{DOMAIN}"
    time.sleep(i * RAMP / max(N, 1))
    sock = Socket(email)

    def think():
        time.sleep(random.uniform(0.3, 1.0))

    for menu in random.sample(menus, 3):
        call("cart add", email, "POST", f"/api/v2/pocha/cart/{email}/{pocha_id}/",
             {"menuID": menu, "quantity": random.randint(1, 2)})
        think()
    call("cart get", email, "GET", f"/api/v2/pocha/cart/{email}/{pocha_id}/")
    think()
    call("checkout info", email, "GET", f"/api/v2/pocha/cart/{email}/{pocha_id}/checkout-info/")
    think()
    call("check stock", email, "PUT", f"/api/v2/pocha/payment/{email}/{pocha_id}/check-stock/", {})
    think()
    call("pay result", email, "PUT", f"/api/v2/pocha/payment/{email}/{pocha_id}/pay-result/", {"result": "success"})
    think()
    call("my orders", email, "GET", f"/api/v2/pocha/order/{email}/{pocha_id}/")
    return sock


# ---- admin dashboard sessions -----------------------------------------------
def admin(pocha_id, stop_at):
    sock = Socket(ADMIN, pocha_id)
    while time.time() < stop_at:
        status, board = call("dashboard", ADMIN, "GET", f"/api/v2/pocha/dashboard/{pocha_id}/")
        items = []
        if status == 200 and board:
            items = [item for bucket in ("pending", "preparing", "ready") for item in board.get(bucket, [])]
        for item in random.sample(items, min(len(items), 5)):
            call("change status", ADMIN, "PUT", f"/api/v2/pocha/dashboard/{item['orderItemID']}/change-status/", {})
        time.sleep(1.0)
    call("dashboard closed", ADMIN, "GET", f"/api/v2/pocha/dashboard/{pocha_id}/closed/")
    return sock


# ---- setup / cleanup in the database ------------------------------------------
def setup(conn):
    with conn.cursor() as c:
        c.execute("SELECT count(*) FROM users WHERE email LIKE %s", (f"%@{DOMAIN}",))
        assert c.fetchone()[0] == 0, "load-test users already exist; clean up first"
        rows = [c.mogrify("(%s,%s,2000,1,1,'LOADTEST',2030)", (f"loadtest-{i:03}@{DOMAIN}", f"Load Test {i:03}")).decode() for i in range(N)]
        rows.append(c.mogrify("(%s,%s,2000,1,1,'LOADTEST',2030)", (ADMIN, "Load Test Admin")).decode())
        c.execute("INSERT INTO users (email, fullname, bornyear, bornmonth, borndate, major, gradyear) VALUES " + ",".join(rows))
        c.execute("INSERT INTO admins (email) VALUES (%s)", (ADMIN,))
        c.execute("INSERT INTO pocha (startdate, enddate, title, description) VALUES "
                  "('2020-01-01', '2020-01-02', 'LOADTEST auto-deleted', 'rehearsal data, deleted by the script') RETURNING pochaid")
        pocha_id = c.fetchone()[0]
        c.execute("INSERT INTO menu (namekor, nameeng, category, price, stock, isimmediateprep, parentpochaid, agecheckrequired) VALUES "
                  "('부하테스트 안주1', 'LT food 1', 'food', 8.0, 1000000, false, %(p)s, false), "
                  "('부하테스트 안주2', 'LT food 2', 'food', 10.0, 1000000, false, %(p)s, false), "
                  "('부하테스트 음료1', 'LT drink 1', 'drink', 3.0, 1000000, true, %(p)s, false), "
                  "('부하테스트 음료2', 'LT drink 2', 'drink', 12.0, 1000000, true, %(p)s, true) RETURNING menuid", {"p": pocha_id})
        menus = [row[0] for row in c.fetchall()]
    conn.commit()
    return pocha_id, menus


def cleanup(conn, pocha_id):
    with conn.cursor() as c:
        c.execute('DELETE FROM orderitem WHERE parentorderid IN (SELECT orderid FROM "order" WHERE parentpochaid = %s)', (pocha_id,))
        items = c.rowcount
        c.execute('DELETE FROM "order" WHERE parentpochaid = %s', (pocha_id,))
        orders = c.rowcount
        c.execute("DELETE FROM menu WHERE parentpochaid = %s", (pocha_id,))
        c.execute("DELETE FROM pocha WHERE pochaid = %s", (pocha_id,))
        c.execute("DELETE FROM notificationarns WHERE email LIKE %s", (f"%@{DOMAIN}",))
        c.execute("DELETE FROM admins WHERE email LIKE %s", (f"%@{DOMAIN}",))
        c.execute("DELETE FROM users WHERE email LIKE %s", (f"%@{DOMAIN}",))
        users = c.rowcount
    conn.commit()
    with conn.cursor() as c:
        c.execute('SELECT (SELECT count(*) FROM users WHERE email LIKE %s) + (SELECT count(*) FROM pocha WHERE pochaid = %s) '
                  '+ (SELECT count(*) FROM menu WHERE parentpochaid = %s) + (SELECT count(*) FROM "order" WHERE parentpochaid = %s)',
                  (f"%@{DOMAIN}", pocha_id, pocha_id, pocha_id))
        left = c.fetchone()[0]
    return items, orders, users, left


# ---- run ------------------------------------------------------------------------
lines = [f"== rehearsal: {N} users, {RAMP:.0f}s ramp, 3 admin dashboards  ({datetime.now():%Y-%m-%d %H:%M}) =="]


def say(text):
    print(text, flush=True)
    lines.append(text)


conn = psycopg2.connect(db_url(), connect_timeout=30)
pocha_id, menus = setup(conn)
say(f"created pocha {pocha_id} with {len(menus)} menus and {N}+1 users")
started = datetime.now(timezone.utc)
sockets = []
try:
    with ThreadPoolExecutor(N + 3) as pool:
        customers = [pool.submit(customer, i, pocha_id, menus) for i in range(N)]
        admins = [pool.submit(admin, pocha_id, time.time() + RAMP + 40) for _ in range(3)]
        sockets = [f.result() for f in customers] + [f.result() for f in admins]
    time.sleep(3)
    say(f"socket events received  order-created={events['order-created']}  status-change={events['status-change']}  socket errors={events['socket errors']}")
    say(f"{'step':16} {'n':>5} {'errors':>6} {'median':>7} {'p95':>7} {'max':>7}")
    for step in ["socket connect", "cart add", "cart get", "checkout info", "check stock", "pay result",
                 "my orders", "dashboard", "change status", "dashboard closed"]:
        rows = latencies.get(step, [])
        if not rows:
            continue
        times = sorted(t for _, t in rows)
        bad = sum(1 for status, _ in rows if status not in OK)
        say(f"{step:16} {len(times):>5} {bad:>6} {statistics.median(times):>6.2f}s "
            f"{times[max(int(len(times) * 0.95) - 1, 0)]:>6.2f}s {times[-1]:>6.2f}s")
    failures = {}
    for step, rows in latencies.items():
        for status, _ in rows:
            if status not in OK:
                failures[(step, status)] = failures.get((step, status), 0) + 1
    if failures:
        say("non-success responses: " + ", ".join(f"{k[0]} {k[1]} x{v}" for k, v in sorted(failures.items(), key=str)))
    with conn.cursor() as c:
        c.execute('SELECT count(*) FROM "order" WHERE parentpochaid = %s AND ispaid', (pocha_id,))
        paid = c.fetchone()[0]
        c.execute('SELECT count(*), sum(CASE WHEN status = %s THEN 1 ELSE 0 END) FROM orderitem '
                  'WHERE parentorderid IN (SELECT orderid FROM "order" WHERE parentpochaid = %s)', ("closed", pocha_id))
        total, closed = c.fetchone()
    say(f"database after run: paid orders={paid}/{N}  order items={total}  closed by admins={closed}")
finally:
    for sock in sockets:
        sock.close()
    items, orders, users, left = cleanup(conn, pocha_id)
    say(f"cleanup: deleted {items} order items, {orders} orders, {users} users, the pocha and its menus; rows left behind: {left}")
    conn.close()
ended = datetime.now(timezone.utc)
try:
    cpu = subprocess.check_output(AWS + [
        "cloudwatch", "get-metric-statistics", "--namespace", "AWS/EC2", "--metric-name", "CPUUtilization",
        "--dimensions", f"Name=InstanceId,Value={INSTANCE}",
        "--start-time", started.strftime("%Y-%m-%dT%H:%M:%SZ"), "--end-time", ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--period", "60", "--statistics", "Maximum", "--query", "max(Datapoints[].Maximum)", "--output", "text"], text=True).strip()
    say(f"instance CPU during the run (max of 1-minute samples, may lag a few minutes): {cpu}%")
except Exception as error:
    say(f"cpu metric unavailable: {error}")
with open(RESULTS, "a") as f:
    f.write("\n".join(lines) + "\n\n")
