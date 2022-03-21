import re

import rleb_settings
from rleb_settings import flair_pattern, rleb_log_info
from rleb_data import Data

from praw.reddit import models as praw_models

def handle_flair_request(sub: praw_models.Subreddit, user: praw_models.Redditor, body: str) -> None:
    """Read, verify, and act of dualflair messages.

    Args:
        sub (praw.models.Subreddit): Subreddit to change user flairs in.
        user (praw.models.Redditor): Redditor requesting flair change.
        body (str): Text of user-sent message.
    """
    # mods can set it to anything so they can add text such as "moderator" to flair
    if user.name in list(map(lambda x: x.name, rleb_settings.moderators)):
        sub.flair.set(user, text=body, css_class="")
        rleb_log_info("REDDIT: Set mod flair for {0} to {1}".format(user.name, body))
    else:
        dualflairs = Data.singleton().read_dualflairs()
        if dualflairs:
            allowed = list(map(lambda x: x[0], dualflairs))

        # break string into :emoji: tokens
        flairs = re.findall(flair_pattern, body)
        seen = set()
        flairs = [f for f in flairs if not (f in seen or seen.add(f))]

        # only get allowed emoji tokens
        allowed_flairs = [f for f in flairs if f in allowed]

        # take the first n flairs (n = # of allowed flairs)
        first_n_flairs = allowed_flairs[:rleb_settings.number_of_allowed_flairs]

        rleb_log_info("\nREDDIT: Flair request for u/{0}: {1}".format(user.name, body))
        rleb_log_info("REDDIT: Requesting: {0}".format(",".join(flairs)))
        rleb_log_info("REDDIT: Allowing: {0}".format(",".join(allowed_flairs)))

        if first_n_flairs != flairs:
            message = f"\"{body}\" wasn't formatted correctly!\n\nMake sure that you are using {rleb_settings.number_of_allowed_flairs} or less flairs and that your flairs are spelled correctly.\n\nSee all allowed flairs: https://www.reddit.com/r/RocketLeagueEsports/wiki/flairs#wiki_how_do_i_get_2_user_flairs.3F \n\n(I'm a bot. Contact modmail to get in touch with a real person: https://reddit.com/message/compose?to=/r/RocketLeagueEsports)"
            user.message("Error with flair request", message)
        else:
            final_flair_text = " ".join(first_n_flairs)
            sub.flair.set(user, text=final_flair_text, css_class="")

            rleb_log_info("REDDIT: Taking: {0}".format(",".join(first_n_flairs)))
            rleb_log_info("REDDIT: Set flair for {0} to {1}".format(user.name, final_flair_text))
