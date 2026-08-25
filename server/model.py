"""KISAWEB model (database and AWS integrations)."""
import server
import MySQLdb.cursors
import boto3
import os
import datetime
import json
from botocore.config import Config

try:
    import psycopg2
    import psycopg2.extras
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

class Cursor:
    def __init__(self):
        self._lastrowid = None
        self.engine = DATABASE_ENGINE

        if self.engine == "postgres":
            if psycopg2 is None:
                raise RuntimeError("psycopg2 is required when DATABASE_ENGINE=postgres")
            database_url = _postgres_url()
            if not database_url:
                raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL is required when DATABASE_ENGINE=postgres")
            self.connection = psycopg2.connect(database_url)
            self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
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
    
    def __del__(self):
        try:
            self.connection.commit()
            self.cursor.close()
            if self.engine == "postgres":
                self.connection.close()
        except Exception:
            pass

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
