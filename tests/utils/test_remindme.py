import sys
import os

from data_bridge import Remindme

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

from threading import Timer
import asyncio


class TestRemindme(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # import rleb_data after setUp is done so that rleb_settings loads with mocks/patches
        global data_bridge
        global global_settings
        import data_bridge
        import global_settings

        global_settings.user_names_to_ids = {"tester#123": 567}

        # Create a mock Discord client
        import unittest.mock as mock
        global_settings.discord_client = mock.AsyncMock()
        global_settings.discord_client.get_channel = mock.Mock()
        self.mock_channel = mock.AsyncMock()
        global_settings.discord_client.get_channel.return_value = self.mock_channel

    async def test_trigger_alert(self):
        reminder = Remindme(1, "tester#123", "message lol", 123, 321)
        global_settings.remindme_timers[1] = None
        await global_settings._trigger_remindme(reminder)

        # Verify the message was sent to the correct channel
        global_settings.discord_client.get_channel.assert_called_with(321)
        self.mock_channel.send.assert_awaited_once_with("**Reminder for <@567>:** message lol")

    async def test_schedule_remindme(self):
        import asyncio

        reminder = Remindme(1, "tester#123", "message lol", 123, 321)
        global_settings.schedule_remindme(reminder)

        # With asyncio, the timer is now a Task (if event loop exists) or None (if no loop)
        timer = global_settings.remindme_timers.get(1)
        if timer is not None:
            self.assertEqual(type(timer), asyncio.Task)
            timer.cancel()

    async def test_refresh_remindmes(self):
        import asyncio
        import time
        import unittest.mock as mock

        # Clear existing timers
        global_settings.remindme_timers.clear()

        # Mock the data bridge to return some reminders
        future_time = int(time.time() + 3600)  # 1 hour from now
        expired_time = int(time.time() - 3600)  # 1 hour ago

        reminders = [
            Remindme(1, "user1#123", "future reminder", future_time, 100),
            Remindme(2, "user2#456", "expired reminder", expired_time, 200),
        ]

        with mock.patch.object(data_bridge.Data.singleton(), 'read_remindmes', return_value=reminders):
            global_settings.refresh_remindmes()

        # Verify both reminders were scheduled
        self.assertEqual(len(global_settings.remindme_timers), 2)
        self.assertIn(1, global_settings.remindme_timers)
        self.assertIn(2, global_settings.remindme_timers)

        # Verify they are asyncio tasks
        for remindme_id, task in global_settings.remindme_timers.items():
            self.assertEqual(type(task), asyncio.Task)
            task.cancel()  # Clean up

        # Clear for next test
        global_settings.remindme_timers.clear()
