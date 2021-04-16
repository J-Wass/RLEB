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


def instantly_crash():
    pass

class TestHealth(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_core after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_core
        import rleb_core
        import rleb_settings

        # Turn off the health thread so that it only runs once and exits.
        rleb_settings.health_enabled = False
        rleb_settings.health_check_startup_latency = 0

        self.mock_rleb_log_error = mock.Mock()
        rleb_settings.rleb_log_error = self.mock_rleb_log_error

        rleb_settings.queues['alerts'] = Queue()

    def test_alerts_on_dead_thread(self):
        with patch('rleb_core.rleb_log_error') as mock_log_error:
            bad_thread = Thread(target=instantly_crash, name="Bad thread")
            bad_thread.start()
            rleb_core.health_check([bad_thread])
            bad_thread.join()

            mock_log_error.assert_called_with("HEALTH: Thread has died: Bad thread (0 crashes)")

if __name__ == '__main__':
    unittest.main()
