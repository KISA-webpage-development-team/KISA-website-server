"""KISA website development configuration."""

import pathlib

# Root of this application, useful if it doesn't occupy an entire domain
APPLICATION_ROOT = '/'

# Secret key for encrypting cookies
SECRET_KEY = b'\xb7\x94x\x8c\x96\x96C.\xd4D%e/V\x86\xa6SJ\x8f\xb0=\x02\x19P'
SESSION_COOKIE_NAME = 'login'

# File Upload to var/uploads/
CLOUDFRONT_URL = "https://d1jb1ppquwym6d.cloudfront.net"

# mySQL configurations
MYSQL_HOST = 'awseb-e-bxtm2zpybp-stack-awsebrdsdatabase-7pth6zviixzm.crcom8asae83.us-east-2.rds.amazonaws.com'
MYSQL_USER = 'admin'
MYSQL_PASSWORD = 'Kisa_umich_23'
MYSQL_DB = 'ebdb'