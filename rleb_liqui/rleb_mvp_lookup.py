from typing import Optional
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

mvp_markdown_template = """
# [Vote for MVPs]({FORM_LINK})

You can view the list of previous MVP polls and results [over here.](https://www.reddit.com/r/RocketLeagueEsports/search/?q="Weekend MVP Poll" "RESULTS")
"""

class MVPCandidates:
    """ Encapsulation of a group of candidates for a specific mvp voting round. """
    def __init__(self,title: str, candidates: list[str]):
        self.title = title
        self.candidates = candidates

async def handle_mvp_lookup(liquipedia_urls: list[str] , channel) -> None:
    """Handles a request to get markdown for a new post about mvps from each liqui url."""
    candidate_groups = await _get_mvp_candidates(liquipedia_urls, channel)
    if candidate_groups is None or len(candidate_groups) == 0:
        await channel.send(f"Could't find mvp candidates from {channel}.")
    
    markdown = await _get_mvp_markdown(candidate_groups, channel)
    if markdown:
        await rleb_stdout.print_to_channel(channel, markdown, title="RLCS 21-22 | Weekend MVP Poll")
    else:
        await channel.send(f"Could't find mvp candidates from {channel}.")

async def _get_mvp_candidates(liquipedia_urls: list[str] , channel) -> list[MVPCandidates]:
    """Gets a list of MVPCandidates for each url in liquipedia_urls."""
    candidate_groups = []
    for url in liquipedia_urls:
        candidates = await _get_single_mvp_candidate_group(url, channel)
        if candidates:
            candidate_groups.append(candidates)
    return candidate_groups

async def _get_single_mvp_candidate_group(liquipedia_url: str , channel) -> Optional[MVPCandidates]:
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

    teams_allowed = 4

    teams_box = html.select("div[class^=teamcard-columns]")[0]
    teams = teams_box.select("div.template-box")

    # Create mapping of team_name to player name.
    mvp_candidates = {}
    for team in teams:
        team_name = team.select("center > a")[0].text
        player_table = team.select("div.teamcard-inner > table")[0]
        players = player_table.select("td")
        candidates = []
        for i in range(3):
            player_name = players[i].text.strip()
            candidates.append(f'{player_name} ({team_name})')
        mvp_candidates[team_name] = candidates

    # Get all players on top teams.
    eligible_candidates = []
    prizepool = html.select("table.prizepooltable")[0]
    rows = prizepool.select("span[class^='team-template-team']")
    for i in range(min(teams_allowed, len(rows))):
        team_name = rows[i].text.strip()
        eligible_candidates = eligible_candidates + mvp_candidates[team_name]

    title = " | ".join(liquipedia_url.split("/")[4:]).replace("_", " ")
    return MVPCandidates(title, eligible_candidates)

async def _get_mvp_markdown(candidate_groups: list[MVPCandidates], channel):
    """Creates a new google form for the candidate groups, and returns reddit markdown for it."""
    form_link = await _create_mvp_form(candidate_groups, channel)
    return mvp_markdown_template.replace("{FORM_LINK}", form_link)

async def _create_mvp_form(candidate_groups: list[MVPCandidates], channel) -> Optional[str]:
    """Creates a google form, with one page for each group of mvp candidates."""
    SCOPES = ["https://www.googleapis.com/auth/drive","https://www.googleapis.com/auth/drive.metadata"]
    credential_info = json.loads(rleb_settings.GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        credential_info, scopes=SCOPES
    )
    form_data = _create_form(candidate_groups, credentials)
    if form_data is None:
        return None
    if not "responderUri" in form_data or not "formId" in form_data:
        return None
    _add_permissions_to_formid(form_data["formId"], credentials)

    edit_msg = await channel.send(f"Edit the form here: https://docs.google.com/forms/d/{form_data['formId']}/edit", embed=None)
    await edit_msg.edit(suppress=True)
    return form_data["responderUri"]
    

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
    random.shuffle(groups)
    for candidate_group in groups:
        options = []

        # Each candidate is an option in the question.
        candidates = candidate_group.candidates.copy()
        for candidate in candidates:
            options.append({"value": candidate})
        question_update = {
            "requests": [{
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
                                }
                            }
                        }
                    },
                    "location": {
                        "index": 0
                    }
                }
            }
            ]
        }
        service.forms().batchUpdate(formId=form_id, body=question_update).execute()
    return result


def _add_permissions_to_formid(form_id, google_credentials):
    """Adds write permissions to all mods for the form."""
    # Add all questions.
    service = build('drive', 'v3', credentials=google_credentials)

    batch = service.new_batch_http_request()
    for email in rleb_settings.moderator_emails:
        permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': email
        }
        batch.add(service.permissions().create(fileId=form_id,body=permission,fields='id',sendNotificationEmail=False))

    batch.execute()
