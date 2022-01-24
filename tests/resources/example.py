class Redditor():
    def __init__(self, name):
        self.name = name

flair_list: list[dict] = [
            {
                "flair_css_class": None,
                "user": Redditor(name="MadWooookie"),
                "flair_text": ":Verified: :F3:",
            },
            {
                "flair_css_class": None,
                "user": Redditor(name="theblondemonkey"),
                "flair_text": ":mod:",
            },
            {
                "flair_css_class": None,
                "user": Redditor(name="ShuichiRL"),
                "flair_text": ":Cloud9: :Verified:",
            },
            {
                "flair_css_class": "",
                "user": Redditor(name="John_aka_Alwayz"),
                "flair_text": ":PSGLogo: :mod: :TeamDignitas: :F3: :NRG: :G2: :Chiefs: :Verified:",
            },
            {
                "flair_css_class": None,
                "user": Redditor(name="Beatmastaflex"),
                "flair_text": ":TeamDignitas:",
            },
            {
                "flair_css_class": "vitality",
                "user": Redditor(name="RLCSNews"),
                "flair_text": ":Vitality: :Verified:",
            }
        ]
