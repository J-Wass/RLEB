from threading import Lock
import time
from typing import NamedTuple
import psycopg2
from psycopg2.extras import execute_values
import os

# This is bad code, don't tell anyone I wrote this.
try:
    import rleb_secrets
except Exception as e:
    rleb_secrets = {}
    print("rleb_secrets.py not found, using keys in environment settings.")


class Remindme(NamedTuple):
    """Encapsulation of data needed to trigger a !remindme notification."""

    remindme_id: int
    discord_username: str
    message: str
    trigger_timestamp: int
    channel_id: str


class Data(object):
    _singleton = None

    # Locks usage of database and memory caches to guarantee atomicity.
    _db_lock = Lock()

    # ONLY USE WITH _DB_LOCK. Generic cache, mapping a string key to any object.
    _cache = {}

    def __init__(self):
        raise RuntimeError("Call singleton() instead")

    def _empty_cache(cache_key: str) -> None:
        """Safely removes cache_key and its memory from the internal data cache."""
        if cache_key in Data._cache:
            del Data._cache[cache_key]

    @classmethod
    def singleton(cls):
        if cls._singleton is None:
            cls._singleton = cls.__new__(cls)
        return cls._singleton

    def postgres_connection(self):
        """MUST_HAVE_DB_LOCK. Returns the postgresSQL connection."""

        if "connection" in Data._cache:
            return Data._cache["connection"]

        connection = psycopg2.connect(
            dbname=os.environ.get("DB_NAME") or rleb_secrets.DB_NAME,
            host=os.environ.get("DB_HOST") or rleb_secrets.DB_HOST,
            user=os.environ.get("DB_USER") or rleb_secrets.DB_USER,
            port=os.environ.get("DB_PORT") or rleb_secrets.DB_PORT,
            password=os.environ.get("DB_PASSWORD") or rleb_secrets.DB_PASSWORD,
        )
        Data._cache["connection"] = connection
        return connection

    def write_remindme(
        self, user: str, message: str, elapsed_time: int, channel_id: int
    ) -> Remindme:
        """Adds a remindme notification to the database."""
        target_timestamp = elapsed_time + time.time()
        remindme_id = -1
        with Data._db_lock:

            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO remindme (discord_username, remindme_message, channel_id, trigger_timestamp) VALUES (%s, %s, %s, %s) RETURNING remindme_id;""",
                (user, message, channel_id, target_timestamp),
            )
            remindme_id = cursor.fetchone()[0]
            db.commit()
        return Remindme(remindme_id, user, message, target_timestamp, channel_id)

    def delete_remindme(self, remindme_id: int) -> None:
        """Deletes a remindme notification from db. Should be used after a remindme is triggered."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                """DELETE FROM remindme WHERE remindme_id = %s;""",
                (remindme_id,),
            )
            db.commit()

    def read_remindmes(self) -> list[Remindme]:
        """Returns all remindmes stored in the db."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM remindme""")
            remindmes = []
            for r in list(cursor.fetchall()):
                # Unpack the sql columns into the Remindme object.
                remindmes.append(Remindme(r[0], r[1], r[2], r[4], r[3]))
            return remindmes

    def write_already_warned_scheduled_post(
        self, log_id: int, seconds_since_epoch: int
    ) -> None:
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO already_warned_scheduled_posts VALUES (%s, %s);""",
                (log_id, seconds_since_epoch),
            )
            db.commit()

    def read_already_warned_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        """Returns a list of log ids for already warned scheduled posts."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                """SELECT id FROM already_warned_scheduled_posts WHERE seconds_since_epoch > %s;""",
                (min_seconds_since_epoch,),
            )
            post_ids = list(map(lambda x: x[0], cursor.fetchall()))
            return post_ids

    def write_already_warned_confirmed_post(
        self, log_id: int, seconds_since_epoch: int
    ) -> None:
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO already_confirmed_scheduled_posts VALUES (%s, %s);""",
                (log_id, seconds_since_epoch),
            )
            db.commit()

    def read_already_confirmed_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        """Returns a list of log ids for already confirmed scheduled posts."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                """SELECT post_id FROM already_confirmed_scheduled_posts WHERE seconds_since_epoch > %s;""",
                (min_seconds_since_epoch,),
            )
            post_ids = list(map(lambda x: x[0], cursor.fetchall()))
            return post_ids

    def write_to_logs(self, logs: list[str]) -> None:
        """ "Writes all logs to the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            memory_logs_tuples = list(map(lambda x: (x,), logs))
            psycopg2.extras.execute_values(
                cursor, "INSERT INTO logs VALUES %s", memory_logs_tuples
            )
            db.commit()

        Data._empty_cache("logs")

    def read_logs(self) -> list[str]:
        """ "Reads logs to the database."""
        with Data._db_lock:

            if "logs" in Data._cache:
                return Data._cache["logs"]

            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM logs ORDER BY log DESC;")
            all_logs = cursor.fetchall()
            Data._cache["logs"] = all_logs
            return all_logs

    def add_triflair(self, flair_to_add) -> list[str]:
        """ "Yeets a triflair out of the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            # NOTE: For legacy reasons, triflairs are called "dualflairs" in postgres.
            cursor.execute("""INSERT INTO dualflairs VALUES (%s)""", (flair_to_add,))
            db.commit()

        Data._empty_cache("triflair")

    def read_triflairs(self) -> list[str]:
        """ "Reads all the triflair from the database."""
        with Data._db_lock:

            if "triflair" in Data._cache:
                return Data._cache["triflair"]

            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM dualflairs;")
            all_dualflairs = cursor.fetchall()
            Data._cache["dualflairs"] = all_dualflairs
            return all_dualflairs

    def yeet_triflair(self, flair_to_remove) -> list[str]:
        """ "Yeets a triflair out of the database."""
        with Data._db_lock:
            db = self.postgres_connection()
            cursor = db.cursor()
            cursor.execute(
                "DELETE FROM dualflairs WHERE dualflair = %s", (flair_to_remove,)
            )
            db.commit()

        Data._empty_cache("triflair")
