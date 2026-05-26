"""HTTP request headers for outbound urllib/API calls."""

from config import PEXELS_API_KEY

USER_AGENT_VIDENERATE = "Videnerate"

# Typical Chrome-on-Windows User-Agent (servers often block bare/short agents):
#   Mozilla/5.0          — legacy compatibility token (all major browsers send it)
#   Windows NT 10.0      — OS family (Windows 10 / 11 report as NT 10.0)
#   Win64; x64           — 64-bit Windows on x64 hardware
#   AppleWebKit/537.36   — engine compatibility token (WebKit-derived stacks)
#   (KHTML, like Gecko)  — compatibility token (does not mean the browser is Gecko)
#   Chrome/122           — browser product and major version
#   Safari/537.36        — WebKit build token many sites expect alongside Chrome
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
