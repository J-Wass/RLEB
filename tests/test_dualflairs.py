import unittest
import unittest.mock as mock

import praw

# Dumb hack to be able to access source code files on both windows and linux
import sys
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

from rleb_dualflairs import handle_dualflair

class TestDualFlairs(unittest.TestCase):

    def test_handle_two_flairs(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub_flair = mock.Mock(spec=praw.models.reddit.subreddit.SubredditFlair)
        mock_sub.flair = mock_sub_flair

        mock_redditor = mock.Mock(spec=praw.models.Redditor)
        mock_redditor.name = "user name"

        handle_dualflair(mock_sub, mock_redditor, ":NRG: :G2:", [])

        mock_sub_flair.set.assert_called_once_with(mock_redditor, text=":NRG: :G2:", css_class="")

    def test_handle_two_flairs_with_garbage_data(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub_flair = mock.Mock(spec=praw.models.reddit.subreddit.SubredditFlair)
        mock_sub.flair = mock_sub_flair

        mock_redditor = mock.Mock(spec=praw.models.Redditor)
        mock_redditor.name = "user name"

        handle_dualflair(mock_sub, mock_redditor, ":NRG: :G2: Moderator", [])

        mock_sub_flair.set.assert_called_once_with(mock_redditor, text=":NRG: :G2:", css_class="")

    def test_handle_one_flair(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub_flair = mock.Mock(spec=praw.models.reddit.subreddit.SubredditFlair)
        mock_sub.flair = mock_sub_flair

        mock_redditor = mock.Mock(spec=praw.models.Redditor)
        mock_redditor.name = "user name"

        handle_dualflair(mock_sub, mock_redditor, ":NRG:", [])

        mock_sub_flair.set.assert_called_once_with(mock_redditor, text=":NRG:", css_class="")

    def test_handle_disallowed_flair(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub_flair = mock.Mock(spec=praw.models.reddit.subreddit.SubredditFlair)
        mock_sub.flair = mock_sub_flair

        mock_redditor = mock.Mock(spec=praw.models.Redditor)
        mock_redditor.name = "user name"

        handle_dualflair(mock_sub, mock_redditor, ":NRG: :Verified:", [])

        mock_sub_flair.set.assert_called_once_with(mock_redditor, text=":NRG:", css_class="")

    def test_handle_three_flairs(self):
        mock_sub = mock.Mock(spec=praw.models.Subreddit)
        mock_sub_flair = mock.Mock(spec=praw.models.reddit.subreddit.SubredditFlair)
        mock_sub.flair = mock_sub_flair

        mock_redditor = mock.Mock(spec=praw.models.Redditor)
        mock_redditor.name = "user name"

        handle_dualflair(mock_sub, mock_redditor, ":NRG: :G2: C9:", [])

        mock_sub_flair.set.assert_called_once_with(mock_redditor, text=":NRG: :G2:", css_class="")


if __name__ == '__main__':
    unittest.main()
