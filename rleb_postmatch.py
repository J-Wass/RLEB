from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import time
import traceback
import math

import rleb_settings
from rleb_settings import rleb_log_info, rleb_log_error
import rleb_stdout


class Player:
    goals = 0
    saves = 0
    assists = 0
    shots = 0
    name = ""
    link = ""
    rating = 0

    def __repr__(self):
        return "{0}: goals {1}, saves {2}, assists {3}, shots {4}".format(
            self.name, self.goals, self.saves, self.assists, self.shots)


async def handle_postmatch(discord_user, matchid, channel):
    """Handle postmatch message.

    Args:
        discord_user (discord.User): User requesting thread.
        matchid (str): Octane match id.
        channel (discord.Channel): Channel that the request was made from.
    """
    # Variable to keep track of how many seconds to pmd took.
    seconds = 0

    # Webdriver setup
    start = time.time()
    rleb_log_info("DISCORD: Creating post match for {0}".format(matchid))
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    driver = None
    try:
        chrome_settings = rleb_settings.get_chrome_settings(rleb_settings.RUNNING_ENVIRONMENT)

        driver = webdriver.Chrome(chrome_settings['driver'],
                                  chrome_options=chrome_options)
    except WebDriverException as e:
        await discord_user.send("Chrome can't start!".format(matchid))
        rleb_log_error("REDDIT: Page didn't load correctly! {0}".format(e))
        rleb_log_error(traceback.format_exc())
        return
    try:
        try:
            driver.get('https://octane.gg/match/{0}#overview'.format(matchid))
            time.sleep(5)  # wait a few seconds for the page to load
        except WebDriverException as e:
            rleb_log_info("Couldn't load {0}. {1}".format(
                'https://octane.gg/match/{0}#overview'.format(matchid), e))
            raise Exception("Couldn't load {0} :(.".format(
                'https://octane.gg/match/{0}#overview'.format(matchid)))

        # Locate WebElements
        team_elements = driver.find_elements_by_css_selector(
            "section[id*=overview] div.scoreboard div.match-team-header a div")
        teams = list(map(lambda x: x.text.split(" (")[0], team_elements))
        score_elements = driver.find_elements_by_css_selector(
            "section[id*=overview] div.scoreboard div.match-team-header a div span"
        )
        scores = list(map(lambda x: x.text, score_elements))
        number_of_games = len(
            driver.find_elements_by_css_selector(
                ".tabs-component-tabs .tabs-component-tab"))
        game_scores = [['-', '-'] for x in range(7)
                       ]  #initialize game scores with empty dashes
        team1_goals = 0
        team1_assists = 0
        team1_saves = 0
        team1_shots = 0
        team2_goals = 0
        team2_assists = 0
        team2_saves = 0
        team2_shots = 0
        player_list = []
        overtimes = ['' for x in range(7)]
        # Iterate all games and build stats sheet
        for x in range(1, number_of_games):
            # Try loading octane page.
            try:
                driver.get('https://octane.gg/match/{0}#g{1}'.format(
                    matchid, x))
                time.sleep(5)  # wait a few seconds for the page to load
            except WebDriverException as e:
                rleb_log_info("Couldn't load {0}. {1}".format(
                    'https://octane.gg/match/{0}#g{1}'.format(matchid, x), e))
                raise Exception("Couldn't load {0} :(.".format(
                    'https://octane.gg/match/{0}#g{1}'.format(matchid, x)))

            # get all html elements
            current_goals = driver.find_elements_by_css_selector(
                "section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(4) td:nth-child(3)"
                .format(x))
            current_assists = driver.find_elements_by_css_selector(
                "section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(4) td:nth-child(4)"
                .format(x))
            current_saves = driver.find_elements_by_css_selector(
                "section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(4) td:nth-child(5)"
                .format(x))
            current_shots = driver.find_elements_by_css_selector(
                "section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(4) td:nth-child(6)"
                .format(x))
            players = driver.find_elements_by_css_selector(
                'section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(-n+3) td:nth-child(1) a'
                .format(x))
            goals = driver.find_elements_by_css_selector(
                'section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(-n+3) td:nth-child(3)'
                .format(x))
            assists = driver.find_elements_by_css_selector(
                'section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(-n+3) td:nth-child(4)'
                .format(x))
            saves = driver.find_elements_by_css_selector(
                'section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(-n+3) td:nth-child(5)'
                .format(x))
            shots = driver.find_elements_by_css_selector(
                'section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(-n+3) td:nth-child(6)'
                .format(x))
            ratings = driver.find_elements_by_css_selector(
                'section[id*=g{0}] div.scoreboard table.vuetable tr:nth-child(-n+3) td:nth-child(7)'
                .format(x))
            match_times = driver.find_elements_by_css_selector(
                'section[id*=g{0}]  > div.scoreboard > div.scoreboard-header > div.col-md-12:nth-child(2)'
                .format(x))
            # increment total stats
            game_scores[x - 1] = [current_goals[0].text, current_goals[1].text]
            team1_goals += int(current_goals[0].text)
            team2_goals += int(current_goals[1].text)
            team1_assists += int(current_assists[0].text)
            team2_assists += int(current_assists[1].text)
            team1_saves += int(current_saves[0].text)
            team2_saves += int(current_saves[1].text)
            team1_shots += int(current_shots[0].text)
            team2_shots += int(current_shots[1].text)

            match_time = match_times[0].get_attribute("innerText").split()[2]
            fragments = match_time.split(':')
            # minutes to seconds, plus seconds, minus 5 minutes (as seconds)
            extra_time = (int(fragments[0]) * 60 + int(fragments[1])) - 300
            if extra_time > 0:
                if extra_time % 60 < 10:
                    overtimes[x - 1] = "+{0}:0{1}".format(
                        math.floor(extra_time / 60), extra_time % 60)
                else:
                    overtimes[x - 1] = "+{0}:{1}".format(
                        math.floor(extra_time / 60), extra_time % 60)

            # Loop over all 6 players to build per-game stats
            for i in range(6):
                if players[i].text not in list(
                        map(lambda x: x.name, player_list)):
                    pl = Player()
                    pl.name = players[i].text
                    pl.link = players[i].get_attribute("href")
                    player_list.append(pl)
                pl = next(
                    filter(lambda x: x.name == players[i].text, player_list))
                pl.goals += int(goals[i].text)
                pl.assists += int(assists[i].text)
                pl.saves += int(saves[i].text)
                pl.shots += int(shots[i].text)
                pl.rating += float(ratings[i].text)

        # mark the higher score
        for gs in game_scores:
            if gs[0] > gs[1]:
                gs[0] = "{0} ✔️".format(gs[0])
            elif gs[0] < gs[1]:
                gs[1] = "{0} ✔️".format(gs[1])

        # divide rating by total games played
        for pl in player_list:
            pl.rating = round(pl.rating / (int(scores[0]) + int(scores[1])), 2)

        # Variables used in post fragment
        team1 = teams[0]
        team2 = teams[1]
        team1_score = scores[0]
        team2_score = scores[1]

        team1_g1 = game_scores[0][0]
        team1_g2 = game_scores[1][0]
        team1_g3 = game_scores[2][0]
        team1_g4 = game_scores[3][0]
        team1_g5 = game_scores[4][0]
        team1_g6 = game_scores[5][0]
        team1_g7 = game_scores[6][0]

        team2_g1 = game_scores[0][1]
        team2_g2 = game_scores[1][1]
        team2_g3 = game_scores[2][1]
        team2_g4 = game_scores[3][1]
        team2_g5 = game_scores[4][1]
        team2_g6 = game_scores[5][1]
        team2_g7 = game_scores[6][1]

        # Post Fragments

        scoreline = "## {0} ({1} - {2}) {3}\n\n".format(
            team1, team1_score, team2_score, team2)
        table_header = "|Team &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|G1 &nbsp;&nbsp;&nbsp;|G2 &nbsp;&nbsp;&nbsp;|G3 &nbsp;&nbsp;&nbsp;|G4 &nbsp;&nbsp;&nbsp;|G5 &nbsp;&nbsp;&nbsp;|G6 &nbsp;&nbsp;&nbsp;|G7 &nbsp;&nbsp;&nbsp;|\n|:-|:-|:-|:-|:-|:-|:-|:-"
        team1_row = "|**{0}**|{1}|{2}|{3}|{4}|{5}|{6}|{7}|".format(
            team1, team1_g1, team1_g2, team1_g3, team1_g4, team1_g5, team1_g6,
            team1_g7)
        team2_row = "|**{0}**|{1}|{2}|{3}|{4}|{5}|{6}|{7}|".format(
            team2, team2_g1, team2_g2, team2_g3, team2_g4, team2_g5, team2_g6,
            team2_g7)
        OT_row = "|OT:|{0}|{1}|{2}|{3}|{4}|{5}|{6}|".format(
            overtimes[0], overtimes[1], overtimes[2], overtimes[3],
            overtimes[4], overtimes[5], overtimes[6])

        team1_player_table_header = "|Player &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|Goals|Assists|Saves|Shots|Rating|\n|:-|:-|:-|:-|:-|:-|"
        team1_player1_row = "|[{0}]({5})|{1}|{2}|{3}|{4}|{6}|".format(
            player_list[0].name, player_list[0].goals, player_list[0].assists,
            player_list[0].saves, player_list[0].shots, player_list[0].link,
            player_list[0].rating)
        team1_player2_row = "|[{0}]({5})|{1}|{2}|{3}|{4}|{6}|".format(
            player_list[1].name, player_list[1].goals, player_list[1].assists,
            player_list[1].saves, player_list[1].shots, player_list[1].link,
            player_list[1].rating)
        team1_player3_row = "|[{0}]({5})|{1}|{2}|{3}|{4}|{6}|".format(
            player_list[2].name, player_list[2].goals, player_list[2].assists,
            player_list[2].saves, player_list[2].shots, player_list[2].link,
            player_list[2].rating)
        stats_team1_row = "|**{0}**|**{1}**|**{2}**|**{3}**|**{4}**||".format(
            team1, team1_goals, team1_assists, team1_saves, team1_shots)
        stats_team2_row = "|**{0}**|**{1}**|**{2}**|**{3}**|**{4}**||".format(
            team2, team2_goals, team2_assists, team2_saves, team2_shots)
        team2_player1_row = "|[{0}]({5})|{1}|{2}|{3}|{4}|{6}|".format(
            player_list[3].name, player_list[3].goals, player_list[3].assists,
            player_list[3].saves, player_list[3].shots, player_list[3].link,
            player_list[3].rating)
        team2_player2_row = "|[{0}]({5})|{1}|{2}|{3}|{4}|{6}|".format(
            player_list[4].name, player_list[4].goals, player_list[4].assists,
            player_list[4].saves, player_list[4].shots, player_list[4].link,
            player_list[4].rating)
        team2_player3_row = "|[{0}]({5})|{1}|{2}|{3}|{4}|{6}|".format(
            player_list[5].name, player_list[5].goals, player_list[5].assists,
            player_list[5].saves, player_list[5].shots, player_list[5].link,
            player_list[5].rating)

        octane_plug = "[Find detailed stats on Octane.gg](https://octane.gg/match/{0})".format(
            matchid)
        # Combine post fragments into one formatted post
        seconds = int(time.time() - start)
        rleb_log_info("REDDIT: PMD posted! (took {0} seconds)".format(seconds))
        await rleb_stdout.print_to_channel(
            channel,
            "\n{0}\n&#x200B;\n\n{1}\n{2}\n{3}\n{15}\n\n&#x200B;\n\n{4}\n{5}\n{6}\n{7}\n{8}{9}\n{10}\n{11}\n{12}\n{13}\n\n&#x200B;{14}\n"
            .format(scoreline, table_header, team1_row, team2_row,
                    team1_player_table_header, team1_player1_row,
                    team1_player2_row, team1_player3_row, stats_team1_row, "",
                    stats_team2_row, team2_player1_row, team2_player2_row,
                    team2_player3_row, octane_plug, OT_row),
            title="Post Match Thread")
    except Exception as e:
        await channel.send(
            "Couldn't load match {0}, is http://octane.gg/match/{0} ready yet?"
            .format(matchid))
        rleb_log_error("REDDIT: Page didn't load correctly! {0}".format(e))
        rleb_log_error(traceback.format_exc())
    finally:
        driver.quit()
        return seconds
