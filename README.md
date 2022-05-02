[![Python Tests](https://github.com/J-Wass/RLEB/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/J-Wass/RLEB/actions/workflows/main.yml)

# Legal Disclaimer

    The author(s) disclaim copyright to this source code.
    In place of a legal notice, here is a blessing:

    	May you use your opportunities for good and not ill.
    	May you find forgiveness for yourself and for others.
    	May you share freely, never taking more than you give.


# r/RocketLeagueEsports Bot (RLEB)

This is RLEB - a bot that is developed and maintained by the moderators of https://www.reddit.com/r/RocketLeagueEsports.

RLEB has many features including

- Handling user flairs
- Tools to build reddit threads
- Tools to organize moderator tasks
- Reddit <---> Discord bridges
- And many other small tools that mods use to improve their job

RLEB can be run easily:

1. `pip install -r requirements.txt`
2. `python rleb_core.py`

Note that you will need to create an `rleb_secrets.py` file if running RLEB locally. This file contains info about API keys, usernames, etc. You can also optionally set up env vars in place of a secrets file. See [the settings file](https://github.com/J-Wass/RLEB/blob/main/rleb_settings.py) for more information on which secrets need to be added. You can also turn off some features from that same settings file if you don't need to use every API integration.
