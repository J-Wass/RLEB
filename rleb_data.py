from threading import Lock
import psycopg2
from psycopg2.extras import execute_values
import os

# This is bad code, don't tell anyone I wrote this.
try:
    import secrets
except Exception as e:
    secrets = {}
    print("secrets.py not found, using keys in environment settings.")

class Data(object):
    _singleton = None
    _db_lock = Lock()

    def __init__(self):
        raise RuntimeError('Call singleton() instead')

    @classmethod
    def singleton(cls):
        if cls._singleton is None:
            cls._singleton = cls.__new__(cls)
        return cls._singleton

    def postgres_connection(self):
        """MUST_HAVE_DB_LOCK. Returns a new postgresSQL connection."""
        return psycopg2.connect(
            dbname=os.environ.get('DB_NAME') or secrets.DB_NAME,
            host=os.environ.get('DB_HOST') or secrets.DB_HOST,
            user=os.environ.get('DB_USER') or secrets.DB_USER,
            port=os.environ.get('DB_PORT') or secrets.DB_PORT,
            password=os.environ.get('DB_PASSWORD') or secrets.DB_PASSWORD,
        )

    def write_already_warned_scheduled_post(self, log_id: int, seconds_since_epoch: int) -> None:
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""INSERT INTO already_warned_scheduled_posts VALUES (%s, %s);""", 
                (log_id, seconds_since_epoch))
            db.commit()

    def read_already_warned_scheduled_posts(self, min_seconds_since_epoch) -> list[int]:
        """"Returns a list of log ids for already warned scheduled posts."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""SELECT id FROM already_warned_scheduled_posts WHERE seconds_since_epoch > %s;""", (min_seconds_since_epoch,))
            log_ids = list(map(lambda x: x[0],cursor.fetchall()))
            return log_ids
