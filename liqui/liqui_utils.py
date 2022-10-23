import base64
import requests
import json
import random

headers = {"User-Agent": "r/RocketLeagueEsports Thread Tools"}


def _get_page_id_from_url(liquipedia_url: str) -> str:
    """Accepts a liquipedia_url and returns a mediawiki api pageid."""
    liquipedia_url = (
        liquipedia_url.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
    )
    liquipedia_page_title = liquipedia_url.split("liquipedia.net/rocketleague/")[1]

    request = f"https://liquipedia.net/rocketleague/api.php?action=query&format=json&titles={liquipedia_page_title}"
    response = requests.get(request, headers=headers)
    # Uncomment to generate the response text for testing.
    # with open("new_id.txt", "w") as f:
    #     f.write(response.text)
    if response.status_code >= 300:
        raise Exception(response.text)
    response_json = json.loads(response.text)

    pages = response_json["query"]["pages"]
    if len(pages) != 1:
        raise Exception(
            f"Found {len(pages)} pages with name {liquipedia_page_title}! Excepted only 1."
        )

    # Just pull out the only key, which is the pageid.
    return random.choice(list(pages.keys()))


def _get_content_api_url_from_liqui_url(liquipedia_url: str) -> str:
    pageid = _get_page_id_from_url(liquipedia_url)
    return f"https://liquipedia.net/rocketleague/api.php?action=parse&format=json&pageid={pageid}"


def get_page_html_from_url(liquipedia_url: str) -> str:
    """Accepts a liquipedia_url and returns the html for that page."""
    request = _get_content_api_url_from_liqui_url(liquipedia_url)
    response = requests.get(request, headers=headers)
    # Uncomment to generate the response text for testing.
    # with open("new_content.txt", "w") as f:
    #     f.write(response.text)
    if response.status_code >= 300:
        raise Exception(response.text)
    response_json = json.loads(response.text)

    content = response_json["parse"]["text"]["*"]
    if content == None or len(content) == 0:
        raise Exception(f"Couldn't parse {liquipedia_url}.")

    return content


def string_to_base64(in_string: str) -> str:
    return base64.b64encode(in_string.encode("utf-8")).decode("utf-8")


def base64_to_string(in_string: str) -> str:
    return base64.b64decode(in_string).decode("utf-8").strip()
