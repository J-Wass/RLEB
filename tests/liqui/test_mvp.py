"""Tests for liqui/mvp_lookup.py"""

import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

import unittest
from unittest.mock import AsyncMock, MagicMock, patch


from liqui.mvp_lookup import (
    MVPCandidates,
    handle_mvp_form_creation,
    handle_mvp_results_lookup,
)
import global_settings


class TestMVPCandidates(unittest.TestCase):
    """Test cases for MVPCandidates class."""

    def test_mvp_candidates_initialization(self):
        """Test MVPCandidates object initialization."""
        title = "NA Regional"
        candidates = ["jstn", "Firstkiller", "Daniel"]

        mvp_candidates = MVPCandidates(title, candidates)

        self.assertEqual(mvp_candidates.title, title)
        self.assertEqual(mvp_candidates.candidates, candidates)

    def test_mvp_candidates_repr(self):
        """Test MVPCandidates string representation."""
        title = "EU Regional"
        candidates = ["Vatira", "Zen", "Joyo"]

        mvp_candidates = MVPCandidates(title, candidates)
        repr_str = repr(mvp_candidates)

        self.assertIn(title, repr_str)
        self.assertIn("Vatira", repr_str)
        self.assertIn("Zen", repr_str)
        self.assertIn("Joyo", repr_str)


class TestMVPFormCreation(unittest.TestCase):
    """Test cases for MVP form creation functionality."""

    def setUp(self):
        super().setUp()

        # Mock _get_mvp_candidates
        self.get_candidates_patch = patch(
            "liqui.mvp_lookup._get_mvp_candidates"
        ).start()

        # Mock _get_mvp_markdown
        self.get_markdown_patch = patch("liqui.mvp_lookup._get_mvp_markdown").start()

        # Mock stdout
        self.print_to_channel_patch = patch(
            "liqui.mvp_lookup.stdout.print_to_channel"
        ).start()

        self.addCleanup(patch.stopall)

    async def test_handle_mvp_form_creation_success(self):
        """Test successful MVP form creation."""
        channel = AsyncMock()
        liquipedia_urls = [
            "https://liquipedia.net/rocketleague/RLCS/NA",
            "https://liquipedia.net/rocketleague/RLCS/EU",
        ]

        # Mock candidate groups
        candidate_groups = [
            MVPCandidates("NA Regional", ["jstn", "Firstkiller", "Daniel"]),
            MVPCandidates("EU Regional", ["Vatira", "Zen", "Joyo"]),
        ]
        self.get_candidates_patch.return_value = candidate_groups

        # Mock markdown
        mvp_markdown = "# Vote for MVP\n\n[Form Link](https://forms.google.com/test)"
        self.get_markdown_patch.return_value = mvp_markdown

        await handle_mvp_form_creation(liquipedia_urls, channel)

        # Verify candidates were fetched
        self.get_candidates_patch.assert_called_once_with(liquipedia_urls, channel)

        # Verify markdown was generated
        self.get_markdown_patch.assert_called_once_with(candidate_groups, channel)

        # Verify markdown was printed
        self.print_to_channel_patch.assert_called_once_with(
            channel, mvp_markdown, title="RLCS 21-22 | Weekend MVP Poll"
        )

    async def test_handle_mvp_form_creation_no_candidates(self):
        """Test MVP form creation when no candidates are found."""
        channel = AsyncMock()
        liquipedia_urls = ["https://liquipedia.net/rocketleague/RLCS/Test"]

        # Mock no candidates found
        self.get_candidates_patch.return_value = None

        await handle_mvp_form_creation(liquipedia_urls, channel)

        # Verify error message was sent
        channel.send.assert_called_once_with(
            f"Could't find mvp candidates from {channel}."
        )

    async def test_handle_mvp_form_creation_empty_candidates(self):
        """Test MVP form creation with empty candidate list."""
        channel = AsyncMock()
        liquipedia_urls = ["https://liquipedia.net/rocketleague/RLCS/Test"]

        # Mock empty candidates
        self.get_candidates_patch.return_value = []

        await handle_mvp_form_creation(liquipedia_urls, channel)

        # Verify error message was sent
        channel.send.assert_called_once_with(
            f"Could't find mvp candidates from {channel}."
        )

    async def test_handle_mvp_form_creation_no_markdown(self):
        """Test MVP form creation when markdown generation fails."""
        channel = AsyncMock()
        liquipedia_urls = ["https://liquipedia.net/rocketleague/RLCS/Test"]

        # Mock candidates but no markdown
        candidate_groups = [
            MVPCandidates("NA Regional", ["jstn", "Firstkiller", "Daniel"])
        ]
        self.get_candidates_patch.return_value = candidate_groups
        self.get_markdown_patch.return_value = None

        await handle_mvp_form_creation(liquipedia_urls, channel)

        # Verify error message was sent
        channel.send.assert_called_once_with(
            f"Could't find mvp candidates from {channel}."
        )


class TestMVPResultsLookup(unittest.IsolatedAsyncioTestCase):
    """Test cases for MVP results lookup functionality."""

    def setUp(self):
        super().setUp()

        # Mock _get_mvp_form_responses
        self.get_responses_patch = patch(
            "liqui.mvp_lookup._get_mvp_form_responses"
        ).start()

        # Mock stdout
        self.print_to_channel_patch = patch(
            "liqui.mvp_lookup.stdout.print_to_channel"
        ).start()

        self.addCleanup(patch.stopall)

    async def test_handle_mvp_results_lookup_with_exception(self):
        """Test MVP results lookup handles exceptions properly."""
        channel = AsyncMock()
        form_url = "https://docs.google.com/forms/d/test/edit"

        # Mock exception
        error_message = "Failed to access form"
        self.get_responses_patch.side_effect = Exception(error_message)

        await handle_mvp_results_lookup(form_url, channel)

        # Verify error messages were sent
        channel.send.assert_any_call(f"\nCouldn't get form responses for {form_url}.")

        # Check that an error with the exception was sent
        calls = [str(call) for call in channel.send.call_args_list]
        self.assertTrue(
            any(error_message in str(call) for call in calls),
            "Error message should be sent to channel",
        )

    async def test_handle_mvp_results_lookup_success(self):
        """Test successful MVP results lookup."""
        channel = AsyncMock()
        form_url = "https://docs.google.com/forms/d/test/edit"

        # Mock form responses - format is ("Player (Team)", percentage)
        mock_responses = {
            "NA Regional": [
                ("jstn (G2 Esports)", 45.0),
                ("Firstkiller (FaZe Clan)", 30.0),
                ("Daniel (Spacestation)", 15.0),
                ("BeastMode (NRG)", 7.0),
                ("Chicago (NRG)", 3.0),
            ]
        }
        self.get_responses_patch.return_value = mock_responses

        await handle_mvp_results_lookup(form_url, channel)

        # Verify responses were fetched
        self.get_responses_patch.assert_called_once_with(form_url)

        # Verify markdown was printed
        self.print_to_channel_patch.assert_called_once()

        # Check the markdown contains expected content
        markdown_arg = self.print_to_channel_patch.call_args[0][1]
        self.assertIn("NA Regional", markdown_arg)
        self.assertIn("jstn", markdown_arg)
        self.assertIn("45", markdown_arg)  # Percentage


if __name__ == "__main__":
    unittest.main()
