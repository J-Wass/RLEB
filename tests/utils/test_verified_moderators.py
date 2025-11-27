# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
from unittest.mock import Mock

import discord


class TestVerifiedModerators(unittest.TestCase):
    def setUp(self):
        super().setUp()

        # import rleb_settings after setUp is done so that rleb_settings loads with mocks/patches
        global global_settings
        import global_settings

    def test_verified_moderator(self):
        global_settings.verified_moderators = ["janedoe#1023"]

        mock_author = Mock(spec=discord.Member)
        mock_author.name = "JaneDoe"
        mock_author.discriminator = "1023"

        self.assertTrue(global_settings.is_discord_mod(mock_author))

    def test_non_verified_moderator(self):
        global_settings.verified_moderators = ["janedoe#1023"]

        mock_author = Mock(spec=discord.Member)
        mock_author.name = "JohnSmith"
        mock_author.discriminator = "2031"

        self.assertFalse(global_settings.is_discord_mod(mock_author))


if __name__ == "__main__":
    unittest.main()
