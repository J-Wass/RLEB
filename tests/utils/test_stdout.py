# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, call

import requests
import discord
from discord import TextChannel


class TestStandardOut(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.mock_channel = mock.Mock(spec=discord.channel.TextChannel)

        # Mock requests.post, return a fake pasteee url.
        # TODO, use rleb_proxy on this.
        self.mock_http_post = patch("requests.post").start()
        self.mock_http_post.return_value = mock.Mock()
        self.mock_http_post.return_value.status_code = 200
        self.mock_http_post.return_value.text = '{"link": "paste.ee url"}'
        self.addCleanup(self.mock_http_post)

        # import rleb_stdout after setUp is done so that rleb_settings loads with mocks/patches
        global create_paste
        global print_to_channel
        global stdout
        global global_settings
        import stdout
        from stdout import create_paste, print_to_channel
        import global_settings

        # Remove the randomness lol
        global_settings.hooks = ["test_hook"]
        global_settings.enable_direct_channel_messages = False

    async def test_create_paste(self):
        result = await create_paste("some words", title="really cool title")

        expected_arguments = {
            "key": global_settings.PASTEEE_APP_KEY,
            "sections": [
                {
                    "name": "really cool title",
                    "syntax": "autodetect",
                    "contents": "some words",
                }
            ],
        }
        expected_headers = {"X-Auth-Token": "token"}

        self.assertEqual(result, "paste.ee url")
        self.mock_http_post.assert_called_once_with(
            "https://api.paste.ee/v1/pastes",
            json=expected_arguments,
            headers=expected_headers,
        )

    async def test_print_to_channel_calls_create_paste(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "create_paste") as mocked_create_paste:
            await print_to_channel(
                mock_channel, "some cool content", title="the best title"
            )
            mocked_create_paste.assert_awaited_once_with(
                "some cool content", title="the best title"
            )

    async def test_print_to_channel_returns_url(self):
        mock_channel = mock.Mock(spec=discord.TextChannel)
        await print_to_channel(
            mock_channel, "some cool content", title="the best title"
        )

        mock_channel.send.assert_awaited_once_with("**test_hook**: paste.ee url")

    async def test_print_to_channel_with_exception(self):
        # Set the pastebin response to be 500, so that the alternative std out is used.
        self.mock_http_post.return_value.status_code = 501
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)

        await print_to_channel(mock_channel, "a\nb\nc\nd\ne\nf", title="the best title")

        # A pastebin exception should cause the content to be marshalled out to the channel, 5 lines at a time.
        mock_channel.send.assert_has_awaits(
            [call("a\nb\nc\nd\ne", embed=None), call("f", embed=None)]
        )

    async def test_print_to_channel_with_direct_messaging(self):
        global_settings.enable_direct_channel_messages = True
        mock_channel = mock.Mock(spec=discord.TextChannel)

        with patch.object(stdout, "create_paste") as mocked_create_paste:
            await print_to_channel(
                mock_channel, "some cool content", title="the best title"
            )

            # With direct channel messaging, a pastebin should not be generated.
            mock_channel.send.assert_called_once_with("some cool content", embed=None)
            mocked_create_paste.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
