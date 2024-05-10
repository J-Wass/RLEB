from datetime import datetime
import time
from typing import Optional
import psycopg2
import os
from dataclasses import dataclass

# This is bad code, don't tell anyone I wrote this.
try:
    import rleb_secrets
except Exception as e:
    rleb_secrets = {}
    print("rleb_secrets.py not found, using keys in environment settings.")


@dataclass
class UserStatistics:
    discord_username: str
    commands_used: int
    thanks_given: int


@dataclass
class Remindme:
    """Encapsulation of data needed to trigger a !remindme notification."""

    remindme_id: int
    discord_username: str
    message: str
    trigger_timestamp: int
    channel_id: str


@dataclass
class AutoUpdate:
    """Encapsulation of data for an autoupdate job."""

    auto_update_id: int
    reddit_url: str
    liquipedia_url: str
    thread_type: str
    thread_options: str
    seconds_since_epoch: int  # start time
    day_number: int  # represents first, second, third day (etc) of the tournament


class Data(object):
    _singleton = None

    # Generic cache, mapping a string key to any object.
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
        """Returns the postgresSQL connection."""

        connection = psycopg2.connect(
            dbname=os.environ.get("DB_NAME") or rleb_secrets.DB_NAME,
            host=os.environ.get("DB_HOST") or rleb_secrets.DB_HOST,
            user=os.environ.get("DB_USER") or rleb_secrets.DB_USER,
            port=os.environ.get("DB_PORT") or rleb_secrets.DB_PORT,
            password=os.environ.get("DB_PASSWORD") or rleb_secrets.DB_PASSWORD,
        )
        return connection
    
    def yolo_query(self, sql: str) -> str:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(sql)
            response = cursor.fetchall()
            return "\n".join([str(r) for r in response])
    
    def get_db_tables(self) -> int:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("""SELECT count(*) FROM pg_catalog.pg_tables where tableowner='pi'""")
            count: int = cursor.fetchone()[0]
        return count

    def read_all_user_statistics(self) -> list[UserStatistics]:
        if "user_statistics" in Data._cache:
            return Data._cache["user_statistics"]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM user_statistics""")
            statistics = []
            for s in list(cursor.fetchall()):
                statistics.append(UserStatistics(s[0], s[1], s[2]))
            return statistics

    def read_user_statistics(self, discord_username: str) -> Optional[UserStatistics]:
        if f"user_statistics_{discord_username}" in Data._cache:
            return Data._cache[f"user_statistics_{discord_username}"]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT * FROM user_statistics WHERE discord_user_name = %s""",
                (discord_username,),
            )
            s = cursor.fetchone()
            if not s:
                return None
            return UserStatistics(s[0], s[1], s[2])

    def increment_user_statistics_commands_used(self, discord_username: str) -> None:
        Data._empty_cache(f"user_statistics_{discord_username}")
        Data._empty_cache("user_statistics")

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO user_statistics (discord_user_name, commands_used, thanks_given)
               VALUES (%s, 1, 0)
               ON CONFLICT (discord_user_name)
               DO UPDATE SET commands_used = user_statistics.commands_used + 1;""",
                (discord_username,),
            )

    def increment_user_statistics_thanks_given(self, discord_username: str) -> None:
        Data._empty_cache(f"user_statistics_{discord_username}")
        Data._empty_cache("user_statistics")

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO user_statistics (discord_user_name, commands_used, thanks_given)
               VALUES (%s, 1, 1)
               ON CONFLICT (discord_user_name)
               DO UPDATE SET thanks_given = user_statistics.thanks_given + 1;""",
                (discord_username,),
            )

    def read_auto_update_from_id(self, auto_update_id: int) -> Optional[AutoUpdate]:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT * FROM auto_updates WHERE auto_update_id = %s""",
                (auto_update_id,),
            )
            r = cursor.fetchone()
            if not r:
                return None

            auto_update = AutoUpdate(r[0], r[1], r[2], r[3], r[4], r[5], r[6])
            return auto_update

    def read_auto_update_from_reddit_thread(
        self, reddit_thread_url: str
    ) -> Optional[AutoUpdate]:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT * FROM auto_updates WHERE reddit_thread_url = %s""",
                (reddit_thread_url,),
            )
            r = cursor.fetchone()
            if not r:
                return None

            auto_update = AutoUpdate(r[0], r[1], r[2], r[3], r[4], r[5], r[6])
            return auto_update

    def read_all_auto_updates(self) -> list[AutoUpdate]:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM auto_updates""")
            rows = cursor.fetchall()

            auto_updates: list[AutoUpdate] = []
            for r in rows:
                auto_updates.append(
                    AutoUpdate(r[0], r[1], r[2], r[3], r[4], r[5], r[6])
                )
            return auto_updates

    def delete_auto_update(self, auto_update: AutoUpdate) -> None:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """DELETE FROM auto_updates WHERE auto_update_id = %s;""",
                (auto_update.auto_update_id,),
            )

    def write_auto_update(
        self,
        reddit_thread_url: str,
        liquipedia_url: str,
        tourney_system: str,
        thread_options: str,
        day_number: int,
    ) -> AutoUpdate:
        """
        Writes a new autoupdate for an RL tourney.

        Params:
            reddit_thread_url: The thread that is being auto update.
            liquipedia_url: The liquipedia url to read data from.
            tourney_system: The type of thread to create (groups, swiss, bracket, etc)
            thread_options: Additional options on top of the tourney system, delimited by -dashes-.
            day_number: The first, second, third, (etc) day of the tournament.
        """
        seconds_since_epoch = datetime.now().timestamp()
        liquipedia_url = (
            liquipedia_url.split("#")[0] if "#" in liquipedia_url else liquipedia_url
        )
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO auto_updates (reddit_thread_url, liquipedia_url, thread_type, thread_options, seconds_since_epoch, day_number) VALUES (%s, %s, %s, %s, %s, %s) RETURNING auto_update_id;""",
                (
                    reddit_thread_url,
                    liquipedia_url,
                    tourney_system,
                    thread_options,
                    seconds_since_epoch,
                    day_number,
                ),
            )
            auto_update_id = cursor.fetchone()[0]
        return AutoUpdate(
            auto_update_id,
            reddit_thread_url,
            liquipedia_url,
            tourney_system,
            thread_options,
            seconds_since_epoch,
            day_number,
        )

    def write_remindme(
        self, user: str, message: str, elapsed_time: int, channel_id: int
    ) -> Remindme:
        """Adds a remindme notification to the database."""
        target_timestamp = elapsed_time + time.time()
        remindme_id = -1

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO remindme (discord_username, remindme_message, channel_id, trigger_timestamp) VALUES (%s, %s, %s, %s) RETURNING remindme_id;""",
                (user, message, channel_id, target_timestamp),
            )
            remindme_id = cursor.fetchone()[0]
        return Remindme(remindme_id, user, message, target_timestamp, channel_id)

    def delete_remindme(self, remindme_id: int) -> None:
        """Deletes a remindme notification from db. Should be used after a remindme is triggered."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """DELETE FROM remindme WHERE remindme_id = %s;""",
                (remindme_id,),
            )

    def read_remindmes(self) -> list[Remindme]:
        """Returns all remindmes stored in the db."""
        with self.postgres_connection() as db:
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
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO already_warned_scheduled_posts VALUES (%s, %s);""",
                (log_id, seconds_since_epoch),
            )

    def read_already_warned_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        """Returns a list of log ids for already warned scheduled posts."""
        with self.postgres_connection() as db:
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
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO already_confirmed_scheduled_posts VALUES (%s, %s);""",
                (log_id, seconds_since_epoch),
            )

    def read_already_confirmed_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        """Returns a list of log ids for already confirmed scheduled posts."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT post_id FROM already_confirmed_scheduled_posts WHERE seconds_since_epoch > %s;""",
                (min_seconds_since_epoch,),
            )
            post_ids = list(map(lambda x: x[0], cursor.fetchall()))
            return post_ids

    def write_to_logs(self, logs: list[tuple[datetime, str]]) -> None:
        """ "Writes all logs to the database."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.executemany(
                "INSERT INTO logs (log_time, log) VALUES (%s, %s);", [(datetime_log[0], datetime_log[1]) for datetime_log in logs]
            )
            Data._empty_cache("logs")

    def read_logs(self, count: int = 10) -> list[tuple[datetime, str]]:
        """Reads logs to the database."""

        if "logs" in Data._cache:
            return Data._cache["logs"]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT log, log_time FROM logs ORDER BY log_time DESC limit %s;", count)
            all_logs = cursor.fetchall()
            Data._cache["logs"] = all_logs
            return all_logs

    def add_triflair(self, flair_to_add) -> list[str]:
        """Yeets a triflair out of the database."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            # NOTE: For legacy reasons, triflairs are called "dualflairs" in postgres.
            cursor.execute("""INSERT INTO dualflairs VALUES (%s)""", (flair_to_add,))

            Data._empty_cache("triflair")

    def read_triflairs(self) -> list[str]:
        """Reads all the triflair from the database."""

        if "triflair" in Data._cache:
            return Data._cache["triflair"]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM dualflairs;")
            all_dualflairs = cursor.fetchall()
            Data._cache["dualflairs"] = all_dualflairs
            return all_dualflairs

    def yeet_triflair(self, flair_to_remove) -> list[str]:
        """Yeets a triflair out of the database."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                "DELETE FROM dualflairs WHERE dualflair = %s", (flair_to_remove,)
            )

            Data._empty_cache("triflair")
