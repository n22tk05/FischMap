import asyncio
import http.cookiejar
import json
import os
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from bs4 import BeautifulSoup

API_URL = "https://fischipedia.org/w/api.php"
USER_AGENT = "FischMap/1.0 (https://github.com/n22tk05/FischMap)"
COOKIE_FILE = Path(__file__).resolve().parent.parent / "data" / "cookies.txt"

_COOKIE_JAR = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
if COOKIE_FILE.is_file():
    try:
        _COOKIE_JAR.load(ignore_discard=True, ignore_expires=True)
    except Exception:
        pass

_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_COOKIE_JAR))


def _save_cookies() -> None:
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COOKIE_JAR.save(ignore_discard=True, ignore_expires=True)


def build_api_url(page_title: str, api_url: str = API_URL) -> str:
    """Build the MediaWiki Action API parse URL for a given page title."""
    params = urlencode({
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
    })
    return f"{api_url}?{params}"


def _fetch_wiki_api_sync(
    target: str,
    api_url: str,
    timeout: int,
    cookie: str | None,
) -> BeautifulSoup:
    url = target if target.startswith(("http://", "https://")) else build_api_url(target, api_url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    cookie_header = cookie or os.environ.get("FISCHIPEDIA_COOKIE")
    if cookie_header:
        headers["Cookie"] = cookie_header

    req = urllib.request.Request(url, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        _save_cookies()
    except HTTPError as exc:
        print(f"HTTP {exc.code} when fetching '{url}'.")
        return BeautifulSoup("", "html.parser")
    except URLError as exc:
        print(f"Network error when fetching '{url}': {exc.reason}")
        return BeautifulSoup("", "html.parser")

    html = payload.get("parse", {}).get("text", {}).get("*", "")
    return BeautifulSoup(html, "html.parser")


async def fetch_wiki_api_soup(
    target: str,
    api_url: str = API_URL,
    timeout: int = 30,
    cookie: str | None = None,
) -> BeautifulSoup:
    """Fetch rendered page HTML from a MediaWiki API URL or page title."""
    return await asyncio.to_thread(_fetch_wiki_api_sync, target, api_url, timeout, cookie)
