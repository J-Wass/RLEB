import global_settings
import praw
import discord
import stdout


async def handle_flair_census(
    sub: praw.reddit.models.Subreddit,
    amount: int,
    channel: discord.TextChannel,
    divider=",",
) -> None:
    """Takes a census of all user flairs and prints to channel.

    Parameters:
        sub (praw.models.Subreddit): The subreddit to fetch user flairs for.
        amount (int): The top x flairs you want to see.
        channel (discord.TextChannel): The channel to print results to.
        divider (str): Optional, divider to put between each flair and their count in the output.
    """

    # Extend timeouts so asyncio doesn't think that is has crashed.
    global_settings.asyncio_timeout = 60 * 15

    all_flairs = {}
    for flair in sub.flair(limit=None):
        if flair["flair_text"] != None:
            tokens = flair["flair_text"].split()
            for token in tokens:
                if token not in all_flairs:
                    all_flairs[token] = 1
                else:
                    all_flairs[token] += 1
    sorted_census = sorted(all_flairs.items(), key=lambda x: x[1])
    sorted_census.reverse()
    amount = min(amount, len(sorted_census))
    response = ""
    for i in range(amount):
        census_item = sorted_census[i]
        response += "{0}{1} {2}\n".format(
            census_item[0].replace(":", ""), divider, census_item[1]
        )

    # Return timeout to normal.
    global_settings.asyncio_timeout = 60 * 5

    await stdout.print_to_channel(channel, response, "Census")
