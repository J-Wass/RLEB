from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
import traceback
import json
import random

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
import discord

from rleb_liqui import rleb_liqui_utils
import rleb_settings
import rleb_stdout

# todo
# make discord command
# get markup from top_5_responses

mvp_results_template = """
# {REGION_NAME}

| | Player | Team | Vote|
|-|-|-|-|
|**MVP**|{PLAYER1}|{PLAYER1_TEAM}|{PLAYER1_PERCENT}%|
|**Runner Up**|{PLAYER2} |{PLAYER2_TEAM}|{PLAYER2_PERCENT}%|
|**3rd**|{PLAYER3} |{PLAYER3_TEAM}|{PLAYER3_PERCENT}%|
|**4th**|{PLAYER4} |{PLAYER4_TEAM}|{PLAYER4_PERCENT}%|
|**5th**|{PLAYER5} |{PLAYER5_TEAM}|{PLAYER5_PERCENT}%|
"""

mvp_markdown_template = """
# [Vote for Tournament MVPs]({FORM_LINK})

You can view the list of previous MVP polls and results [over here.](https://www.reddit.com/r/RocketLeagueEsports/search?q=selftext%3A%22MVP%22+%22Results%22+author%3ARLMatchThreads+subreddit%3ARocketLeagueEsports&sort=new&t=all)
"""

footer = "You can view the list of previous MVP polls and results [over here.](https://www.reddit.com/r/RocketLeagueEsports/search?q=selftext%3A%22MVP%22+%22Results%22+author%3ARLMatchThreads+subreddit%3ARocketLeagueEsports&sort=new&t=all)"


class MVPCandidates:
    """Encapsulation of a group of candidates for a specific mvp voting round."""

    def __init__(self, title: str, candidates: list[str]):
        self.title = title
        self.candidates = candidates

    def __repr__(self):
        return f'{self.title} -> {self.candidates}'


async def handle_mvp_form_creation(liquipedia_urls: list[str], channel) -> None:
    """Handles a request to get markdown for a new post about mvps from each liqui url."""
    candidate_groups = await _get_mvp_candidates(liquipedia_urls, channel)
    if candidate_groups is None or len(candidate_groups) == 0:
        await channel.send(f"Could't find mvp candidates from {channel}.")

    markdown = await _get_mvp_markdown(candidate_groups, channel)
    if markdown:
        await rleb_stdout.print_to_channel(
            channel, markdown, title="RLCS 21-22 | Weekend MVP Poll"
        )
    else:
        await channel.send(f"Could't find mvp candidates from {channel}.")


async def handle_mvp_results_lookup(form_url: str, channel) -> None:
    """Fetches the results of a google form for the supplied form edit url."""

    # Gather a mapping of region->form responses
    try:
        top_5_for_each_region = _get_mvp_form_responses(form_url)
    except Exception as e:
        await channel.send(f"\nCouldn't get form responses for {form_url}.")
        await channel.send(f"Full error: {str(e)}\n{traceback.format_exc()}")
        return

    # For each region, create markdown using the form responses.
    region_markdowns = []
    for region, top_5_players in top_5_for_each_region.items():
        markdown = mvp_results_template.replace("{REGION_NAME}", region)
        top_5_players.sort(key=lambda x: x[1], reverse=True)
        for i, player_tuple in enumerate(top_5_players, start=1):
            name = player_tuple[0].split("(")[0].strip()
            team = player_tuple[0].split("(")[1].split(")")[0].strip()
            markdown = (
                markdown.replace(f"{{PLAYER{i}}}", name)
                .replace(f"{{PLAYER{i}_PERCENT}}", str(round(player_tuple[1], 1)))
                .replace(f"{{PLAYER{i}_TEAM}}", team)
            )
        region_markdowns.append(markdown)
    markdown = "\n".join(region_markdowns) + "\n" + footer
    await rleb_stdout.print_to_channel(
        channel, markdown, "RLCS | Week After MVP Poll | RESULTS"
    )


async def _get_mvp_candidates(
    liquipedia_urls: list[str], channel
) -> list[MVPCandidates]:
    """Gets a list of MVPCandidates for each url in liquipedia_urls."""
    candidate_groups = []
    for url in liquipedia_urls:
        candidates = await _get_single_mvp_candidate_group(url, channel)
        if candidates:
            candidate_groups.append(candidates)
    return candidate_groups


async def _get_single_mvp_candidate_group(
    liquipedia_url: str, channel, teams_allowed: int = 4
) -> Optional[MVPCandidates]:
    """Gets an MVPCandidate group from the liquipedia_url."""
    page = None
    try:
        page = rleb_liqui_utils.get_page_html_from_url(liquipedia_url)
    except Exception as e:
        await channel.send("Couldn't load {0}!\nError: {1}".format(liquipedia_url, e))
        rleb_settings.rleb_log_info(
            "MVP: Couldn't load {0}!\nError: {1}".format(liquipedia_url, e)
        )
        rleb_settings.rleb_log_error(traceback.format_exc())
        return None

    html = BeautifulSoup(page, "html.parser")

    mvp_candidates = {}

    teams_boxes = html.select("div[class^=teamcard-columns]")
    for teams_box in teams_boxes:
        teams = teams_box.select("div.template-box")

        # Create mapping of team_name to player name.
        for team in teams:
            team_name = team.select("center > a")[0].text
            player_tables = team.select("div.teamcard-inner > table")
            for player_table in player_tables:
                players = player_table.select("td")
                candidates = []
                for i, player in enumerate(players):
                    player_name = player.text.strip()

                    # Filter out bad liqui data
                    bad_rows = ["DNP", "Ranking", "Substitutes", "Main Roster"]
                    if any(bad_row in player_name for bad_row in bad_rows):
                        continue
                    if player_name == "":
                        continue

                    candidates.append(f"{player_name} ({team_name})")
                if team_name not in mvp_candidates:
                    mvp_candidates[team_name] = []
                mvp_candidates[team_name].extend(candidates)

    # Get all players on top teams.
    eligible_candidates = []
    prizepool = html.select("table.prizepooltable:not(.collapsed)")
    
    # Liqui can render the prizepool as a div or table lol.
    if not prizepool or len(prizepool) == 0:
        prizepool = html.select("div.general-collapsible.prizepooltable")
        rows = prizepool[0].select("span.name")
    else:
        rows = prizepool[0].select("span[class^='team-template-team']")

    for i in range(min(teams_allowed, len(rows))):
        team_name = rows[i].text.strip()
        if team_name == "TBD" or  team_name == "":
            continue
        eligible_candidates = eligible_candidates + mvp_candidates[team_name]

    title = " | ".join(liquipedia_url.split("/")[4:]).replace("_", " ")
    return MVPCandidates(title, eligible_candidates)


async def _get_mvp_markdown(candidate_groups: list[MVPCandidates], channel):
    """Creates a new google form for the candidate groups, and returns reddit markdown for it."""
    form_link = await _create_mvp_form(candidate_groups, channel)
    return mvp_markdown_template.replace("{FORM_LINK}", form_link)


async def _create_mvp_form(
    candidate_groups: list[MVPCandidates], channel
) -> Optional[str]:
    """Creates a google form, with one page for each group of mvp candidates."""
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.metadata",
    ]
    credential_info = json.loads(rleb_settings.GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credential_info, scopes=SCOPES
    )
    try:
        form_data = _create_form(candidate_groups, credentials)
    except:
        await channel.send(f"Couldn't build google form, are all the liquipedia pages formatted correctly?")
        return None
    if form_data is None:
        return None
    if not "responderUri" in form_data or not "formId" in form_data:
        return None
    _add_permissions_to_formid(form_data["formId"], credentials)

    edit_msg = await channel.send(
        f"Edit the form here: https://docs.google.com/forms/d/{form_data['formId']}/edit",
        embed=None,
    )
    await edit_msg.edit(suppress=True)
    return form_data["responderUri"]


def _get_mvp_form_responses(form_link: str) -> Dict[str, List[Tuple[str, float]]]:
    """
    Returns a mapping of region_name to list of mvp winners.
    MVP winners are represented as a Tuple[player_name, percent_won].
    """

    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.metadata",
    ]
    credential_info = json.loads(rleb_settings.GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credential_info, scopes=SCOPES
    )

    # ex form link = https://docs.google.com/forms/d/ABC123ABC123ABC123/edit
    form_id = form_link.split("docs.google.com/forms/d/")[1].split("/")[0]
    service = build("forms", "v1", credentials=credentials)

    # Mapping of Region -> list of tuple (name, percent)
    # ex) 'APAC N' -> [('Maxeew (Gaimin Gladiators)', 33.3), ('LCT (Gaimin Gladiators)', 26.7), ('Abscrazy (Gaimin Gladiators)', 8.9)]
    return_dict = {}

    # Mapping of question_id to name.
    question_names = {}
    result = service.forms().get(formId=form_id).execute()
    for item in result["items"]:
        question_id = item["questionItem"]["question"]["questionId"]
        question_name = item["title"]
        question_names[question_id] = question_name

    # Mapping of question_id to list of answers
    question_bucket = {}
    result = service.forms().responses().list(formId=form_id).execute()
    responses = result["responses"]
    for r in responses:
        if not "answers" in r:
            continue
        for question_id, answers in r["answers"].items():
            # If question_id hasn't been seen, add a bucket.
            if question_id not in question_bucket:
                question_bucket[question_id] = []

            answer = answers["textAnswers"]["answers"][0]["value"]
            question_bucket[question_id].append(answer)

    # Get top 5 for each question.
    for question_id, answers in question_bucket.items():
        top_5_frequency = Counter(answers).most_common(5)
        number_of_answers = len(answers)
        top_5_percent = list(
            map(lambda x: (x[0], 100 * x[1] / number_of_answers, 1), top_5_frequency)
        )

        question_name = question_names[question_id]
        return_dict[question_name] = top_5_percent

    return return_dict


def _create_form(candidate_groups: list[MVPCandidates], credentials: str) -> any:
    """Creates a google form and returns the result."""
    service = build("forms", "v1", credentials=credentials)
    form = {
        "info": {
            "title": "RLCS MVP Voting",
        },
    }
    result = service.forms().create(body=form).execute()
    form_id = result["formId"]

    # Build a question for each candidate group as a form update.
    groups = candidate_groups.copy()
    for candidate_group in groups:
        options = []

        # Each candidate is an option in the question.
        candidates = candidate_group.candidates.copy()
        for candidate in candidates:
            options.append({"value": candidate})
        question_update = {
            "requests": [
                {
                    "createItem": {
                        "item": {
                            "title": "[OPTIONAL] " + candidate_group.title,
                            "questionItem": {
                                "question": {
                                    "required": False,
                                    "choiceQuestion": {
                                        "type": "RADIO",
                                        "options": options,
                                        "shuffle": True,
                                    },
                                }
                            },
                        },
                        "location": {"index": 0},
                    }
                }
            ]
        }
        service.forms().batchUpdate(formId=form_id, body=question_update).execute()
    return result


def _add_permissions_to_formid(form_id, google_credentials):
    """Adds write permissions to all mods for the form."""
    # Add all questions.
    service = build("drive", "v3", credentials=google_credentials)

    batch = service.new_batch_http_request()
    for email in rleb_settings.moderator_emails:
        permission = {"type": "user", "role": "writer", "emailAddress": email}
        batch.add(
            service.permissions().create(
                fileId=form_id,
                body=permission,
                fields="id",
                sendNotificationEmail=False,
            )
        )

    batch.execute()
