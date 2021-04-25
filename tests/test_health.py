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

        # import rleb_core after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_core
        global rleb_settings
        import rleb_core
        import rleb_settings

        # Turn off the health thread so that it only runs once and exits.
        rleb_settings.health_check_startup_latency = 0
        rleb_settings.health_enabled = False
        rleb_settings.asyncio_health_check_enabled = False
        rleb_settings.thread_health_check_enabled = False
        rleb_settings.chrome_health_check_enabled = False

        self.mock_rleb_log_error = mock.Mock()
        rleb_settings.rleb_log_error = self.mock_rleb_log_error

        rleb_settings.queues['alerts'] = Queue()

    def test_alerts_on_dead_thread(self):
        rleb_settings.thread_health_check_enabled = True
        rleb_settings.thread_crashes['thread'] = 3
        with patch('rleb_core.rleb_log_error') as mock_log_error:
            bad_thread = Thread(target=instantly_crash, name="Bad thread")
            bad_thread.start()
            rleb_core.health_check([bad_thread])
            bad_thread.join()

            mock_log_error.assert_called_with(
                "HEALTH: Thread has died: Bad thread (3 crashes)")
        self.assertEqual("Thread has died: Bad thread (3 crashes)",
                         rleb_settings.queues['alerts'].get())

    def test_alerts_on_dead_asyncio_thread(self):
        rleb_settings.asyncio_health_check_enabled = True
        rleb_settings.asyncio_threads = {
            'submissions': datetime.now() - timedelta(seconds=350),
            'alerts': datetime.now(),
            'modmail': datetime.now() - timedelta(seconds=250),
            'trello': datetime.now()
        }
        rleb_settings.thread_crashes['asyncio'] = 2

        with patch('rleb_core.rleb_log_error') as mock_log_error:
            rleb_core.health_check([])

            mock_log_error.assert_called_with(
                "HEALTH: submissions asyncio thread has stopped responding! (2 crashes)"
            )
        self.assertEqual(
            "submissions asyncio thread has stopped responding! (2 crashes)",
            rleb_settings.queues['alerts'].get())

    def test_alerts_on_chrome_mismatch(self):
        def mock_version(args=[]):
            """ Mock method for subprocess.checkout_output."""
            if len(args) == 0:
                return ""
            path = args[0]
            arg = args[1]
            if path == rleb_settings.get_chrome_settings(
                    rleb_settings.RUNNING_ENVIRONMENT)['path']:
                return b'Google Chrome 36.0.1985.125'
            elif path == rleb_settings.get_chrome_settings(
                    rleb_settings.RUNNING_ENVIRONMENT)['driver']:
                return b'Chromedriver 37.2.43'

        mock_subprocess = patch.object(subprocess,
                                       "check_output",
                                       new=mock_version).start()
        self.addCleanup(mock_subprocess)

        rleb_settings.chrome_health_check_enabled = True
        rleb_settings.RUNNING_ENVIRONMENT = "linux"

        with patch('rleb_core.rleb_log_error') as mock_log_error:
            rleb_core.health_check([])

            mock_log_error.assert_called_with(
                "HEALTH: The chromedriver version (37) does not match chrome version (36)!"
            )
        self.assertEqual(
            "The chromedriver version (37) does not match chrome version (36)!",
            rleb_settings.queues['alerts'].get())


if __name__ == '__main__':
    unittest.main()
