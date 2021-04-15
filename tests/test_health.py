# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock

from tests.common.rleb_test_case import RLEBTestCase

import 

class TestHealth(RLEBTestCase):
    def setUp(self):
        super().setUp()

        self.mock_sub_flair = mock.Mock(
            spec=praw.models.reddit.subreddit.SubredditFlair)
        self.mock_sub.flair = self.mock_sub_flair

        self.mock_redditor = mock.Mock(spec=praw.models.Redditor)
        self.mock_redditor.name = "user_name"

        # import rleb_core after setUp is done so that rleb_settings loads with mocks/patches
        global rleb_core
        from rleb_core import handle_dualflair
        import rleb_settings


    def test_handle_two_flairs(self):
        handle_dualflair(self.mock_sub, self.mock_redditor, ":NRG: :G2:")

        self.mock_sub_flair.set.assert_called_once_with(self.mock_redditor,
                                                        text=":NRG: :G2:",
                                                        css_class="")

if __name__ == '__main__':
    unittest.main()
