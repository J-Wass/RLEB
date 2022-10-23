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


def instantly_crash():
    pass


class TestHealth(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import health_check after setUp is done so that rleb_settings loads with mocks/patches
        global health_check
        global global_settings
        import health_check
        import global_settings

        # Turn off the health thread so that it only runs once and exits.
        global_settings.health_check_startup_latency = 0
        global_settings.health_enabled = False
        global_settings.asyncio_health_check_enabled = False
        global_settings.thread_health_check_enabled = False
        global_settings.chrome_health_check_enabled = False
        global_settings.BOT_COMMANDS_CHANNEL_ID = 1234321

        self.mock_rleb_log_error = mock.Mock()
        global_settings.rleb_log_error = self.mock_rleb_log_error

        global_settings.queues["alerts"] = Queue()

    def test_alerts_on_dead_thread(self):
        global_settings.thread_health_check_enabled = True
        global_settings.thread_crashes["thread"] = 3
        with patch("health_check.rleb_log_error") as mock_log_error:
            bad_thread = Thread(target=instantly_crash, name="Bad thread")
            bad_thread.start()
            health_check.health_check([bad_thread])
            bad_thread.join()

            mock_log_error.assert_called_with(
                "HEALTH: Thread has died: Bad thread (3 crashes)"
            )

        alert = global_settings.queues["alerts"].get()
        self.assertEqual(
            "Thread has died: Bad thread (3 crashes)",
            alert[0],
        )
        self.assertEqual(
            global_settings.BOT_COMMANDS_CHANNEL_ID,
            alert[1],
        )

    def test_alerts_on_dead_asyncio_thread(self):
        global_settings.asyncio_health_check_enabled = True
        global_settings.asyncio_threads = {
            "submissions": datetime.now() - timedelta(seconds=350),
            "alerts": datetime.now(),
            "modmail": datetime.now() - timedelta(seconds=250),
            "trello": datetime.now(),
        }
        global_settings.thread_crashes["asyncio"] = 2

        with patch("health_check.rleb_log_error") as mock_log_error:
            health_check.health_check([])

            mock_log_error.assert_called_with(
                "HEALTH: submissions asyncio thread has stopped responding! (2 crashes)"
            )
        self.assertEqual(
            "submissions asyncio thread has stopped responding! (2 crashes)",
            global_settings.queues["alerts"].get()[0],
        )


if __name__ == "__main__":
    unittest.main()
