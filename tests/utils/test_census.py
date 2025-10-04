# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock

from tests.common.rleb_async_test_case import RLEBAsyncTestCase

import discord
import praw


class TestFlairCensus(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Import census after setUp is done so that rleb_settings loads with mocks/patches.
        global global_settings
        global census
        import global_settings
        import census

    async def test_handle_flair_census(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub.flair.return_value = [
            {"flair_text": ":NRG: :G2:"},
            {"flair_text": ":G2: :NRG:"},
            {"flair_text": ":G2:"},
            {"flair_text": ":FaZe: :Verified:"},
            {"flair_text": ":Verified:"},
            {"flair_text": ":Cloud9: Moderator"},
            {"flair_text": ""},
            {"flair_text": ":Verified: :MuffinMen:"},
        ]

        mock_channel = mock.Mock(spec=discord.TextChannel)

        await census.handle_flair_census(mock_sub, 3, mock_channel)

        mock_channel.send.assert_awaited_once_with(
            "Verified, 3\nG2, 3\nNRG, 2\n", embed=None
        )

    async def test_handle_verified_flair_list(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)

        mock_user_1 = mock.Mock()
        mock_user_1.name = "Memory"

        mock_user_2 = mock.Mock()
        mock_user_2.name = "Paarth"

        mock_user_3 = mock.Mock()
        mock_user_3.name = "2piece"

        mock_user_4 = mock.Mock()
        mock_user_4.name = "Jstn"

        mock_sub.flair.return_value = [
            {"flair_text": ":NRG: :G2:", "user": mock_user_4},
            {"flair_text": ":G2: :NRG:"},
            {"flair_text": ":G2:"},
            {"flair_text": ":FaZe: :Verified:", "user": mock_user_1},
            {"flair_text": ":Verified:", "user": mock_user_2},
            {"flair_text": ":Cloud9: Moderator"},
            {"flair_text": ""},
            {"flair_text": ":Verified: :MuffinMen:", "user": mock_user_3},
        ]

        mock_channel = mock.Mock(spec=discord.TextChannel)

        await census.handle_verified_flair_list(mock_sub, mock_channel)

        mock_channel.send.assert_awaited_once_with(
            "There are 3 verified users on the subreddit.\nMemory\nPaarth\n2piece\n",
            embed=None,
        )


if __name__ == "__main__":
    unittest.main()
