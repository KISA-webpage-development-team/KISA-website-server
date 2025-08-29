import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file (only in local dev)
load_dotenv()

"""KISA website development configuration."""

# Root of this application
APPLICATION_ROOT = '/'

# Secret key for encrypting cookies
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key")  # Default for safety

# Session cookie name
SESSION_COOKIE_NAME = 'login'

# File Upload to CloudFront
CLOUDFRONT_URL = os.getenv("CLOUDFRONT_URL", "https://d1jb1ppquwym6d.cloudfront.net")

# MySQL Configurations
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")

# Cloudinary Configurations
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Database selection
MYSQL_DB = 'testdb' if os.getenv('FLASK_ENV') == 'development' else 'ebdb'