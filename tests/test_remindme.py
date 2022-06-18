import sys
import os

from rleb_data import Remindme

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch
from tests.common.rleb_test_case import RLEBTestCase

from threading import Thread, Timer
from queue import Queue
from datetime import datetime, timedelta
import subprocess


class TestRemindme(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_data after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_data
        global rleb_settings
        import rleb_data
        import rleb_settings

        rleb_settings.user_names_to_ids = {"tester#123": 567}
        rleb_settings.queues["alerts"] = Queue()

    def test_trigger_alert(self):
        reminder = Remindme(1, "tester#123", "message lol", 123, 321)
        rleb_settings.remindme_timers[1] = None
        rleb_settings._trigger_remindme(reminder)

        self.assertEquals(
            rleb_settings.queues["alerts"].get(),
            ("**Reminder for <@567>:** message lol", 321),
        )

    def test_schedule_remindme(self):
        reminder = Remindme(1, "tester#123", "message lol", 123, 321)
        rleb_settings.schedule_remindme(reminder)

        timer = rleb_settings.remindme_timers[1]
        self.assertEqual(type(timer), Timer)
        timer.cancel()
