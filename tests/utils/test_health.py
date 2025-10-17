# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch
from tests.common.rleb_async_test_case import RLEBAsyncTestCase

from threading import Thread
from queue import Queue
from datetime import datetime, timedelta


def instantly_crash():
    pass


class TestHealth(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

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

        global_settings.threads_heartbeats["Task alert thread"] = datetime.now()
        global_settings.threads_heartbeats["Auto update thread"] = datetime.now()

    async def test_alerts_on_dead_asyncio_thread(self):
        import asyncio

        global_settings.asyncio_health_check_enabled = True
        global_settings.asyncio_threads_heartbeats = {
            "submissions": datetime.now() - timedelta(seconds=350),
            "alerts": datetime.now(),
            "modmail": datetime.now() - timedelta(seconds=250),
        }
        global_settings.thread_crashes["asyncio"] = 2

        # Create a mock alert channel
        mock_alert_channel = mock.AsyncMock()

        # Create a task that will run health_check
        health_task = asyncio.create_task(health_check.health_check(mock_alert_channel))

        # Let it run once, then cancel it
        await asyncio.sleep(0.1)
        health_task.cancel()

        try:
            await health_task
        except asyncio.CancelledError:
            pass

        # Verify the alert was sent to the channel
        mock_alert_channel.send.assert_awaited_with(
            "submissions asyncio thread has stopped responding! (2 crashes)"
        )


if __name__ == "__main__":
    unittest.main()
