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

    # Locks usage of database and memory caches to guarantee atomicity.
    _db_lock = Lock()

    # ONLY USE WITH _DB_LOCK. Generic cache, mapping a string key to any object.
    _cache = {}

    def __init__(self):
        raise RuntimeError('Call singleton() instead')

    @classmethod
    def singleton(cls):
        if cls._singleton is None:
            cls._singleton = cls.__new__(cls)
        return cls._singleton

    def postgres_connection(self):
        """MUST_HAVE_DB_LOCK. Returns the postgresSQL connection."""

        if 'connection' in Data._cache:
            return Data._cache['connection']

        connection = psycopg2.connect(
            dbname=os.environ.get('DB_NAME') or secrets.DB_NAME,
            host=os.environ.get('DB_HOST') or secrets.DB_HOST,
            user=os.environ.get('DB_USER') or secrets.DB_USER,
            port=os.environ.get('DB_PORT') or secrets.DB_PORT,
            password=os.environ.get('DB_PASSWORD') or secrets.DB_PASSWORD,
        )
        Data._cache['connection'] = connection
        return connection

    def write_already_warned_scheduled_post(self, log_id: int, seconds_since_epoch: int) -> None:
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""INSERT INTO already_warned_scheduled_posts VALUES (%s, %s);""", 
                (log_id, seconds_since_epoch))
            db.commit()

    def read_already_warned_scheduled_posts(self, min_seconds_since_epoch: int) -> list[int]:
        """"Returns a list of log ids for already warned scheduled posts."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""SELECT id FROM already_warned_scheduled_posts WHERE seconds_since_epoch > %s;""", (min_seconds_since_epoch,))
            post_ids = list(map(lambda x: x[0],cursor.fetchall()))
            return post_ids

    def write_already_warned_confirmed_post(self, log_id: int, seconds_since_epoch: int) -> None:
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""INSERT INTO already_confirmed_scheduled_posts VALUES (%s, %s);""", 
                (log_id, seconds_since_epoch))
            db.commit()

    def read_already_confirmed_scheduled_posts(self, min_seconds_since_epoch: int) -> list[int]:
        """"Returns a list of log ids for already confirmed scheduled posts."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""SELECT post_id FROM already_confirmed_scheduled_posts WHERE seconds_since_epoch > %s;""", (min_seconds_since_epoch,))
            post_ids = list(map(lambda x: x[0],cursor.fetchall()))
            return post_ids

    def write_to_logs(self, logs: list[str]) -> None:
        """"Writes all logs to the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            memory_logs_tuples = list(map(lambda x: (x, ), logs))
            psycopg2.extras.execute_values(cursor, "INSERT INTO logs VALUES %s",
                                   memory_logs_tuples)
            db.commit()

    def read_logs(self) -> list[str]:
        """"Reads logs to the database."""
        with Data._db_lock:
            
            if 'logs' in Data._cache:
                return Data._cache['logs']

            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM logs;")
            all_logs = cursor.fetchall()
            Data._cache['logs'] = all_logs 
            return 

    def add_dualflair(self, flair_to_add) -> list[str]:
        """"Yeets a dualflair out of the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""INSERT INTO dualflairs VALUES (%s)""",
                            (flair_to_add, ))
            db.commit()  
    
    def read_dualflairs(self) -> list[str]:
        """"Reads all the dualflairs from the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM dualflairs;")
            return cursor.fetchall()  

    def yeet_dualflair(self, flair_to_remove) -> list[str]:
        """"Yeets a dualflair out of the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("DELETE FROM dualflairs WHERE dualflair = %s",
                               (flair_to_remove, ))
            db.commit()          

