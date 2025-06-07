import requests
import random
import traceback
import json

import discord

import global_settings


async def create_paste(content, title=None):
    """
    Creates a pastebin/paste.ee of with the given content. Returns the link to the paste
    """

    # First try paste.ee.
    try:
        request = "https://api.paste.ee/v1/pastes"
        arguments = {
            "key": global_settings.PASTEEE_APP_KEY,
            "sections": [
                {
                    "name": ("Untitled" if title is None else title),
                    "syntax": "autodetect",
                    "contents": content,
                }
            ],
        }
        headers = {"X-Auth-Token": "token"}
        response = requests.post(request, json=arguments, headers=headers)
        if response.status_code > 300:
            raise Exception(response.text)
        return json.loads(response.text)["link"]
    # If paste.ee fails, try pastebin.
    except:
        request = "https://pastebin.com/api/api_post.php"
        arguments = {
            "api_dev_key": global_settings.PASTEBIN_API_KEY,
            "api_user_key": global_settings.PASTEBIN_API_USER_KEY,
            "api_paste_code": content,
            "api_paste_expire_date": "1W",
            "api_option": "paste",
            "api_paste_private": "0",
            "api_paste_name": ("Untitled" if title is None else title),
        }
        response = requests.post(request, data=arguments)
        if response.status_code > 300:
            raise Exception(response.text)
        return response.text


async def print_to_channel(
    channel: discord.channel.TextChannel,
    content: str,
    title: str = None,
    force_pastebin: bool = False,
    use_hook: bool = True,
) -> None:
    """Prints |content| in the discord |channel|. If |content| is long, it will write to pastebin or paste.ee.
    In dire cases, |content| will be marshalled out, line by line to discord to avoid the char limit.

    Args:
        channel (discord.channel.TextChannel): Discord channel to print a message in.
        content (str): The content of the message to be sent.
        title (str): Optional, the title to make the pastebin.
        force_pastebin (bool): Forces the stdout to occur on pastebin, instead of directly in discord.
        use_hook (bool): Whether the `content` should be printed with a catchphrase hook in the beginning.
    """
    if content is None:
        await channel.send("Something went wrong :(", embed=None)
        return
    if (
        len(content) < 250
        and global_settings.enable_direct_channel_messages
        and not force_pastebin
    ):
        message = await channel.send(content, embed=None)
        await message.edit(suppress=True)
        return

    try:
        response = await create_paste(content, title=title)
        hook = random.choice(global_settings.hooks)
        if use_hook:
            message = await channel.send("**{0}**: {1}".format(hook, response))
        else:
            message = await channel.send(response)
        await message.edit(suppress=True)  # remove those annoying embeds
    except Exception as e:

        # If something goes wrong with paste.ee or pastebin, print text directly to discord.

        global_settings.rleb_log_error(traceback.format_exc())
        global_settings.rleb_log_error(e)

        # Discord will bold text if it uses *'s. Escape the stars so they can make it all the way to reddit.
        content = content.replace("*", "\*")

        # Marshall the text out, 5 lines at a time. Discord cuts the message off at some char limit.
        formatted_text_rows = content.split("\n")
        while len(formatted_text_rows) > 5:
            formatted_text_row_message = await channel.send(
                "\n".join(formatted_text_rows[:5]), embed=None
            )
            await formatted_text_row_message.edit(
                suppress=True
            )  # remove those annoying embeds
            formatted_text_rows = formatted_text_rows[5:]
        formatted_text_message = await channel.send(
            "\n".join(formatted_text_rows), embed=None
        )
        await formatted_text_message.edit(suppress=True)  # remove those annoying embeds
