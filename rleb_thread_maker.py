import discord
import requests
import traceback
from bs4 import BeautifulSoup

import rleb_stdout
import rleb_settings

THREAD_TEMPLATE = """

"""


async def generate_thread_markdown(page: str) -> str:
    return ""


async def handle_make_thread(
    thread_type: str, url: str, channel: discord.TextChannel
) -> None:
    try:
        page = None
        try:
            page = requests.get(url).content
        except Exception as e:
            await channel.send("Couldn't load {0}!\nError: {1}".format(url, e))
            rleb_settings.rleb_log_info(
                "THREAD: Couldn't load {0}!\nError: {1}".format(url, e)
            )
            rleb_settings.rleb_log_error(traceback.format_exc())
            return

        finalMarkdown = await generate_thread_markdown(page)

        await rleb_stdout.print_to_channel(channel, finalMarkdown, title="Thread")

    except Exception as e:
        await channel.send("Couldn't make thread for {0}. Error: {1}".format(url, e))
        rleb_settings.rleb_log_info(
            "THREAD: Couldn't find groups in {0}. Error: {1}".format(url, e)
        )
        rleb_settings.rleb_log_error(traceback.format_exc())
