# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
from unittest.mock import Mock
from tests.common.rleb_test_case import RLEBTestCase

import discord


class TestVerifiedModerators(RLEBTestCase):
    def setUp(self):
        super().setUp()

        # import rleb_settings after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_settings
        import rleb_settings

    def test_verified_moderator(self):
        rleb_settings.verified_moderators = ['janedoe#1023']

        mock_author = Mock(spec=discord.Member)
        mock_author.name = 'JaneDoe'
        mock_author.discriminator = '1023'

        self.assertTrue(rleb_settings.is_discord_mod(mock_author))

    def test_non_verified_moderator(self):
        rleb_settings.verified_moderators = ['janedoe#1023']

        mock_author = Mock(spec=discord.Member)
        mock_author.name = 'JohnSmith'
        mock_author.discriminator = '2031'

        self.assertFalse(rleb_settings.is_discord_mod(mock_author))


if __name__ == '__main__':
    unittest.main()
