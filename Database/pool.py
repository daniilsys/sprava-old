from dbutils.pooled_db import PooledDB
import pymysql
from pymysql.cursors import DictCursor
import os
from urllib.parse import urlparse

database_url = os.environ.get("JAWSDB_URL") or os.environ.get("CLEARDB_DATABASE_URL")

if database_url:
    parsed = urlparse(database_url)
    DB_HOST = parsed.hostname
    DB_USER = parsed.username
    DB_PASSWORD = parsed.password
    DB_NAME = parsed.path.lstrip("/")
    DB_PORT = parsed.port or 3306
else:
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "sprava")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))

pool = PooledDB(
    creator=pymysql,
    maxconnections=20,
    mincached=2,
    maxcached=5,
    maxshared=0,
    blocking=True,
    ping=1,
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    port=DB_PORT,
    charset='utf8mb4',
    cursorclass=DictCursor,
    autocommit=True
)

def get_cursor():
    conn = pool.connection()
    return conn, conn.cursor()