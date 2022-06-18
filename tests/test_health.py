# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch
from tests.common.rleb_test_case import RLEBTestCase

from threading import Thread
from queue import Queue
from datetime import datetime, timedelta
import subprocess


def instantly_crash():
    pass


class TestHealth(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_health after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_health
        global rleb_settings
        import rleb_health
        import rleb_settings

        # Turn off the health thread so that it only runs once and exits.
        rleb_settings.health_check_startup_latency = 0
        rleb_settings.health_enabled = False
        rleb_settings.asyncio_health_check_enabled = False
        rleb_settings.thread_health_check_enabled = False
        rleb_settings.chrome_health_check_enabled = False
        rleb_settings.BOT_COMMANDS_CHANNEL_ID = 1234321

        self.mock_rleb_log_error = mock.Mock()
        rleb_settings.rleb_log_error = self.mock_rleb_log_error

        rleb_settings.queues["alerts"] = Queue()

    def test_alerts_on_dead_thread(self):
        rleb_settings.thread_health_check_enabled = True
        rleb_settings.thread_crashes["thread"] = 3
        with patch("rleb_health.rleb_log_error") as mock_log_error:
            bad_thread = Thread(target=instantly_crash, name="Bad thread")
            bad_thread.start()
            rleb_health.health_check([bad_thread])
            bad_thread.join()

            mock_log_error.assert_called_with(
                "HEALTH: Thread has died: Bad thread (3 crashes)"
            )

        alert = rleb_settings.queues["alerts"].get()
        self.assertEqual(
            "Thread has died: Bad thread (3 crashes)",
            alert[0],
        )
        self.assertEqual(
            rleb_settings.BOT_COMMANDS_CHANNEL_ID,
            alert[1],
        )

    def test_alerts_on_dead_asyncio_thread(self):
        rleb_settings.asyncio_health_check_enabled = True
        rleb_settings.asyncio_threads = {
            "submissions": datetime.now() - timedelta(seconds=350),
            "alerts": datetime.now(),
            "modmail": datetime.now() - timedelta(seconds=250),
            "trello": datetime.now(),
        }
        rleb_settings.thread_crashes["asyncio"] = 2

        with patch("rleb_health.rleb_log_error") as mock_log_error:
            rleb_health.health_check([])

            mock_log_error.assert_called_with(
                "HEALTH: submissions asyncio thread has stopped responding! (2 crashes)"
            )
        self.assertEqual(
            "submissions asyncio thread has stopped responding! (2 crashes)",
            rleb_settings.queues["alerts"].get()[0],
        )


if __name__ == "__main__":
    unittest.main()
