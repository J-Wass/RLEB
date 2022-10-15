import discord
import requests
import base64

import rleb_settings
import rleb_stdout

async def handle_stream_lookup(url: str, channel: discord.channel.TextChannel) -> None:
    """Handle stream table lookup message.

    Args:
        channel (discord.channel.TextChannel): Channel the lookup is being used in.
        url (str): Liquipedia URL string to look for stream tables.
    """
    rleb_settings.rleb_log_info("DISCORD: Creating stream lookup for {0}".format(url))

    try:
        response = requests.get(f"http://127.0.0.1:8080/streams/{base64.b64encode(url.encode('utf-8')).decode('utf-8')}")
        markdown = base64.b64decode(response.content).decode('utf-8').strip()
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