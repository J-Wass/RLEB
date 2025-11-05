import sys
import os

from data_bridge import Remindme

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

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

    async def test_refresh_remindmes_is_noop(self):
        # refresh_remindmes is now a no-op since polling handles reminders
        import global_settings
        global_settings.refresh_remindmes()  # Should not raise an error
