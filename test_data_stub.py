"""
Enhanced test data stub with realistic sample data for testing without a database.

This module provides a DataStubWithSampleData class that extends the basic DataStub
with in-memory storage and pre-populated sample data. Useful for development,
testing, and demos.

Usage:
    Set DATA_MODE environment variable to "test" to use this stub with sample data.
    Set DATA_MODE to "stubbed" for empty stub.
    Set DATA_MODE to "real" for actual database.
"""

from datetime import datetime
from typing import Optional
import time
from data_bridge import DataStub, UserStatistics, Remindme, AutoUpdate


class DataStubWithSampleData(DataStub):
    """
    Test data stub with realistic sample data stored in memory.

    This class simulates a database by storing all data in memory dictionaries.
    It comes pre-populated with sample data and supports read/write operations.
    """

    _singleton = None

    # In-memory storage
    _user_statistics: dict[str, UserStatistics] = {}
    _aliases: dict[str, str] = {}
    _auto_updates: dict[int, AutoUpdate] = {}
    _remindmes: dict[int, Remindme] = {}
    _warned_posts: set[int] = set()
    _confirmed_posts: set[int] = set()
    _logs: list[tuple[datetime, str]] = []
    _triflairs: set[str] = set()

    # Auto-increment IDs
    _next_auto_update_id: int = 1
    _next_remindme_id: int = 1

    @classmethod
    def singleton(cls) -> "DataStubWithSampleData":
        if cls._singleton is None:
            cls._singleton = cls.__new__(cls)
            cls._singleton._initialize_sample_data()
        return cls._singleton

    def _initialize_sample_data(self) -> None:
        """Populate the stub with realistic sample data."""

        # Sample user statistics
        self._user_statistics = {
            "TestUser#1234": UserStatistics("TestUser#1234", 42, 15),
            "AnotherUser#5678": UserStatistics("AnotherUser#5678", 103, 27),
            "ModUser#0001": UserStatistics("ModUser#0001", 256, 89),
            "NewUser#9999": UserStatistics("NewUser#9999", 1, 0),
        }

        # Sample team aliases
        self._aliases = {
            "G2 Esports": "G2",
            "Team Vitality": "VIT",
            "NRG Esports": "NRG",
            "FaZe Clan": "FaZe",
            "Team BDS": "BDS",
            "Spacestation Gaming": "SSG",
            "FURIA Esports": "FURIA",
            "Oxygen Esports": "OXG",
        }

        # Sample auto-updates
        current_time = int(time.time())
        self._auto_updates = {
            1: AutoUpdate(
                1,
                "https://reddit.com/r/RLCSnewsTest/comments/1p7qg37/auto_update_test_1/",
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2025/Birmingham_Major",
                "swiss",
                "header=true",
                current_time - 3600,
                1,
            ),
            2: AutoUpdate(
                2,
                "https://old.reddit.com/r/RLCSnewsTest/comments/1p7qgou/auto_update_test_2/",
                "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2025/Raleigh_Major",
                "bracket",
                "",
                current_time - 7200,
                2,
            ),
        }
        self._next_auto_update_id = 3

        # Sample remindmes (none active initially, but structure is ready)
        self._remindmes = {}
        self._next_remindme_id = 1

        # Sample triflairs (Reddit flairs)
        self._triflairs = {
            ":G2:",
            ":NRG:",
            ":VIT:",
            ":BDS:",
            ":SSG:",
            ":FaZe:",
            ":FURIA:",
            ":OXG:",
            ":C9:",
            ":Verified:",
        }

        # Sample logs
        self._logs = [
            (datetime.now(), "INFO: System initialized with sample data"),
            (datetime.now(), "INFO: Test user connected"),
            (datetime.now(), "WARNING: Sample warning message"),
            (datetime.now(), "INFO: Sample bracket lookup completed"),
            (datetime.now(), "ERROR: Sample error message for testing"),
        ]

        # Sample warned/confirmed posts
        self._warned_posts = {12345, 67890}
        self._confirmed_posts = {11111, 22222}

    # === User Statistics Methods ===

    def read_all_user_statistics(self) -> list[UserStatistics]:
        return list(self._user_statistics.values())

    def read_user_statistics(self, discord_username: str) -> Optional[UserStatistics]:
        return self._user_statistics.get(discord_username)

    def increment_user_statistics_commands_used(self, discord_username: str) -> None:
        if discord_username in self._user_statistics:
            self._user_statistics[discord_username].commands_used += 1
        else:
            self._user_statistics[discord_username] = UserStatistics(
                discord_username, 1, 0
            )

    def increment_user_statistics_thanks_given(self, discord_username: str) -> None:
        if discord_username in self._user_statistics:
            self._user_statistics[discord_username].thanks_given += 1
        else:
            self._user_statistics[discord_username] = UserStatistics(
                discord_username, 0, 1
            )

    # === Alias Methods ===

    def add_alias(self, long_name: str, short_name: str) -> None:
        self._aliases[long_name] = short_name

    def remove_alias(self, long_name: str) -> None:
        if long_name in self._aliases:
            del self._aliases[long_name]

    def read_all_aliases(self) -> dict[str, str]:
        return self._aliases.copy()

    # === Auto Update Methods ===

    def read_auto_update_from_id(self, auto_update_id: int) -> Optional[AutoUpdate]:
        return self._auto_updates.get(auto_update_id)

    def read_auto_update_from_reddit_thread(
        self, reddit_thread_url: str
    ) -> Optional[AutoUpdate]:
        for auto_update in self._auto_updates.values():
            if auto_update.reddit_url == reddit_thread_url:
                return auto_update
        return None

    def read_all_auto_updates(self) -> list[AutoUpdate]:
        return list(self._auto_updates.values())

    def write_auto_update(
        self,
        reddit_thread_url: str,
        liquipedia_url: str,
        tourney_system: str,
        thread_options: str,
        day_number: int,
    ) -> AutoUpdate:
        auto_update = AutoUpdate(
            self._next_auto_update_id,
            reddit_thread_url,
            liquipedia_url,
            tourney_system,
            thread_options,
            int(time.time()),
            day_number,
        )
        self._auto_updates[self._next_auto_update_id] = auto_update
        self._next_auto_update_id += 1
        return auto_update

    def delete_auto_update(self, auto_update: AutoUpdate) -> None:
        if auto_update.auto_update_id in self._auto_updates:
            del self._auto_updates[auto_update.auto_update_id]

    # === Remindme Methods ===

    def write_remindme(
        self, user: str, message: str, elapsed_time: int, channel_id: str
    ) -> Remindme:
        remindme = Remindme(
            self._next_remindme_id,
            user,
            message,
            int(time.time()) + elapsed_time,
            channel_id,
        )
        self._remindmes[self._next_remindme_id] = remindme
        self._next_remindme_id += 1
        return remindme

    def delete_remindme(self, remindme_id: int) -> None:
        if remindme_id in self._remindmes:
            del self._remindmes[remindme_id]

    def read_remindmes(self) -> list[Remindme]:
        return list(self._remindmes.values())

    # === Scheduled Post Methods ===

    def write_already_warned_scheduled_post(
        self, log_id: int, seconds_since_epoch: int
    ) -> None:
        self._warned_posts.add(log_id)

    def read_already_warned_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        # In a real DB, would filter by timestamp
        return list(self._warned_posts)

    def write_already_warned_confirmed_post(
        self, log_id: int, seconds_since_epoch: int
    ) -> None:
        self._confirmed_posts.add(log_id)

    def read_already_confirmed_scheduled_posts(
        self, min_seconds_since_epoch: int
    ) -> list[int]:
        # In a real DB, would filter by timestamp
        return list(self._confirmed_posts)

    # === Logging Methods ===

    def write_to_logs(self, logs: list[tuple[datetime, str]]) -> None:
        self._logs.extend(logs)
        # Keep only last 1000 logs to avoid memory issues
        if len(self._logs) > 1000:
            self._logs = self._logs[-1000:]

    def read_logs(self, count: int = 10) -> list[tuple[datetime, str]]:
        return self._logs[-count:] if self._logs else []

    # === Triflair Methods ===

    def add_triflair(self, flair_to_add: str) -> None:
        self._triflairs.add(flair_to_add)

    def read_triflairs(self) -> list[str]:
        # Return as list of tuples to match DB format (but type is list[str])
        result: list[str] = [(flair,) for flair in sorted(self._triflairs)]  # type: ignore[assignment,misc]
        return result

    def yeet_triflair(self, flair_to_remove: str) -> None:
        self._triflairs.discard(flair_to_remove)

    # === Utility Methods ===

    def get_db_tables(self) -> int:
        """Return count of 'tables' (data structures) in the stub."""
        return 8  # user_stats, aliases, auto_updates, remindmes, warned, confirmed, logs, triflairs

    def yolo_query(self, sql: str) -> str:
        """Return sample data for debugging."""
        return f"STUB MODE: Would execute query: {sql[:100]}..."

    # === Additional Helper Methods ===

    def reset_to_sample_data(self) -> None:
        """Reset all data to initial sample state. Useful for testing."""
        self._initialize_sample_data()

    def clear_all_data(self) -> None:
        """Clear all data (useful for test isolation)."""
        self._user_statistics.clear()
        self._aliases.clear()
        self._auto_updates.clear()
        self._remindmes.clear()
        self._warned_posts.clear()
        self._confirmed_posts.clear()
        self._logs.clear()
        self._triflairs.clear()
        self._next_auto_update_id = 1
        self._next_remindme_id = 1

    def get_data_summary(self) -> dict:
        """Return a summary of all stored data (useful for debugging)."""
        return {
            "user_statistics_count": len(self._user_statistics),
            "aliases_count": len(self._aliases),
            "auto_updates_count": len(self._auto_updates),
            "remindmes_count": len(self._remindmes),
            "warned_posts_count": len(self._warned_posts),
            "confirmed_posts_count": len(self._confirmed_posts),
            "logs_count": len(self._logs),
            "triflairs_count": len(self._triflairs),
        }
