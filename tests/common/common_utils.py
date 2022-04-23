# Utilities that tests classes may need to share.


class MockRequest:
    """Mock request class for stubbing requests.get()."""

    def __init__(self, content: str, status_code: int = 200):
        self.text = content
        self.status_code = status_code


def page_id_query_from_url(liqui_url: str) -> str:
    """Takes a liquipedia url and returns an api query to get the url's id."""
    liquipedia_url = (
        liqui_url.replace("https://", "").replace("http://", "").replace("www.", "")
    )
    liquipedia_page_title = liquipedia_url.split("liquipedia.net/rocketleague/")[1]

    request = f"https://liquipedia.net/rocketleague/api.php?action=query&format=json&titles={liquipedia_page_title}"
    return request


def page_content_from_id(liqui_id: str) -> str:
    """Takes a liquipedia page id and returns an api query to get the page's content."""

    request = f"https://liquipedia.net/rocketleague/api.php?action=parse&format=json&pageid={liqui_id}"
    return request


def mock_response(response_path: str) -> str:
    """Takes the name of a file in resources and returns its full path."""
    return f"tests/resources/{response_path}"

# List of urls that need to be proxied to local files for testing.
common_proxies = {
    # Pastebin
    "https://api.paste.ee/v1/pastes" :  mock_response("paste.ee_response.json"),

    # Page ID lookups.
    page_id_query_from_url(
        "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Spring/North_America/1/Closed_Qualifier"
    ): mock_response("liqui_api_mock_responses/swiss_incomplete_page_id.txt"),
    page_id_query_from_url(
        "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Fall/Sub-Saharan_Africa/1"
    ): mock_response("liqui_api_mock_responses/swiss_missing_teams_page_id.txt"),
    page_id_query_from_url(
        "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Fall/North_America/2"
    ): mock_response("liqui_api_mock_responses/swiss_complete_page_id.txt"),
    page_id_query_from_url(
        "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/Season_X/Spring/Oceania"
    ): mock_response("liqui_api_mock_responses/groups_page_id.txt"),
    page_id_query_from_url(
        "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/Season_X/Spring/North_America/The_Grid/Open_Qualifier"
    ): mock_response("liqui_api_mock_responses/teams_double_elim_page_id.txt"),
    page_id_query_from_url(
        "https://liquipedia.net/rocketleague/Rocket_League_Championship_Series/2021-22/Winter"
    ): mock_response("liqui_api_mock_responses/bracket_page_id.txt"),

    # Page content reads.
    page_content_from_id("113385"): mock_response(
        "liqui_api_mock_responses/swiss_incomplete_page_content.txt"
    ),
    page_content_from_id("113139"): mock_response(
        "liqui_api_mock_responses/swiss_missing_teams_page_content.txt"
    ),
    page_content_from_id("113124"): mock_response(
        "liqui_api_mock_responses/swiss_complete_page_content.txt"
    ),
    page_content_from_id("104174"): mock_response(
        "liqui_api_mock_responses/groups_page_content.txt"
    ),
    page_content_from_id("104165"): mock_response(
        "liqui_api_mock_responses/teams_double_elim_page_content.txt"
    ),
    page_content_from_id("113085"): mock_response(
        "liqui_api_mock_responses/bracket_page_content.txt"
    ),
}
