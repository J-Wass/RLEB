from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import time
import traceback
import math

import rleb_settings
import rleb_stdout

async def handle_group_lookup(url, channel, discord_user):
        """Handle group lookup message.

        Args:
            channel (discord.Channel): Channel the lookup is being used in.
            url (str): Liquipedia URL string to look for groups.
            discord_user (discord.User): User requesting lookup.
        """
        # Variable to keep track of how many seconds the lookup took.
        seconds = 0

        # Webdriver setup
        start = time.time()
        rleb_settings.rleb_log_info("DISCORD: Creating group lookup for {0}".format(url))
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')

        driver = None
        try:
            try:
                chromedriver_file = "./chromedriver" if rleb_settings.RUNNING_ENVIRONMENT == "linux" else "./chromedriver.exe"
                driver = webdriver.Chrome(chromedriver_file, chrome_options = chrome_options)
            except WebDriverException as e:
                await channel.send("Chrome can't start!")
                rleb_settings.rleb_log_info("LOOKUP: Chrome can't start! Error: {0}".format(e))
                rleb_settings.rleb_log_error(traceback.format_exc())
                return

            try:
                driver.get(url)
                time.sleep(2) # wait a few seconds for the page to load
            except WebDriverException as e:
                await channel.send("Couldn't load {0}. Error: {1}".format(url, e))
                rleb_settings.rleb_log_info("LOOKUP: Couldn't load {0}. Error: {1}".format(url, e))
                rleb_settings.rleb_log_error(traceback.format_exc())

            # Super hacky js solution.
            JS = """
// Iterate all teams in participants table.
GROUP_TEMPLATE_HEADER = `||||||.SEP.|:-|:-|:-|:-|:-|.SEP.|**#**|**{GROUP_NAME}** .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. .NBSP. |**W-L** |**W-L**|**GD** .NBSP. |`

GROUP_TEMPLATE_ROW = `|{PLACEMENT}|[**{NAME}**]({LINK})|{MATCH_RECORD}|{GAME_RECORD}|{PLUS_MINUS}|`

class Team {
    constructor(teamName, teamLink, matchRecord, gameRecord, plusMinus) {
        this.teamName = teamName;
        this.teamLink = teamLink;
        this.matchRecord = matchRecord;
        this.gameRecord = gameRecord;
        this.plusMinus = plusMinus;
    }
}

class Group {
    constructor(groupName, teams) {
        this.groupName = groupName;
        this.teams = teams;
    }
}

// Holds all groups in the liquipedia page.
groups = [];

// Iterate each table.
tables = document.querySelectorAll("table.grouptable");
tables.forEach((t) => {
    groupName = t.querySelectorAll("tr:nth-child(1) th")[0].innerText;

    // Hold all of the teams for the group object.
    teams = [];

    // Iterate each row.
    rows = t.querySelectorAll("tr:nth-child(n+2)");
    rows.forEach((r) => {
        name = r.querySelectorAll("td")[0].innerText.trim();
        link = r.querySelectorAll("td")[0].querySelectorAll(".team-template-text a")[0].href
        matchRecord = r.querySelectorAll("td")[1].innerText;
        gameRecord = r.querySelectorAll("td")[2].innerText;
        plusMinus = r.querySelectorAll("td")[3].innerText;

        newTeam = new Team(name, link, matchRecord, gameRecord, plusMinus);
        teams.push(newTeam)
    });

    newGroup = new Group(groupName, teams)
    groups.push(newGroup);
});

finalMarkdown = '';
groups.forEach((g) => {
    groupMarkdown = GROUP_TEMPLATE_HEADER
    groupMarkdown = groupMarkdown.replace("{GROUP_NAME}", g.groupName || 'Group');
    placement = 1;
    g.teams.forEach((t) => {
        row = GROUP_TEMPLATE_ROW;
        row = row.replace("{PLACEMENT}", placement);
        row = row.replace("{NAME}", t.teamName);
        row = row.replace("{LINK}", t.teamLink);
        row = row.replace("{MATCH_RECORD}", t.matchRecord);
        row = row.replace("{GAME_RECORD}", t.gameRecord);
        row = row.replace("{PLUS_MINUS}", t.plusMinus);
        groupMarkdown += ".SEP. &#x200B; .SEP." + row
        placement++;
    });

    finalMarkdown += ".SEP..SEP." + groupMarkdown
});

console.log(finalMarkdown);

const new_div = document.createElement(`div`);
new_div.innerHTML = finalMarkdown;
new_div.id = `groups_table`;
document.body.append(new_div);
            """
            driver.execute_script(JS)

            # IMPORTANT: The above script puts the table markdown into div#groups_table.
            group_tables = "\n".join(driver.find_element_by_id("groups_table").text.split(".SEP."))
            group_tables = group_tables.replace(".NBSP.", "&nbsp;")
            await rleb_stdout.print_to_channel(channel, group_tables, title="Groups")

        except Exception as e:
            await channel.send("Couldn't find groups in {0}. Error: {1}".format(url, e))
            rleb_settings.rleb_log_info("LOOKUP: Couldn't find groups in {0}. Error: {1}".format(url, e))
            rleb_settings.rleb_log_error(traceback.format_exc())

        finally:
            driver.quit()
            seconds = int(time.time() - start)
            return seconds
