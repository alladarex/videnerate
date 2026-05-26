from config import PEXELS_API_KEY

USER_AGENT_VIDENERATE = "Videnerate"

USER_AGENT_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122 Safari/537.36"
)

ACCEPT_LANGUAGE_EN = "en-US,en;q=0.9"

VIDENERATE_HEADERS: dict[str, str] = {"User-Agent": USER_AGENT_VIDENERATE}

BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT_BROWSER,
    "Accept-Language": ACCEPT_LANGUAGE_EN,
}


def pexels_headers() -> dict[str, str]:
    if not PEXELS_API_KEY:
        return {}
    return {**VIDENERATE_HEADERS, "Authorization": PEXELS_API_KEY}


def ddg_api_headers(referer: str) -> dict[str, str]:
    return {
        **BROWSER_HEADERS,
        "Accept": "application/json,text/javascript,*/*;q=0.1",
        "Referer": referer,
    }