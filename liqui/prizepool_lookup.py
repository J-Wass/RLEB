import traceback


from bs4 import BeautifulSoup

from liqui import diesel, liqui_utils
from stdout import print_to_channel
import global_settings


async def handle_prizepool_lookup(liquipedia_url: str, channel: str) -> str:
    """Gets prizepool markdown from a liquipedia tournament page."""

    global_settings.rleb_log_info(
        "Prizepool: Creating prizepool lookup for {0}".format(liquipedia_url)
    )

    # Attempt to load markdown from Diesel.
    await channel.send("Building prizepool table from Diesel...")
    markdown = await diesel.get_prizepool_markdown(liquipedia_url)
    if markdown:
       await print_to_channel(channel, markdown, title="Prizepool")
       return

    # If Diesel fails, fallback to RLEB, python parsing.
    await channel.send("Failed to build bracket table from Diesel. Trying RLEB...")

    page = None
    try:
        page = liqui_utils.get_page_html_from_url(liquipedia_url)
    except Exception as e:
        await channel.send("Couldn't load {0}!\nError: {1}".format(liquipedia_url, e))
        global_settings.rleb_log_info(
            "MVP: Couldn't load {0}!\nError: {1}".format(liquipedia_url, e)
        )
        global_settings.rleb_log_error(traceback.format_exc())

    html = BeautifulSoup(page, "html.parser")

    # Get all rows of prizepool table, ignore the first row which contains table headers.
    try:
        team_rows = html.select("div.prizepooltable")[0].select(
            ".csstable-widget-row:not(:first-child)"
        )
    except:
        team_rows = html.select("table.prizepooltable")[0].select(
            "tr:not(:first-child)"
        )

    markdown = "|**Place**|**Prize**|**Team**|**RLCS Points**|\n|:-|:-|:-|:-|"

    # This part is actually a bit complex because liqui uses tricky CSS to create two 3rd-4th places in tourneys where there is no difference between 3rd and 4th place.
    # In tourneys where 3rd and 4th place are equivalent, we need to keep track of the prize & point total from 3rd place because it's missing from 4th place.
    team_place = None
    prize = None
    new_points = None
    # Iterate the first 8 from the prizepool.
    for i in range(min(9, len(team_rows))):
        team_data = team_rows[i].select(".csstable-widget-cell")
        # Partially down the prizepool, there's a row "expand" that just houses a toggle for the UI,
        if team_data[0].get(
            "class"
        ) == "prizepooltabletoggle" or "general-collapsible-expand-button" in team_data[
            0
        ].get(
            "class"
        ):
            continue
        team_name = None
        if len(team_data) == 4:
            # If this is a complete row, write down the new prize and points.
            team_place = team_data[0].text.replace(" ", "").strip()
            prize = team_data[1].text.strip()
            new_points = team_data[2].text.strip()
            team_name = team_data[3].text.strip()
        else:
            # If this is a followup row, use prize and points from previous row.
            team_name = team_data[0].text.strip()
        markdown += (
            f"\n|**{team_place}** | {prize} | {team_name} | +{new_points} **()** |"
        )

    await print_to_channel(channel, markdown)
