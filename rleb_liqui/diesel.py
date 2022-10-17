import discord
import requests
import base64
from rleb_liqui.rleb_liqui_utils import string_to_base64, base64_to_string

import rleb_settings
import rleb_stdout

async def handle_stream_lookup(url: str, channel: discord.channel.TextChannel) -> None:
    """Handle stream table lookup message.

    Args:
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for stream tables.
    """
    rleb_settings.rleb_log_info("DIESEL: Creating stream lookup for {0}".format(url))

    try:
        response = requests.get(f"http://127.0.0.1:8080/streams/{string_to_base64(url)}")
        markdown = base64_to_string(response.content)
        await rleb_stdout.print_to_channel(channel, markdown , title="Streams")
        return
    except Exception as e:
        await channel.send("Failed to build streams table :(")
        await channel.send(e)

async def healthcheck() -> str:
    try:
        return requests.get(f"http://127.0.0.1:8080/healthcheck").content.decode('utf-8').strip()
    except Exception as e:
        return f"Diesel is not running properly: {e}"

async def get_mvp_candidates(liquipedia_url: str, teams_allowed:int=4) -> str:
    """Returns a \n delimited string of mvp candidates for a given liqui url. `teams_allowed` = # of top teams to list mvp candidates for."""
    rleb_settings.rleb_log_info("DIESEL: Creating mvp lookup for {0}".format(liquipedia_url))

    response = requests.get(f"http://127.0.0.1:8080/mvp_candidates/{string_to_base64(liquipedia_url)}/teams_allowed/{teams_allowed}")
    eligible_candidates = base64_to_string(response.content)
    return eligible_candidates
