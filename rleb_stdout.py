import requests
import traceback

import rleb_settings

async def create_paste(content, title=None):
    """Creates a pastebin of with the given content."""

    #TODO - add api login token so we can make posts from rlesportsbot account

    request = "https://pastebin.com/api/api_post.php"
    arguments = {
        'api_dev_key': rleb_settings.PASTEBIN_API_KEY,
        'api_paste_code': content,
        'api_paste_expire_date' : '10M',
        'api_option': 'paste',
        'api_paste_private': '0',
        'api_paste_name': ('Untitled' if title is None else title)
    }

    response = requests.post(request, data = arguments)
    if response.status_code > 300:
         raise Exception(response.text)
    return response.text

async def print_to_channel(channel, content, title=None):
    """Prints either a pastebin link, or the raw text to the passed channel."""
    try:
        response = await create_paste(content, title)
        message = await channel.send(response)
        await message.edit(suppress=True) # remove those annoying embeds
    except Exception as e:
        rleb_settings.rleb_log_error(traceback.format_exc())
        rleb_settings.rleb_log_error(e)
        await channel.send("Couldn't connect to pastebin, printing out text here instead.")

        # Discord will bold text if it uses *'s. Escape the stars so they can make it all the way to reddit.
        content = content.replace("*", "\*")

        # Marshall the text out
        formatted_text_rows = content.split("\n")
        while len(formatted_text_rows) > 5:
            formatted_text_row_message = await channel.send("\n".join(formatted_text_rows[:5]))
            await formatted_text_row_message.edit(suppress=True) # remove those annoying embeds
            formatted_text_rows = formatted_text_rows[5:]
        formatted_text_message = await channel.send("\n".join(formatted_text_rows), embed=None)
        await formatted_text_message.edit(suppress=True) # remove those annoying embeds
        