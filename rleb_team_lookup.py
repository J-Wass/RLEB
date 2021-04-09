from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import time
import traceback
import math

import rleb_settings
import rleb_stdout


async def handle_team_lookup(url, channel, discord_user):
    """Handle team lookup message.

        Args:
            channel (discord.Channel): Channel the lookup is being used in.
            url (str): Liquipedia URL string to look for teams.
            discord_user (discord.User): User requesting lookup.
        """
    # Variable to keep track of how many seconds the lookup took.
    seconds = 0

    # Webdriver setup
    start = time.time()
    rleb_settings.rleb_log_info("DISCORD: Creating lookup for {0}".format(url))
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')

    driver = None
    try:
        try:
            chromedriver_file = "./chromedriver" if rleb_settings.RUNNING_ENVIRONMENT == "linux" else "./chromedriver.exe"
            driver = webdriver.Chrome(chromedriver_file,
                                      chrome_options=chrome_options)
        except WebDriverException as e:
            await channel.send("Chrome can't start!")
            rleb_settings.rleb_log_info(
                "LOOKUP: Chrome can't start! Error: {0}".format(e))
            rleb_settings.rleb_log_error(traceback.format_exc())
            return

        try:
            driver.get(url)
            time.sleep(2)  # wait a few seconds for the page to load
        except WebDriverException as e:
            await channel.send("Couldn't load {0}. Error: {1}".format(url, e))
            rleb_settings.rleb_log_info(
                "LOOKUP: Couldn't load {0}. Error: {1}".format(url, e))
            rleb_settings.rleb_log_error(traceback.format_exc())

        # Super hacky js solution.
        driver.execute_script("""
                // Iterate all teams in participants table.
                var table_rows = [];
                document.querySelectorAll(`div.teamcard`).forEach((team) => {
                  console.log(team)
                  const team_name = team.querySelector(`b a`) ? team.querySelector(`b a`).text : "TBD";
                  const team_link = team.querySelector(`b a`) ? team.querySelector(`b a`).href : "#";
                  var players = [];

                  // Iterate the first 3 players in the players' table.
                  var player_list = [...team.querySelectorAll(`.teamcard-inner .list td > a`)]
                  player_list.slice(0,3).forEach((player) =>{
                    players.push(player.text.replaceAll('_', '-'));
                  });

                  players = players.length == 3 ? players : ['?', '?', '?'];

                  table_rows.push(`|[**${team_name}**](${team_link}) \- ${players[0]}, ${players[1]}, ${players[2]}|`);
                });

                // Use ".SEP." as a seperator to later break into newlines in python. Yes this is dumb and hacky.
                const header = `|Team|\n.SEP.|:--:|\n.SEP.`;
                const full_text = header + table_rows.join(`\n.SEP.`);
                const new_div = document.createElement(`div`);
                new_div.innerHTML = full_text;
                new_div.id = `team_table`;
                document.body.append(new_div);
                console.log(full_text)
            """)

        # IMPORTANT: The above script puts the table markdown into div#team_table.
        # Split table markdown by the separate .SEP. and join it with newlines.
        teams = driver.find_element_by_id("team_table").text.replace(
            ".SEP.", "\n")
        await rleb_stdout.print_to_channel(channel, teams, title="Teams")

    except Exception as e:
        await channel.send("Couldn't find teams in {0}. Error: {1}".format(
            url, e))
        rleb_settings.rleb_log_info(
            "LOOKUP: Couldn't find teams in {0}. Error: {1}".format(url, e))
        rleb_settings.rleb_log_error(traceback.format_exc())

    finally:
        driver.quit()
        seconds = int(time.time() - start)
        return seconds
