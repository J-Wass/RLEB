# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock

from tests.common.rleb_test_case import RLEBTestCase
from tests.resources.example import flair_list
import discord
import praw
import asyncio
from rleb_census import handle_user_flairs, handle_flair_census


class TestFlairCensus(RLEBTestCase):
    def test_handle_flair_census(self):
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

        loop = asyncio.new_event_loop()
        loop.run_until_complete(handle_flair_census(mock_sub, 3, mock_channel))
        loop.close()

        mock_channel.send.assert_awaited_once_with("Verified, 3\nG2, 3\nNRG, 2\n")

    # def can_get_verified_users(self):
    #     mock_sub = mock.Mock(spec=praw.models.Subreddit)
                            
    #     mock_sub.flair.return_value = example_flair_list
    #     mock_channel = mock.Mock(spec=discord.TextChannel)

    #     loop = asyncio.new_event_loop()
    #     loop.run_until_complete(handle_user_flairs(mock_sub, "Verified", mock_channel))
    #     loop.close()
    #     mock_channel.send.assert_awaited_once_with(['MadWooookie', 'John_aka_Alwayz'])

    # def can_get_users_with_chosen_flair(self):
    #     mock_sub = mock.Mock(spec=praw.models.Subreddit)
                            
    #     mock_sub.flair.return_value = example_flair_list
    #     mock_channel = mock.Mock(spec=discord.TextChannel)

    #     loop = asyncio.new_event_loop()
    #     loop.run_until_complete(handle_user_flairs(mock_sub, "Verified", mock_channel))
    #     loop.close()
    #     mock_channel.send.assert_awaited_once_with(['MadWooookie', 'ShuichiRL', 'John_aka_Alwayz', 'RLCSNews'])


if __name__ == '__main__':
    unittest.main()
