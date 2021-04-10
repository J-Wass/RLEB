# Dumb hack to be able to access source code files on both windows and linux
import sys
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock

from tests.common.rleb_test_case import RLEBTestCase

import praw
from rleb_dualflairs import handle_dualflair

class TestDualFlairs(RLEBTestCase):

    def setUp(self):
        self.mock_sub = mock.Mock(spec=praw.models.Subreddit)
        self.mock_sub_flair = mock.Mock(spec=praw.models.reddit.subreddit.SubredditFlair)
        self.mock_sub.flair = self.mock_sub_flair

        self.mock_redditor = mock.Mock(spec=praw.models.Redditor)
        self.mock_redditor.name = "user_name"
        return super().setUp()

    def test_handle_two_flairs(self):
        handle_dualflair(self.mock_sub, self.mock_redditor, ":NRG: :G2:", [])

        self.mock_sub_flair.set.assert_called_once_with(self.mock_redditor, text=":NRG: :G2:", css_class="")

    def test_handle_two_flairs_with_garbage_data(self):
        handle_dualflair(self.mock_sub, self.mock_redditor, ":NRG: :G2: Moderator", [])

        self.mock_sub_flair.set.assert_called_once_with(self.mock_redditor, text=":NRG: :G2:", css_class="")

    def test_handle_one_flair(self):
        handle_dualflair(self.mock_sub, self.mock_redditor, ":NRG:", [])

        self.mock_sub_flair.set.assert_called_once_with(self.mock_redditor, text=":NRG:", css_class="")

    def test_handle_disallowed_flair(self):
        handle_dualflair(self.mock_sub, self.mock_redditor, ":NRG: :Verified:", [])

        self.mock_sub_flair.set.assert_called_once_with(self.mock_redditor, text=":NRG:", css_class="")

    def test_handle_three_flairs(self):
        handle_dualflair(self.mock_sub, self.mock_redditor, ":NRG: :G2: C9:", [])

        self.mock_sub_flair.set.assert_called_once_with(self.mock_redditor, text=":NRG: :G2:", css_class="")


if __name__ == '__main__':
    unittest.main()
