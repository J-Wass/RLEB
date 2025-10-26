# Test for liqui/diesel.py
import sys
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock
from unittest.mock import patch, AsyncMock
from tests.common.rleb_async_test_case import RLEBAsyncTestCase
import discord

from liqui import diesel
from liqui.liqui_utils import string_to_base64
import requests

class TestDiesel(RLEBAsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Mock aliases
        self.data_stub.read_all_aliases.return_value = {
            "Team_Envy": "NV",
            "NRG_Esports": "NRG"
        }

        # Mock requests.get to return valid base64-encoded responses
        def mock_diesel_request(url, *args, **kwargs):
            class MockResponse:
                def __init__(self, content, status_code=200):
                    self.content = content if isinstance(content, bytes) else content.encode('utf-8')
                    self.status_code = status_code
                    self.text = content if isinstance(content, str) else content.decode('utf-8')

                def decode(self, encoding='utf-8'):
                    return self.content.decode(encoding)

            # Return mock markdown based on endpoint
            if 'healthcheck' in url:
                return MockResponse('OK')
            elif 'prizepool' in url:
                return MockResponse('UHJpemVwb29sIG1hcmtkb3du')  # "Prizepool markdown" in base64
            elif 'swiss' in url:
                return MockResponse('U3dpc3MgbWFya2Rvd24=')  # "Swiss markdown" in base64
            elif 'bracket' in url:
                return MockResponse('QnJhY2tldCBtYXJrZG93bg==')  # "Bracket markdown" in base64
            elif 'groups' in url:
                return MockResponse('R3JvdXAgbWFya2Rvd24=')  # "Group markdown" in base64
            elif 'makethread' in url:
                return MockResponse('TWFrZXRocmVhZCBtYXJrZG93bg==')  # "Makethread markdown" in base64
            elif 'broadcast' in url:
                return MockResponse('QnJvYWRjYXN0IG1hcmtkb3du')  # "Broadcast markdown" in base64
            elif 'streams' in url:
                return MockResponse('U3RyZWFtcyBtYXJrZG93bg==')  # "Streams markdown" in base64
            elif 'schedule' in url:
                return MockResponse('U2NoZWR1bGUgbWFya2Rvd24=')  # "Schedule markdown" in base64
            elif 'coverage' in url:
                return MockResponse('Q292ZXJhZ2UgbWFya2Rvd24=')  # "Coverage markdown" in base64
            elif 'mvp_candidates' in url:
                return MockResponse('TVZQIGNhbmRpZGF0ZXM=')  # "MVP candidates" in base64
            return MockResponse('')

        self.mock_diesel_requests = patch.object(requests, 'get', side_effect=mock_diesel_request).start()
        self.addCleanup(self.mock_diesel_requests.stop)

    async def test_healthcheck_success(self):
        """Test diesel healthcheck returns status."""
        result = await diesel.healthcheck()
        self.assertEqual(result, 'OK')

    async def test_get_prizepool_markdown(self):
        """Test prizepool markdown generation."""
        result = await diesel.get_prizepool_markdown("https://liquipedia.net/test")
        self.assertEqual(result, "Prizepool markdown")

    async def test_get_swiss_markdown(self):
        """Test swiss bracket markdown generation."""
        result = await diesel.get_swiss_markdown("https://liquipedia.net/test")
        self.assertEqual(result, "Swiss markdown")

    async def test_get_bracket_markdown(self):
        """Test bracket markdown generation."""
        result = await diesel.get_bracket_markdown("https://liquipedia.net/test", 1)
        self.assertEqual(result, "Bracket markdown")

    async def test_get_bracket_markdown_date(self):
        """Test bracket markdown generation by date."""
        result = await diesel.get_bracket_markdown_date("https://liquipedia.net/test", 20220101)
        self.assertEqual(result, "Bracket markdown")

    async def test_get_group_markdown(self):
        """Test group markdown generation."""
        result = await diesel.get_group_markdown("https://liquipedia.net/test")
        self.assertEqual(result, "Group markdown")

    async def test_handle_makethread_lookup(self):
        """Test makethread handler with channel."""
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        with patch('stdout.print_to_channel', new_callable=mock.AsyncMock) as mock_print:
            await diesel.handle_makethread_lookup("https://liquipedia.net/test", "template", 1, mock_channel)
            mock_print.assert_awaited_once()

    async def test_handle_broadcast_lookup(self):
        """Test broadcast lookup handler."""
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        with patch('stdout.print_to_channel', new_callable=mock.AsyncMock) as mock_print:
            await diesel.handle_broadcast_lookup("https://liquipedia.net/test", mock_channel)
            mock_print.assert_awaited_once()

    async def test_handle_stream_lookup(self):
        """Test stream lookup handler."""
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        with patch('stdout.print_to_channel', new_callable=mock.AsyncMock) as mock_print:
            await diesel.handle_stream_lookup("https://liquipedia.net/test", mock_channel)
            mock_print.assert_awaited_once()

    async def test_handle_schedule_lookup(self):
        """Test schedule lookup handler."""
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        with patch('stdout.print_to_channel', new_callable=mock.AsyncMock) as mock_print:
            await diesel.handle_schedule_lookup("https://liquipedia.net/test", 1, mock_channel)
            mock_print.assert_awaited_once()

    async def test_handle_schedule_lookup_date(self):
        """Test schedule lookup handler by date."""
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        with patch('stdout.print_to_channel', new_callable=mock.AsyncMock) as mock_print:
            await diesel.handle_schedule_lookup_date("https://liquipedia.net/test", 20220101, mock_channel)
            mock_print.assert_awaited_once()

    async def test_handle_coverage_lookup(self):
        """Test coverage lookup handler."""
        mock_channel = mock.AsyncMock(spec=discord.TextChannel)
        with patch('stdout.print_to_channel', new_callable=mock.AsyncMock) as mock_print:
            await diesel.handle_coverage_lookup("https://liquipedia.net/test", mock_channel)
            mock_print.assert_awaited_once()

    async def test_get_mvp_candidates(self):
        """Test MVP candidates retrieval."""
        result = await diesel.get_mvp_candidates("https://liquipedia.net/test", 4)
        self.assertEqual(result, "MVP candidates")

if __name__ == "__main__":
    unittest.main()
