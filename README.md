# r/RocketLeagueEsports Bot (RLEB)

This is RLEB: a bot that is developed and maintained by the moderators of https://www.reddit.com/r/RocketLeagueEsports.

RLEB has many features including

- [Handling dualflairs](https://www.reddit.com/r/RocketLeagueEsports/wiki/flairs#wiki_how_do_i_get_2_user_flairs.3F)
- Tools to build reddit threads
- Tools to organize moderator tasks
- Reddit <---> Discord bridges

# Getting started

The following are instructions on setting up the RLEsportsBot locally. Firstly clone the repo and follow the example steps.

## Prerequisites

Use a Python virtualenv to install all the packages you need in a containted environment.

Also required is Google Chrome to be installed to use `!teams !postmatch !groups` etc. commands.

Then copy your `secrets.py` file into the main repository folder.

See `secrets.example.py` for an example of the structure of this file.

## Installing and setting up the environment

1. Install a virtual environment package

   ```py
   pip install virtualenv
   ```

2. Create a virtualenv folder

   ```py
   virtualenv venv
   ```

3. Activate virtual environment

   ```py
   source venv/bin/activate
   ```

4. Install the relevant packages to this repository

   ```py
   pip install -r requirements.txt
   ```

Once setup rerun steps 4 & 5 before each new update.

# Usage

Run the bot locally. The following is the entry point.

```py
python rleb_core.py
```

# Tests

[![Python Tests](https://github.com/J-Wass/RLEB/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/J-Wass/RLEB/actions/workflows/main.yml)

# License - SQLite 2001 September 15

    The authors disclaim copyright to this source code.
    In place of a legal notice, here is a blessing:

    	May you do good and not evil.
    	May you find forgiveness for yourself and for others.
    	May you share freely, never taking more than you give.
