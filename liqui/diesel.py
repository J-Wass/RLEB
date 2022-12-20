import discord
import requests
from liqui.liqui_utils import string_to_base64, base64_to_string

import global_settings
import stdout


async def handle_stream_lookup(url: str, channel: discord.channel.TextChannel) -> None:
    """Handle stream table lookup message.

    Args:
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for stream tables.
    """
    global_settings.rleb_log_info("DIESEL: Creating stream lookup for {0}".format(url))

    try:
        response = requests.get(
            f"http://127.0.0.1:8080/streams/{string_to_base64(url)}"
        )
        markdown = base64_to_string(response.content)
        await stdout.print_to_channel(channel, markdown, title="Streams")
        return
    except Exception as e:
        await channel.send("Failed to build streams table :(")
        await channel.send(e)

async def handle_schedule_lookup(liquipedia_url: str, day_number: int, channel: discord.channel.TextChannel) -> None:
    """Handle schedule table lookup message.

    Args:
        url (str): Liquipedia URL string to look for stream tables.
        day_number (int): The day (usually 1, 2, or 3) of the event to create a schedule for.
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
    """
    global_settings.rleb_log_info(f"DIESEL: Creating schedule lookup for {liquipedia_url} day {day_number}".format(liquipedia_url))

    try:
        response = requests.get(
        f"http://127.0.0.1:8080/schedule/{string_to_base64(liquipedia_url)}/day/{day_number}"
    )
        markdown = base64_to_string(response.content)
        await stdout.print_to_channel(channel, markdown, title="Streams")
        return
    except Exception as e:
        await channel.send("Failed to build schedule table :(")
        await channel.send(e)
       

async def handle_coverage_lookup(url: str, channel: discord.channel.TextChannel) -> None:
    """Handle coverage table lookup message.

    Args:
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for coverage tables.
    """
    global_settings.rleb_log_info("DIESEL: Creating coverage lookup for {0}".format(url))

    try:
        response = requests.get(
            f"http://127.0.0.1:8080/coverage/{string_to_base64(url)}"
        )
        markdown = base64_to_string(response.content)
        await stdout.print_to_channel(channel, markdown, title="Coverage")
        return
    except Exception as e:
        await channel.send("Failed to build coverage table :(")
        await channel.send(e)


async def healthcheck() -> str:
    try:
        return (
            requests.get(f"http://127.0.0.1:8080/healthcheck")
            .content.decode("utf-8")
            .strip()
        )
    except Exception as e:
        return f"Diesel is not running properly: {e}"


async def get_mvp_candidates(liquipedia_url: str, teams_allowed: int = 4) -> str:
    """Returns a \n delimited string of mvp candidates for a given liqui url. `teams_allowed` = # of top teams to list mvp candidates for."""
    global_settings.rleb_log_info(
        "DIESEL: Creating mvp lookup for {0}".format(liquipedia_url)
    )

    response = requests.get(
        f"http://127.0.0.1:8080/mvp_candidates/{string_to_base64(liquipedia_url)}/teams_allowed/{teams_allowed}"
    )
    eligible_candidates = base64_to_string(response.content)
    return eligible_candidates
