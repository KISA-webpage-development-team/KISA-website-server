"""KISAWEB model (database and AWS integrations)."""
import server
try:
    import MySQLdb.cursors
except ImportError:
    MySQLdb = None
import boto3
import os
import datetime
import json
import queue
import threading
import flask
from botocore.config import Config

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

# Under the gevent worker in the Procfile, psycopg2's C-level waits would block
# the whole event loop; psycogreen makes them cooperative. It only applies once
# gevent has patched the socket module, so a plain threaded process is
# unaffected.
try:
    from gevent import monkey as _gevent_monkey
except ImportError:
    _gevent_monkey = None

if psycopg2 is not None and _gevent_monkey is not None and _gevent_monkey.is_module_patched("socket"):
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()


DATABASE_ENGINE = os.getenv("DATABASE_ENGINE", "mysql").lower()

# Every camelCase column the API returns. Postgres folds unquoted identifiers to
# lowercase, so the map is derived from this one list -- adding a column here is
# the only step needed to keep the response shape stable.
CAMEL_COLUMNS = [
    "pochaID", "menuID", "orderID", "orderItemID", "parentPochaID", "parentOrderID",
    "nameKor", "nameEng", "isImmediatePrep", "ageCheckRequired", "isPaid",
    "readCount", "isAnnouncement", "isCommentOfComment", "parentCommentid",
    "startDate", "endDate", "endpointARN",
    "bornYear", "bornMonth", "bornDate", "gradYear",
]

PG_KEY_MAP = {column.lower(): column for column in CAMEL_COLUMNS}
PG_KEY_MAP["count"] = "COUNT(*)"

INSERT_RETURNING_COLUMNS = {
    "insert into posts": "postid",
    "insert into pocha": "pochaid",
    "insert into menu": "menuid",
    'insert into "order"': "orderid",
}


def _postgres_url():
    return os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")


def _normalize_row(row):
    if row is None:
        return None
    return {PG_KEY_MAP.get(key, key): value for key, value in dict(row).items()}


def _prepare_postgres_sql(sql):
    sql = sql.replace("`order`", '"order"')
    lowered = sql.lstrip().lower()
    returning_column = None

    if "returning" not in lowered:
        for prefix, column in INSERT_RETURNING_COLUMNS.items():
            if lowered.startswith(prefix):
                sql = sql.rstrip().rstrip(";") + f" RETURNING {column}"
                returning_column = column
                break

    return sql, returning_column

# ---- connection pool -------------------------------------------------------
# Each request uses one connection, and the pool is the throttle on database
# concurrency: when every connection is out, a request waits for one instead of
# opening more, which under gevent is a cheap yield and keeps the process from
# blowing past Supabase's connection limit. The pool is built on first use,
# which keeps it on the right side of gunicorn's fork.
#
# psycopg2's own pool is deliberately not used: it closes every returned
# connection beyond minconn, so under concurrency it reconnects on almost every
# request, and it holds its lock across connect(), which serialises those
# reconnects.
POOL_MAX = int(os.getenv("DB_POOL_MAX", "16"))
POOL_WAIT = float(os.getenv("DB_POOL_WAIT", "10"))


class _Pool:
    def __init__(self, database_url, maxconn):
        self._database_url = database_url
        self._idle = queue.LifoQueue()          # reuse the warmest connection first
        self._slots = threading.Semaphore(maxconn)
        self.in_use = 0                         # diagnostic only

    def getconn(self, timeout):
        if not self._slots.acquire(timeout=timeout):
            raise RuntimeError(f"no database connection became free within {timeout:g}s")
        try:
            try:
                connection = self._idle.get_nowait()
            except queue.Empty:
                connection = psycopg2.connect(self._database_url)
        except BaseException:
            self._slots.release()
            raise
        self.in_use += 1
        return connection

    def putconn(self, connection, close=False):
        self.in_use -= 1
        if close:
            try:
                connection.close()
            except Exception:
                pass
        else:
            self._idle.put(connection)
        self._slots.release()

    def idle(self):
        return self._idle.qsize()


_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                database_url = _postgres_url()
                if not database_url:
                    raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL is required when DATABASE_ENGINE=postgres")
                _pool = _Pool(database_url, POOL_MAX)
    return _pool


def _checkout():
    """Take a live connection from the pool.

    Waits up to POOL_WAIT seconds for a free slot. The pooler can drop an idle
    connection without the handle noticing, so every checkout is probed first;
    that round trip costs far less than the TCP, TLS and auth handshakes of
    opening a new connection.
    """
    pool = _get_pool()
    failure = None
    for _ in range(3):
        connection = pool.getconn(POOL_WAIT)
        try:
            if connection.closed:
                raise psycopg2.InterfaceError("connection already closed")
            with connection.cursor() as probe:
                probe.execute("SELECT 1")
            connection.rollback()
            return connection
        except psycopg2.Error as error:
            failure = error
            pool.putconn(connection, close=True)
    raise failure


def _checkin(connection, close=False):
    try:
        _get_pool().putconn(connection, close=close)
    except Exception:
        pass


def _request_connection():
    """Return (connection, caller_owns_it) for the current request.

    Flask-MySQLdb already gives every cursor in a request the same connection.
    Matching that on the Postgres side keeps it to one connection per request
    instead of one per cursor, and makes an explicit rollback undo the request's
    work rather than a single cursor's.
    """
    if not flask.has_app_context():
        return _checkout(), True
    connection = getattr(flask.g, "_db_connection", None)
    if connection is None:
        connection = _checkout()
        flask.g._db_connection = connection
    return connection, False


class Cursor:
    def __init__(self):
        self._lastrowid = None
        self._closed = False
        self._owns_connection = False
        self.engine = DATABASE_ENGINE

        if self.engine == "postgres":
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is required when DATABASE_ENGINE=postgres")
            self.connection, self._owns_connection = _request_connection()
            self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            if MySQLdb is None:
                raise RuntimeError("mysqlclient is required when DATABASE_ENGINE=mysql")
            self.connection = server.db.connection
            self.cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
    
    def execute(self, sql, argsdict):
        returning_column = None
        if self.engine == "postgres":
            sql, returning_column = _prepare_postgres_sql(sql)
        self.cursor.execute(sql, argsdict)
        if self.engine == "postgres" and returning_column:
            row = self.cursor.fetchone()
            self._lastrowid = row[returning_column] if row else None

    def fetchall(self):
        rows = self.cursor.fetchall()
        if self.engine == "postgres":
            return [_normalize_row(row) for row in rows]
        return rows
    
    def fetchone(self):
        row = self.cursor.fetchone()
        if self.engine == "postgres":
            return _normalize_row(row)
        return row
    
    def lastrowid(self):
        if self.engine == "postgres":
            return self._lastrowid
        return self.cursor.lastrowid
    
    def rowcount(self):
        return self.cursor.rowcount
    
    def rollback(self):
        self.connection.rollback()
    
    def close(self):
        """Finish with this cursor. Idempotent.

        Inside a request the connection goes back to the pool at teardown, not
        here, so several cursors can share it.
        """
        if self._closed:
            return
        self._closed = True

        if self.engine != "postgres":
            # Flask-MySQLdb owns this connection and closes it itself.
            try:
                self.connection.commit()
            except Exception:
                pass
            try:
                self.cursor.close()
            except Exception:
                pass
            return

        try:
            self.cursor.close()
        except Exception:
            pass

        if self._owns_connection:
            broken = False
            try:
                self.connection.commit()
            except Exception:
                broken = True
            _checkin(self.connection, close=broken)

    def __del__(self):
        # Safety net for a cursor built outside an application context.
        try:
            self.close()
        except Exception:
            pass


@server.application.teardown_appcontext
def _release_request_connection(error):
    """Commit and return the request's connection.

    Doing this here rather than in Cursor.__del__ returns the connection when
    the request ends instead of whenever the garbage collector runs, which is
    what left backends sitting 'idle in transaction'.
    """
    try:
        connection = flask.g.pop("_db_connection", None)
    except Exception:
        return
    if connection is None:
        return

    broken = False
    try:
        if error is None:
            connection.commit()
        else:
            connection.rollback()
    except Exception:
        broken = True
    _checkin(connection, close=broken)


class AWSClient:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            region_name=os.getenv("AWS_REGION", "us-east-2"),
            config=Config(signature_version='s3v4')
        )
        self.cloudfront = boto3.client('cloudfront')
        self.sns = boto3.client(
            'sns',
            region_name=os.getenv("AWS_REGION", "us-east-2")
        )
        self.platformApplicationArn = {
            "production": {
                "arn": "arn:aws:sns:us-east-2:220688543567:app/APNS/kisa-mobile-sns",
                "messagekey": "APNS"
            },
            "development": {
                "arn": "arn:aws:sns:us-east-2:220688543567:app/APNS_SANDBOX/kisa-mobile-sns-dev",
                "messagekey": "APNS_SANDBOX"
            }
        }

    def generate_presigned_url(self, intention, file_key, file_type):
        params = {
            "Bucket": os.getenv("S3_BUCKET_NAME"),
            "Key": file_key,
        }
        if intention == "put_object":
            params["ContentType"] = file_type

        return self.s3.generate_presigned_url(
            intention,
            params,
            ExpiresIn=3600
        )
    
    def create_invalidation(self, invalidate_paths):
        # cloudfront invalidation requires absolute path
        invalidate_paths = [f"/{path}" for path in invalidate_paths]

        self.cloudfront.create_invalidation(
            DistributionId=os.getenv("CLOUDFRONT_DISTRIBUTION_ID"),
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(invalidate_paths),
                    'Items': invalidate_paths
                },
                'CallerReference': str(datetime.datetime.now())
            }
        )

    def delete_object(self, key):
        self.s3.delete_object(
            Bucket=os.getenv('S3_BUCKET_NAME'),
            Key=key
        )

    def copy_object(self, key, new_key):
        self.s3.copy_object(
            Bucket=os.getenv("S3_BUCKET_NAME"),
            CopySource={"Bucket": os.getenv("S3_BUCKET_NAME"), "Key": key},
            Key=new_key
        )

    def move_object(self, key, new_key):
        self.copy_object(key, new_key)
        self.delete_object(key)

    def delete_uploaded_objects(self, keys):
        self.create_invalidation(keys)
        for key in keys:
            self.delete_object(key)

    def create_endpoint(self, token, email):
        return self.sns.create_platform_endpoint(
            PlatformApplicationArn=self.platformApplicationArn[os.getenv("FLASK_ENV")]["arn"],
            Token=token,
            CustomUserData=email
        )
    
    def send_notification(self, endpoint_arn, subject, title=None, body=None, silent=False, data=None):
        # 'APNS' for production and 'APNS_SANDBOX' for development
        messagekey = self.platformApplicationArn[os.getenv("FLASK_ENV")]["messagekey"]
        
        # Silent notification with custom data
        if silent and data:
            apns_payload = {
                "aps": {
                    "content-available": 1
                },
                "custom_data": data
            }
            
        # Regular push notification
        else:
            apns_payload = {
                "aps": {
                    "alert": {
                        "title": title or subject,
                        "body": body or "No message provided"
                    },
                    "badge": 1,
                    "sound": "default"
                }
            }

        message_payload = {
            messagekey: json.dumps(apns_payload),
            "default": body or subject or "Update available"
        }

        self.sns.publish(
            TargetArn=endpoint_arn,
            Subject=subject,
            Message=json.dumps(message_payload),
            MessageStructure='json'
        )
