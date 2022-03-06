async def handle_flair_census(sub, amount, channel, divider=","):
    """Takes a census of all user flairs and prints to |channel|.

    Parameters:
        sub (praw.models.Subreddit): The subreddit to fetch user flairs for.
        amount (int): The top x flairs you want to see.
        channel (discord.TextChannel): The channel to print results to.
        divider (str): Optional, divider to put between each flair and their count in the output.
    """
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
    await channel.send(response)
