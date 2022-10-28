[![Python Tests](https://github.com/J-Wass/RLEB/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/J-Wass/RLEB/actions/workflows/main.yml)
[![codecov](https://codecov.io/github/J-Wass/RLEB/branch/main/graph/badge.svg?token=51JCI81BGZ)](https://codecov.io/github/J-Wass/RLEB) 

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

# Running RLEB:

1. `pip install -r requirements.txt`
2. `python rleb_core.py`

Note that you will need to create an `rleb_secrets.py` file if running RLEB locally. This file contains info about API keys, usernames, etc. Check out the [sample secrets](https://github.com/J-Wass/RLEB/blob/main/rleb_sample_secrets.py) to learn more. You can also deploy with these secrets key-value pairs as OS ENV variables.

If using liqui tools, you should also run [Diesel](https://github.com/J-Wass/Diesel) @ 127.0.0.1:8080. Diesel is a fast media wiki parser that turns media wiki pages into reddit markdown. It's written and Go and is impemented as an http server that RLEB can talk to. RLEB can also parse media wiki, but it is over 10x slower than Diesel.

# Apple lol

Mac users (especially on M1 chipset) may need to set certain flags to be able to install everything from requirements.txt.

	# Clone rleb into a fresh directory

	> brew install postgresql

	# Open new terminal window

	> export CPPFLAGS="-I/opt/homebrew/opt/openssl@1.1/include"
	> export LDFLAGS="-L/opt/homebrew/opt/openssl@1.1/lib -L${HOME}/.pyenv/versions/3.8.10/lib"
	> python3 -m venv env
	> source env/bin/activate
	> pip3 install -r requirements.txt
	> pip3 install aiohttp==3.7.4
	> pip3 install -U discord.py

	# Go to MacintoshHD -> Applications -> Python3.x Folder
	# Double click on the "Install Certificates.command".

