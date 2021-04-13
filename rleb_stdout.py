import requests
import random
import traceback

import rleb_settings


async def create_paste(content, title=None):
    """Creates a pastebin of with the given content."""

    request = "https://pastebin.com/api/api_post.php"
    arguments = {
        'api_dev_key': rleb_settings.PASTEBIN_API_KEY,
        'api_user_key': rleb_settings.PASTEBIN_API_USER_KEY,
        'api_paste_code': content,
        'api_paste_expire_date': '1W',
        'api_option': 'paste',
        'api_paste_private': '0',
        'api_paste_name': ('Untitled' if title is None else title)
    }
    response = requests.post(request, data=arguments)
    if response.status_code > 300:
        raise Exception(response.text)
    return response.text


async def print_to_channel(channel, content, title=None):
    """Prints a pastebin link with the |content| in the discord |channel|. 
       If the pastebin fails to load, the content will be printed directly in the channel.
    
       Args:
           channel (discord.channel.TextChannel): Discord channel to print a message in.
           content (str): The content of the message to be sent.
           title (str): Optional, the title to make the pastebin.
    """
    try:
        response = await create_paste(content, title=title)
        hook = random.choice(rleb_settings.hooks)
        message = await channel.send("**{0}**: {1}".format(hook, response))
        await message.edit(suppress=True)  # remove those annoying embeds
    except Exception as e:
        rleb_settings.rleb_log_error(traceback.format_exc())
        rleb_settings.rleb_log_error(e)

        # Discord will bold text if it uses *'s. Escape the stars so they can make it all the way to reddit.
        content = content.replace("*", "\*")

        # Marshall the text out, 5 lines at a time. Discord cuts the message off at some char limit.
        formatted_text_rows = content.split("\n")
        while len(formatted_text_rows) > 5:
            formatted_text_row_message = await channel.send("\n".join(
                formatted_text_rows[:5]),
                                                            embed=None)
            await formatted_text_row_message.edit(
                suppress=True)  # remove those annoying embeds
            formatted_text_rows = formatted_text_rows[5:]
        formatted_text_message = await channel.send(
            "\n".join(formatted_text_rows), embed=None)
        await formatted_text_message.edit(suppress=True
                                          )  # remove those annoying embeds
