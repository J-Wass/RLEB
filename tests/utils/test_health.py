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

    async def test_alerts_on_too_many_thread_crashes(self):
        import asyncio

        global_settings.health_enabled = True
        global_settings.thread_health_check_enabled = True
        global_settings.thread_crashes["thread"] = 5

        mock_alert_channel = mock.AsyncMock()
        health_task = asyncio.create_task(health_check.health_check(mock_alert_channel))

        await asyncio.sleep(0.1)
        health_task.cancel()

        try:
            await health_task
        except asyncio.CancelledError:
            pass

        self.assertFalse(global_settings.thread_health_check_enabled)
        self.assertFalse(global_settings.health_enabled)
        mock_alert_channel.send.assert_awaited()

    async def test_alerts_on_too_many_asyncio_crashes(self):
        import asyncio

        global_settings.health_enabled = True
        global_settings.asyncio_health_check_enabled = True
        global_settings.thread_crashes["asyncio"] = 5

        mock_alert_channel = mock.AsyncMock()
        health_task = asyncio.create_task(health_check.health_check(mock_alert_channel))

        await asyncio.sleep(0.1)
        health_task.cancel()

        try:
            await health_task
        except asyncio.CancelledError:
            pass

        self.assertFalse(global_settings.asyncio_health_check_enabled)
        self.assertFalse(global_settings.health_enabled)
        mock_alert_channel.send.assert_awaited()

    async def test_alerts_on_dead_threads(self):
        import asyncio

        global_settings.health_enabled = False  # Will exit after one iteration
        global_settings.thread_health_check_enabled = True
        global_settings.threads_to_check = ["Task alert thread", "Auto update thread"]
        global_settings.threads_heartbeats["Task alert thread"] = datetime.now() - timedelta(seconds=350)
        global_settings.threads_heartbeats["Auto update thread"] = datetime.now()

        mock_alert_channel = mock.AsyncMock()

        # Run health check once
        await health_check.health_check(mock_alert_channel)

        # Should have removed dead thread from check list
        self.assertNotIn("Task alert thread", global_settings.threads_to_check)
        mock_alert_channel.send.assert_awaited()

    async def test_health_check_handles_exception(self):
        import asyncio

        global_settings.health_enabled = False  # Exit after one iteration
        global_settings.asyncio_health_check_enabled = True

        # Create a condition that will raise an exception
        global_settings.asyncio_threads_heartbeats = None  # This will cause an error

        mock_alert_channel = mock.AsyncMock()

        # Should handle the exception gracefully
        await health_check.health_check(mock_alert_channel)

        # Exception should be caught and not crash the function
        # Alert channel send might be called for error message
        # The test passes if no exception is raised


if __name__ == "__main__":
    unittest.main()
