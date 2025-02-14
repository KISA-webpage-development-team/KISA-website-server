"""KISAWEB model (connection with mySQL database)."""
import server
import MySQLdb.cursors
import boto3
import os
import datetime
from botocore.config import Config

class Cursor:
    def __init__(self):
        self.cursor = server.db.connection.cursor(MySQLdb.cursors.DictCursor)
    
    def execute(self, sql, argsdict):
        self.cursor.execute(sql, argsdict)

    def fetchall(self):
        return self.cursor.fetchall()
    
    def fetchone(self):
        return self.cursor.fetchone()
    
    def lastrowid(self):
        return self.cursor.lastrowid
    
    def rowcount(self):
        return self.cursor.rowcount
    
    def rollback(self):
        server.db.connection.rollback()
    
    def __del__(self):
        server.db.connection.commit()
        self.cursor.close()

class AWSClient:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            region_name=os.getenv("AWS_REGION", "us-east-2"),
            config=Config(signature_version='s3v4')
        )
        self.cloudfront = boto3.client('cloudfront')

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