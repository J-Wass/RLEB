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


async def handle_verified_flair_list(
    sub: praw.reddit.models.Subreddit, channel: discord.TextChannel
) -> None:
    """Creates a list of all verified users and prints to channel.

    Parameters:
        sub (praw.models.Subreddit): The subreddit to fetch user flairs for.
        channel (discord.TextChannel): The channel to print results to.
    """

    # Extend timeouts so asyncio doesn't think that is has crashed.
    global_settings.asyncio_timeout = 60 * 15

    verified_users = []
    for flair in sub.flair(limit=None):
        if (not flair) or ("flair_text" not in flair) or (not flair["flair_text"]):
            continue

        if global_settings.verified_needle in flair["flair_text"].strip().lower():
            verified_users.append(flair["user"])

    response = f"There are {len(verified_users)} verified users on the subreddit.\n"
    if len(verified_users) == 0:
        response = "No verified users found :("

    for i in range(len(verified_users)):
        response += f"{verified_users[i].name}\n"

    # Return timeout to normal.
    global_settings.asyncio_timeout = 60 * 5

    await stdout.print_to_channel(channel, response, "Verified Users")
