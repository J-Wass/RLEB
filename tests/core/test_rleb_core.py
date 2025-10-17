"""Tests for rleb_core.py"""

import unittest
from unittest.mock import patch, MagicMock
import asyncio

import rleb_core
import global_settings


class TestRLEBCore(unittest.TestCase):
    """Test cases for the RLEB core startup functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch asyncio
        self.asyncio_patch = patch('rleb_core.asyncio').start()

        # Patch discord_bridge
        self.discord_bridge_patch = patch('rleb_core.discord_bridge').start()

        # Patch global_settings functions
        # Patch where it's imported, not where it's defined
        self.log_info_patch = patch('rleb_core.rleb_log_info').start()
        self.refresh_remindmes_patch = patch.object(
            global_settings, 'refresh_remindmes'
        ).start()
        self.refresh_autoupdates_patch = patch.object(
            global_settings, 'refresh_autoupdates'
        ).start()

        # Mock global settings attributes
        self.running_env_patch = patch.object(
            global_settings, 'RUNNING_ENVIRONMENT', 'test_environment'
        ).start()
        self.running_mode_patch = patch.object(
            global_settings, 'RUNNING_MODE', 'test_mode'
        ).start()

        self.addCleanup(patch.stopall)

    def test_start_sets_event_loop_policy(self):
        """Test that start() sets the asyncio event loop policy."""
        rleb_core.start()

        # Verify asyncio event loop policy was set
        self.asyncio_patch.set_event_loop_policy.assert_called_once()
        self.assertEqual(
            self.asyncio_patch.set_event_loop_policy.call_args[0][0].__class__.__name__,
            'MagicMock'  # The mock of DefaultEventLoopPolicy
        )

    def test_start_logs_startup_message(self):
        """Test that start() logs the startup message with environment info."""
        rleb_core.start()

        # Verify startup log
        self.log_info_patch.assert_any_call(
            "Starting RLEB. Running under test_environment in test_mode mode."
        )

    def test_start_refreshes_remindmes(self):
        """Test that start() refreshes remindmes from database."""
        rleb_core.start()

        # Verify remindmes are refreshed
        self.refresh_remindmes_patch.assert_called_once()

    def test_start_refreshes_autoupdates(self):
        """Test that start() refreshes autoupdates from database."""
        rleb_core.start()

        # Verify autoupdates are refreshed
        self.refresh_autoupdates_patch.assert_called_once()

    def test_start_logs_discord_bot_startup(self):
        """Test that start() logs discord bot startup message."""
        rleb_core.start()

        # Verify discord startup log
        self.log_info_patch.assert_any_call(
            "Starting discord bot (all monitoring will run in asyncio tasks)."
        )

    def test_start_calls_discord_bridge_start(self):
        """Test that start() calls discord_bridge.start()."""
        rleb_core.start()

        # Verify discord bridge is started
        self.discord_bridge_patch.start.assert_called_once()

    def test_start_execution_order(self):
        """Test that start() executes steps in the correct order."""
        call_order = []

        def track_asyncio_policy(*args, **kwargs):
            call_order.append('asyncio_policy')

        def track_log(*args, **kwargs):
            if 'Starting RLEB' in args[0]:
                call_order.append('log_startup')
            elif 'Starting discord bot' in args[0]:
                call_order.append('log_discord')

        def track_refresh_remindmes():
            call_order.append('refresh_remindmes')

        def track_refresh_autoupdates():
            call_order.append('refresh_autoupdates')

        def track_discord_start():
            call_order.append('discord_start')

        self.asyncio_patch.set_event_loop_policy.side_effect = track_asyncio_policy
        self.log_info_patch.side_effect = track_log
        self.refresh_remindmes_patch.side_effect = track_refresh_remindmes
        self.refresh_autoupdates_patch.side_effect = track_refresh_autoupdates
        self.discord_bridge_patch.start.side_effect = track_discord_start

        rleb_core.start()

        # Verify correct execution order
        expected_order = [
            'asyncio_policy',
            'log_startup',
            'refresh_remindmes',
            'refresh_autoupdates',
            'log_discord',
            'discord_start'
        ]
        self.assertEqual(call_order, expected_order)

    def test_start_with_different_environments(self):
        """Test start() with different environment configurations."""
        test_cases = [
            ('production', 'real'),
            ('development', 'local'),
            ('testing', 'test'),
        ]

        for env, mode in test_cases:
            with self.subTest(environment=env, mode=mode):
                # Reset mocks
                self.log_info_patch.reset_mock()

                # Update environment
                with patch.object(global_settings, 'RUNNING_ENVIRONMENT', env):
                    with patch.object(global_settings, 'RUNNING_MODE', mode):
                        rleb_core.start()

                        # Verify correct environment is logged
                        self.log_info_patch.assert_any_call(
                            f"Starting RLEB. Running under {env} in {mode} mode."
                        )


if __name__ == "__main__":
    unittest.main()
