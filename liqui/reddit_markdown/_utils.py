LIQUI_BASE = "https://liquipedia.net/rocketleague"


def url_to_page_name(liquipedia_url: str) -> str:
    """Extract the Liquipedia page name from a full URL."""
    url = (
        liquipedia_url.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
    )
    return url.split("liquipedia.net/rocketleague/")[1]


def liqui_link(page_name: str) -> str:
    escaped = page_name.replace("(", r"\(").replace(")", r"\)")
    return f"{LIQUI_BASE}/{escaped}"


def format_money(amount) -> str:
    try:
        n = int(amount)
    except (TypeError, ValueError):
        return "TBD"
    return f"${n:,}" if n > 0 else "TBD"


def ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def opponent_name(opp: dict) -> str:
    return opp.get("name") or opp.get("template") or "TBD"
