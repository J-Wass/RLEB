# Dumb hack to be able to access source code files on both windows and linux
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/..")

import unittest
import unittest.mock as mock

from tests.common.rleb_test_case import RLEBTestCase

import praw


class TestDualFlairs(RLEBTestCase):
    def setUp(self):
        super().setUp()

        self.mock_sub = mock.Mock(spec=praw.reddit.models.Subreddit)
        self.mock_sub_flair = mock.MagicMock()
        self.mock_sub.flair = self.mock_sub_flair

        self.mock_redditor = mock.Mock(spec=praw.reddit.models.Redditor)
        self.mock_redditor.name = "user_name"

        # import rleb_dualflairs after setUp is done so that rleb_settings loads with mocks/patches
        global handle_flair_request
        global rleb_settings
        global rleb_reddit
        from rleb_triflairs import handle_flair_request
        from rleb_reddit import monitor_modmail
        import rleb_settings

        # Dualflairs spams the console so much.
        rleb_settings.logging_enabled = False

    def tearDown(self):
        rleb_settings.logging_enabled = True
        super().tearDown()

    def test_handle_two_flairs(self):
        handle_flair_request(self.mock_sub, self.mock_redditor, ":NRG: :G2:")

        self.mock_sub_flair.set.assert_called_once_with(
            self.mock_redditor, text=":NRG: :G2:", css_class=""
        )

    def test_handle_two_flairs_with_garbage_data(self):
        handle_flair_request(self.mock_sub, self.mock_redditor, ":NRG: :G2: Moderator")

        self.mock_sub_flair.set.assert_called_once_with(
            self.mock_redditor, text=":NRG: :G2:", css_class=""
        )

    def test_handle_one_flair(self):
        handle_flair_request(self.mock_sub, self.mock_redditor, ":NRG:")

        self.mock_sub_flair.set.assert_called_once_with(
            self.mock_redditor, text=":NRG:", css_class=""
        )

    def test_handle_disallowed_flair(self):
        handle_flair_request(self.mock_sub, self.mock_redditor, ":NRG: :Verified:")

        # self.mock_sub_flair.set.assert_not_awaited()
        expected_message = "\":NRG: :Verified:\" wasn't formatted correctly!\n\nMake sure that you are using 3 or less flairs and that your flairs are spelled correctly.\n\nSee all allowed flairs: https://www.reddit.com/r/RocketLeagueEsports/wiki/flairs#wiki_how_do_i_get_2_user_flairs.3F \n\n(I'm a bot. Contact modmail to get in touch with a real person: https://reddit.com/message/compose?to=/r/RocketLeagueEsports)"
        self.mock_redditor.message.assert_called_once_with(
            "Error with flair request", expected_message
        )
        self.mock_sub_flair.set.assert_not_called()

    def test_handle_three_flairs(self):
        handle_flair_request(self.mock_sub, self.mock_redditor, ":NRG: :G2: :C9:")

        self.mock_sub_flair.set.assert_called_once_with(
            self.mock_redditor, text=":NRG: :G2: :C9:", css_class=""
        )

    def test_handle_moderator_flair(self):
        mock_moderator = mock.Mock(auto_spec=praw.models.Redditor)
        mock_moderator.name = "mr_mod"

        handle_flair_request(self.mock_sub, mock_moderator, ":NRG: Modguy")

        self.mock_sub_flair.set.assert_called_once_with(
            mock_moderator, text=":NRG: Modguy", css_class=""
        )


if __name__ == "__main__":
    unittest.main()
