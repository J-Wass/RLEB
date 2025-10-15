import sys
import os

from data_bridge import Remindme

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

from tests.common.rleb_test_case import RLEBTestCase

from threading import Timer
from queue import Queue


class TestRemindme(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_data after setUp is done so that rleb_settings loads with mocks/patches
        global data_bridge
        global global_settings
        import data_bridge
        import global_settings

        global_settings.user_names_to_ids = {"tester#123": 567}
        global_settings.queues["alerts"] = Queue()

    def test_trigger_alert(self):
        reminder = Remindme(1, "tester#123", "message lol", 123, 321)
        global_settings.remindme_timers[1] = None
        global_settings._trigger_remindme(reminder)

        self.assertEqual(
            global_settings.queues["alerts"].get(),
            ("**Reminder for <@567>:** message lol", 321),
        )

    def test_schedule_remindme(self):
        import asyncio

        reminder = Remindme(1, "tester#123", "message lol", 123, 321)
        global_settings.schedule_remindme(reminder)

        # With asyncio, the timer is now a Task (if event loop exists) or None (if no loop)
        timer = global_settings.remindme_timers.get(1)
        if timer is not None:
            self.assertEqual(type(timer), asyncio.Task)
            timer.cancel()
