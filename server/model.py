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
import threading
import flask
from botocore.config import Config

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except ImportError:
    psycopg2 = None


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
# gunicorn serves this app with a single gthread worker, and each request uses
# one connection, so the pool only has to cover that worker's threads. It is
# built on first use, which keeps it on the right side of gunicorn's fork.
POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "16"))

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
                _pool = psycopg2.pool.ThreadedConnectionPool(POOL_MIN, POOL_MAX, database_url)
    return _pool


def _checkout():
    """Take a live connection from the pool.

    The pooler can drop an idle connection without the handle noticing, so every
    checkout is probed first. That round trip costs far less than the TCP, TLS
    and auth handshakes of opening a new connection.

    Returns (connection, came_from_pool).
    """
    pool = _get_pool()
    failure = None
    for _ in range(3):
        try:
            connection = pool.getconn()
        except psycopg2.pool.PoolError:
            # Saturated. Fall back to a dedicated connection so a burst degrades
            # to the old one-per-request behaviour rather than failing requests.
            return psycopg2.connect(_postgres_url()), False
        try:
            if connection.closed:
                raise psycopg2.InterfaceError("connection already closed")
            with connection.cursor() as probe:
                probe.execute("SELECT 1")
            connection.rollback()
            return connection, True
        except psycopg2.Error as error:
            failure = error
            pool.putconn(connection, close=True)
    raise failure


def _checkin(connection, from_pool, close=False):
    try:
        if from_pool:
            _get_pool().putconn(connection, close=close)
        else:
            connection.close()
    except Exception:
        pass


def _request_connection():
    """Return (connection, caller_owns_it, came_from_pool) for the request.

    Flask-MySQLdb already gives every cursor in a request the same connection.
    Matching that on the Postgres side keeps it to one connection per request
    instead of one per cursor, and makes an explicit rollback undo the request's
    work rather than a single cursor's.
    """
    if not flask.has_app_context():
        connection, from_pool = _checkout()
        return connection, True, from_pool
    connection = getattr(flask.g, "_db_connection", None)
    if connection is None:
        connection, from_pool = _checkout()
        flask.g._db_connection = connection
        flask.g._db_from_pool = from_pool
    return connection, False, getattr(flask.g, "_db_from_pool", True)


class Cursor:
    def __init__(self):
        self._lastrowid = None
        self._closed = False
        self._owns_connection = False
        self._from_pool = False
        self.engine = DATABASE_ENGINE

        if self.engine == "postgres":
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is required when DATABASE_ENGINE=postgres")
            self.connection, self._owns_connection, self._from_pool = _request_connection()
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
            _checkin(self.connection, self._from_pool, close=broken)

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
        from_pool = flask.g.pop("_db_from_pool", True)
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
    _checkin(connection, from_pool, close=broken)


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
