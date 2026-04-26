"""Tests for weekly_status.py"""

import unittest
from datetime import datetime

from tasks import Task, Event
from weekly_status import build_weekly_status


def _ts(date: str, time: str) -> int:
    """Returns UTC timestamp for a date ('YYYY-MM-DD') and time ('HH:MM') pair."""
    dt = datetime.strptime(f"{date} {time} +0000", "%Y-%m-%d %H:%M %z")
    return int(dt.timestamp())


def make_task(name: str, creator: str, schedule_time: str, date: str) -> Task:
    return Task(name, creator, "updater1", "updater2", "Monday", date, schedule_time)


def make_event(name: str, creator: str, timestamp: int, id: str) -> Event:
    return Event(name, creator, "", timestamp, id)


class TestBuildWeeklyStatus(unittest.TestCase):

    def test_scheduled_task_shows_ok_and_poster(self) -> None:
        ts = _ts("2026-04-21", "14:00")
        tasks = [make_task("Weekly Thread", "alice", "Schedule 14:00", "2026-04-21")]
        posts = [make_event("Weekly Thread", "bob", ts, "post-1")]

        result = build_weekly_status(tasks, posts)

        self.assertIn("✅", result)
        self.assertIn("Weekly Thread", result)
        self.assertIn(f"<t:{ts}:F>", result)
        self.assertIn("Prepared By: alice", result)

    def test_missing_task_shows_needs_and_assigned_mod(self) -> None:
        ts = _ts("2026-04-22", "10:00")
        tasks = [make_task("Power Rankings", "carol", "Schedule 10:00", "2026-04-22")]
        posts = []

        result = build_weekly_status(tasks, posts)

        self.assertIn("❌", result)
        self.assertIn("Power Rankings", result)
        self.assertIn(f"<t:{ts}:F>", result)
        self.assertIn("Assigned To: carol", result)

    def test_manual_task_shows_pencil_and_assigned_mod(self) -> None:
        tasks = [make_task("Community Post", "dave", "Post", "2026-04-23")]
        posts = []

        result = build_weekly_status(tasks, posts)

        self.assertIn("📝", result)
        self.assertIn("Community Post", result)
        self.assertIn("manual", result)
        self.assertIn("assigned: dave", result)
        self.assertNotIn("<t:", result)

    def test_unrecognized_reddit_post_appears_at_bottom(self) -> None:
        ts = _ts("2026-04-24", "16:00")
        tasks = []
        posts = [make_event("Mystery Thread", "eve", ts, "mystery-1")]

        result = build_weekly_status(tasks, posts)

        self.assertIn("Unrecognized reddit threads", result)
        self.assertIn("Mystery Thread", result)
        self.assertIn("By: eve", result)
        self.assertIn(f"<t:{ts}:F>", result)

    def test_matched_post_does_not_appear_as_unrecognized(self) -> None:
        ts = _ts("2026-04-21", "14:00")
        tasks = [make_task("Weekly Thread", "alice", "Schedule 14:00", "2026-04-21")]
        posts = [make_event("Weekly Thread", "bob", ts, "post-1")]

        result = build_weekly_status(tasks, posts)

        self.assertNotIn("Unrecognized reddit threads", result)

    def test_mixed_tasks_and_posts(self) -> None:
        ts1 = _ts("2026-04-21", "14:00")
        ts_extra = _ts("2026-04-25", "08:00")

        tasks = [
            make_task("Weekly Thread", "alice", "Schedule 14:00", "2026-04-21"),
            make_task("Power Rankings", "carol", "Schedule 10:00", "2026-04-22"),
            make_task("Community Post", "dave", "Post", "2026-04-23"),
        ]
        posts = [
            make_event("Weekly Thread", "bob", ts1, "post-1"),
            make_event("Mystery Thread", "eve", ts_extra, "mystery-1"),
        ]

        result = build_weekly_status(tasks, posts)

        self.assertIn("✅", result)
        self.assertIn("❌", result)
        self.assertIn("📝", result)
        self.assertIn("Unrecognized reddit threads", result)
        self.assertIn("Mystery Thread", result)

    def test_empty_tasks_and_posts(self) -> None:
        result = build_weekly_status([], [])

        self.assertIn("No tasks found on the weekly sheet", result)
        self.assertNotIn("Unrecognized reddit threads", result)

    def test_malformed_schedule_time_shows_parse_error(self) -> None:
        tasks = [make_task("Broken Task", "frank", "Schedule BADTIME", "2026-04-21")]
        posts = []

        result = build_weekly_status(tasks, posts)

        self.assertIn("❓", result)
        self.assertIn("Broken Task", result)
        self.assertIn("parse error", result)

    def test_multiple_unrecognized_posts(self) -> None:
        ts1 = _ts("2026-04-25", "08:00")
        ts2 = _ts("2026-04-26", "09:00")
        tasks = []
        posts = [
            make_event("Thread A", "mod1", ts1, "a-1"),
            make_event("Thread B", "mod2", ts2, "b-1"),
        ]

        result = build_weekly_status(tasks, posts)

        self.assertIn("Thread A", result)
        self.assertIn("Thread B", result)
        self.assertIn("By: mod1", result)
        self.assertIn("By: mod2", result)


if __name__ == "__main__":
    unittest.main()
