from datetime import datetime
import time
from typing import Optional, Any
import psycopg2
import os
import configparser
from dataclasses import dataclass

config = configparser.ConfigParser(interpolation=None)
if os.path.exists("rleb_secrets.ini"):
    config.read("rleb_secrets.ini")
else:
    config.read("rleb_secrets_sample.ini")


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
    channel_id: int


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


class DataStub(object):
    _singleton: Optional["DataStub"] = None
    _cache: dict[str, Any] = {}

    def __init__(self) -> None:
        raise RuntimeError("Call singleton() instead")

    @classmethod
    def singleton(cls) -> "DataStub":
        if cls._singleton is None:
            cls._singleton = cls.__new__(cls)
        return cls._singleton

    def yolo_query(self, sql: str) -> str:
        return ""

    def get_db_tables(self) -> int:
        return 0

    def read_all_user_statistics(self) -> list[UserStatistics]:
        return []

    def read_user_statistics(self, discord_username: str) -> Optional[UserStatistics]:
        return None

    def increment_user_statistics_commands_used(self, discord_username: str) -> None:
        pass

    def increment_user_statistics_thanks_given(self, discord_username: str) -> None:
        pass

    def add_alias(self, long_name: str, short_name: str) -> None:
        pass

    def remove_alias(self, long_name: str) -> None:
        pass

    def read_all_aliases(self) -> dict[str, str]:
        return {}

    def read_auto_update_from_id(self, auto_update_id: int) -> Optional[AutoUpdate]:
        return None

    def read_auto_update_from_reddit_thread(
        self, reddit_thread_url: str
    ) -> Optional[AutoUpdate]:
        return None

    def read_all_auto_updates(self) -> list[AutoUpdate]:
        return []

    def delete_auto_update(self, auto_update: AutoUpdate) -> None:
        pass

    def write_auto_update(
        self,
        reddit_thread_url: str,
        liquipedia_url: str,
        tourney_system: str,
        thread_options: str,
        day_number: int,
    ) -> AutoUpdate:
        return AutoUpdate(
            -1,
            reddit_thread_url,
            liquipedia_url,
            tourney_system,
            thread_options,
            int(time.time()),
            day_number,
        )

    def write_remindme(
        self, user: str, message: str, elapsed_time: int, channel_id: int
    ) -> Remindme:
        return Remindme(-1, user, message, int(time.time()) + elapsed_time, channel_id)

    def delete_remindme(self, remindme_id: int) -> None:
        pass

    def read_remindmes(self) -> list[Remindme]:
        return []

    def write_already_warned_scheduled_post(
        self, log_id: int, seconds_since_epoch: int
    ) -> None:
        pass

    def read_already_warned_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        return []

    def write_already_warned_confirmed_post(
        self, log_id: int, seconds_since_epoch: int
    ) -> None:
        pass

    def read_already_confirmed_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        return []

    def write_to_logs(self, logs: list[tuple[datetime, str]]) -> None:
        pass

    def read_logs(self, count: int = 10) -> list[tuple[datetime, str]]:
        return []

    def add_triflair(self, flair_to_add: str) -> None:
        pass

    def read_triflairs(self) -> list[str]:
        return []

    def yeet_triflair(self, flair_to_remove: str) -> None:
        pass


class Data(DataStub):
    """Bridge between RLEB and postgres DB"""

    _singleton: Optional["Data"] = None

    # Generic cache, mapping a string key to any object.
    _cache: dict[str, Any] = {}

    def __init__(self) -> None:
        raise RuntimeError("Call singleton() instead")

    @staticmethod
    def _empty_cache(cache_key: str) -> None:
        """Safely removes cache_key and its memory from the internal data cache."""
        if cache_key in Data._cache:
            del Data._cache[cache_key]

    @classmethod
    def singleton(cls) -> "DataStub":
        if cls._singleton is None:
            data_mode = os.environ.get("DATA_MODE") or config["General"].get(
                "DATA_MODE", "stubbed"
            )

            if data_mode == "real":
                # Use real PostgreSQL database
                cls._singleton = cls.__new__(cls)  # type: ignore[assignment]
            elif data_mode == "test":
                # Use test stub with sample data
                from test_data_stub import DataStubWithSampleData

                cls._singleton = DataStubWithSampleData.singleton()  # type: ignore[assignment]
            else:
                # Use empty stub (default for "stubbed" or any other value)
                cls._singleton = cls.__new__(DataStub)  # type: ignore[assignment]
        return cls._singleton  # type: ignore[return-value]

    def postgres_connection(self) -> Any:
        """Returns the postgresSQL connection."""
        connection = psycopg2.connect(
            dbname=os.environ.get("DB_NAME") or config["PostgreSQL"]["DB_NAME"],
            host=os.environ.get("DB_HOST") or config["PostgreSQL"]["DB_HOST"],
            user=os.environ.get("DB_USER") or config["PostgreSQL"]["DB_USER"],
            port=os.environ.get("DB_PORT") or config["PostgreSQL"]["DB_PORT"],
            password=os.environ.get("DB_PASSWORD")
            or config["PostgreSQL"]["DB_PASSWORD"],
        )
        return connection

    def yolo_query(self, sql: str) -> str:
        # Security: Denylist dangerous SQL commands (backup to read-only transaction)
        blocked_commands = [
            # Write operations
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "CREATE",
            "ALTER",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
            "EXECUTE",
            "CALL",
            "COPY",
            # Esoteric and potentially dangerous commands
            "DO",
            "LOAD",
            "VACUUM",
            "LOCK",
            "SET",
            "PREPARE",
            "REFRESH",
            "REINDEX",
            "CLUSTER",
            "ANALYZE",
            "COMMENT",
            "CHECKPOINT",
            "DISCARD",
            "IMPORT",
            "LISTEN",
            "UNLISTEN",
            "NOTIFY",
        ]
        sql_upper = sql.upper()
        for cmd in blocked_commands:
            if cmd in sql_upper:
                raise ValueError(
                    f"SQL command '{cmd}' is not allowed. Only SELECT queries are permitted."
                )

        try:
            with self.postgres_connection() as db:
                cursor = db.cursor()
                cursor.execute("SET TRANSACTION READ ONLY;")
                cursor.execute(sql)
                response = cursor.fetchall()
                return "\n".join([str(r) for r in response])
        except psycopg2.Error as e:
            # Provide detailed database error information
            error_msg = f"Database error: {e.pgerror if e.pgerror else str(e)}"
            if e.pgcode:
                error_msg += f"\nError code: {e.pgcode}"
            if hasattr(e, "diag") and e.diag:
                if e.diag.message_primary:
                    error_msg += f"\nDetails: {e.diag.message_primary}"
                if e.diag.message_detail:
                    error_msg += f"\n{e.diag.message_detail}"
            raise ValueError(error_msg) from e
        except Exception as e:
            # Catch any other unexpected errors
            raise ValueError(
                f"Unexpected error executing query: {type(e).__name__}: {str(e)}"
            ) from e

    def get_db_tables(self) -> int:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT count(*) FROM pg_catalog.pg_tables where tableowner='pi' and schemaname='public';"""
            )
            count: int = cursor.fetchone()[0]
        return count

    def read_all_user_statistics(self) -> list[UserStatistics]:
        if "user_statistics" in Data._cache:
            return Data._cache["user_statistics"]  # type: ignore[no-any-return]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM public.user_statistics""")
            statistics = []
            for s in list(cursor.fetchall()):
                statistics.append(UserStatistics(s[0], s[1], s[2]))
            return statistics

    def read_user_statistics(self, discord_username: str) -> Optional[UserStatistics]:
        if f"user_statistics_{discord_username}" in Data._cache:
            return Data._cache[f"user_statistics_{discord_username}"]  # type: ignore[no-any-return]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT * FROM public.user_statistics WHERE discord_user_name = %s""",
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
                """INSERT INTO public.user_statistics (discord_user_name, commands_used, thanks_given)
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
                """INSERT INTO public.user_statistics (discord_user_name, commands_used, thanks_given)
               VALUES (%s, 1, 1)
               ON CONFLICT (discord_user_name)
               DO UPDATE SET thanks_given = user_statistics.thanks_given + 1;""",
                (discord_username,),
            )

    def add_alias(self, long_name: str, short_name: str) -> None:
        Data._empty_cache("aliases")
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO public.aliases (long_name, short_name) VALUES (%s, %s);""",
                (long_name, short_name),
            )

    def remove_alias(self, long_name: str) -> None:
        Data._empty_cache("aliases")
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """DELETE FROM public.aliases WHERE long_name = %s;""",
                (long_name),
            )

    def read_all_aliases(self) -> dict[str, str]:
        """Returns a mapping of long_name to short_name for each alias"""

        if "aliases" in Data._cache:
            return Data._cache["aliases"]  # type: ignore[no-any-return]
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM public.aliases;")
            all_aliases = cursor.fetchall()
            return_dict = {long: short for long, short in all_aliases}
            Data._cache["aliases"] = return_dict
            return return_dict

    def read_auto_update_from_id(self, auto_update_id: int) -> Optional[AutoUpdate]:
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT * FROM public.auto_updates WHERE auto_update_id = %s""",
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
                """SELECT * FROM public.auto_updates WHERE reddit_thread_url = %s""",
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
            cursor.execute("""SELECT * FROM public.auto_updates""")
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
                """DELETE FROM public.auto_updates WHERE auto_update_id = %s;""",
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
        seconds_since_epoch = int(datetime.now().timestamp())
        liquipedia_url = (
            liquipedia_url.split("#")[0] if "#" in liquipedia_url else liquipedia_url
        )
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO public.auto_updates (reddit_thread_url, liquipedia_url, thread_type, thread_options, seconds_since_epoch, day_number) VALUES (%s, %s, %s, %s, %s, %s) RETURNING auto_update_id;""",
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
        target_timestamp = int(elapsed_time + time.time())
        remindme_id = -1

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """INSERT INTO public.remindme (discord_username, remindme_message, channel_id, trigger_timestamp) VALUES (%s, %s, %s, %s) RETURNING remindme_id;""",
                (user, message, channel_id, target_timestamp),
            )
            remindme_id = cursor.fetchone()[0]
        return Remindme(remindme_id, user, message, target_timestamp, channel_id)

    def delete_remindme(self, remindme_id: int) -> None:
        """Deletes a remindme notification from db. Should be used after a remindme is triggered."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """DELETE FROM public.remindme WHERE remindme_id = %s;""",
                (remindme_id,),
            )

    def read_remindmes(self) -> list[Remindme]:
        """Returns all remindmes stored in the db."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("""SELECT * FROM public.remindme""")
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
                """INSERT INTO public.already_warned_scheduled_posts VALUES (%s, %s);""",
                (log_id, seconds_since_epoch),
            )

    def read_already_warned_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        """Returns a list of log ids for already warned scheduled posts."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT id FROM public.already_warned_scheduled_posts WHERE seconds_since_epoch > %s;""",
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
                """INSERT INTO public.already_confirmed_scheduled_posts VALUES (%s, %s);""",
                (log_id, seconds_since_epoch),
            )

    def read_already_confirmed_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        """Returns a list of log ids for already confirmed scheduled posts."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                """SELECT post_id FROM public.already_confirmed_scheduled_posts WHERE seconds_since_epoch > %s;""",
                (min_seconds_since_epoch,),
            )
            post_ids = list(map(lambda x: x[0], cursor.fetchall()))
            return post_ids

    def write_to_logs(self, logs: list[tuple[datetime, str]]) -> None:
        """ "Writes all logs to the database."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.executemany(
                "INSERT INTO public.logs (log_time, log) VALUES (%s, %s);",
                [(datetime_log[0], datetime_log[1]) for datetime_log in logs],
            )

    def read_logs(self, count: int = 10) -> list[tuple[datetime, str]]:
        """Reads logs to the database."""

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                "SELECT log, log_time FROM public.logs ORDER BY log_time DESC limit %s;",
                (count,),
            )
            all_logs = cursor.fetchall()
            return all_logs  # type: ignore[no-any-return]

    def add_triflair(self, flair_to_add: str) -> None:
        """Adds a triflair to the database."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            # NOTE: For legacy reasons, triflairs are called "dualflairs" in postgres.
            cursor.execute(
                """INSERT INTO public.dualflairs VALUES (%s)""", (flair_to_add,)
            )

            Data._empty_cache("triflair")

    def read_triflairs(self) -> list[str]:
        """Reads all the triflair from the database."""

        if "triflair" in Data._cache:
            return Data._cache["triflair"]  # type: ignore[no-any-return]

        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM public.dualflairs;")
            all_dualflairs = cursor.fetchall()
            Data._cache["dualflairs"] = all_dualflairs
            return all_dualflairs  # type: ignore[no-any-return]

    def yeet_triflair(self, flair_to_remove: str) -> None:
        """Yeets a triflair out of the database."""
        with self.postgres_connection() as db:
            cursor = db.cursor()
            cursor.execute(
                "DELETE FROM public.dualflairs WHERE dualflair = %s", (flair_to_remove,)
            )

            Data._empty_cache("triflair")
