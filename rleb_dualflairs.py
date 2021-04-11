import re

import rleb_settings
from rleb_settings import flair_pattern, rleb_log_info

# allowlist of allowed flairs
# fallback if file not found
allowed = [
    ":ARG:", ":Afterthought:", ":Birds_and_the_Beez:", ":Bull_Send:",
    ":Chiefs:", ":Cloud9:", ":Compadres:", ":Dignitas:", ":Discombobulators:",
    ":EU_RLCS_Fan:", ":Esper:", ":EvilGeniuses:", ":FC_Barcelona:",
    ":Fadeaway:", ":FantasyDeath:", ":Flipsid3Tactics:", ":Frontline:", ":G2:",
    ":Ghost:", ":GaleForce:", ":GfactorGalaxy:", ":Ground_Zero:", ":Hawks:",
    ":INTZ:", ":KingsOfUrban:", ":Leftovers:", ":Linked_Up:", ":Lotus:",
    ":LowkeyEsports:", ":Maxs_Rancid_Rats:"
    ":Method:", ":Mindfreak:", ":NA_RLCS_Fan:", ":NRG:", ":NRG_Legacy:",
    ":Nordavind:", ":NorthernGaming:", ":ORDER:", ":Orchid:", ":Overt:",
    ":Oxey_Team:", ":RGRR:", ":Reciprocity:"
    ":Renegades:", ":Rogue:", ":SpacestationGaming:", ":TSM:",
    ":TeamEchoZulu:", ":Team_Vertex:", ":TheBricks:", ":TheD00ds:",
    ":ThePeeps:", ":The_Three_Sins:", ":TripleTrouble:", ":Upper90:",
    ":Veloce:", ":Vendetta:", ":Vikings:", ":Vitality:", ":WeDemGirlz:",
    ":complexity:", ":iBuyPower:", ":mousesports:", ":AIN:", ":Goat_Gaming:",
    ":Pittsburgh_Knights:", ":FlompResont:", ":Chaos:", ":Full_Metal_Gaming:",
    ":Monos:", ":RCD_Espanyol:", ":Charlotte_Phoenix:"
]


def handle_dualflair(sub, user, body):
    """Read, verify, and act of dualflair messages.

    Args:
        sub (praw.models.Subreddit): Subreddit to change user flairs in.
        user (praw.models.Redditor): Redditor requesting flair change.
        body (str): Text of user-sent message.
    """
    # mods can set it to anything so they can add text such as "moderator" to flair
    if user.name in list(map(lambda x: x.name, rleb_settings.moderators)):
        sub.flair.set(user, text=body, css_class="")
        rleb_log_info("REDDIT: Set mod flair for {0} to {1}".format(
            user.name, body))
    else:
        db = rleb_settings.postgresConnection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM dualflairs;")
        dualflairs = cursor.fetchall()
        if dualflairs:
            allowed = list(map(lambda x: x[0], dualflairs))
        # break string into :emoji: tokens
        flairs = re.findall(flair_pattern, body)
        seen = set()
        flairs = [f for f in flairs if not (f in seen or seen.add(f))]
        # only get allowed emoji tokens
        allowed_flairs = [f for f in flairs if f in allowed]
        first_two = allowed_flairs[:2]
        final_flair = " ".join(first_two)
        sub.flair.set(user, text=final_flair, css_class="")
        rleb_log_info("\nREDDIT: Flair request for u/{0}: {1}".format(
            user.name, body))
        rleb_log_info("REDDIT: Requesting: {0}".format(",".join(flairs)))
        rleb_log_info("REDDIT: Allowing: {0}".format(",".join(allowed_flairs)))
        rleb_log_info("REDDIT: Taking: {0}".format(",".join(first_two)))
        rleb_log_info("REDDIT: Set flair for {0} to {1}".format(
            user.name, first_two))
