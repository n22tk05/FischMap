import asyncio
import inspect
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crawl.browser import build_api_url, fetch_wiki_api_soup
from crawl.fisch import fish_soup
from crawl.location import location_soup
from to_json import to_json

BASE_URL = "https://fischipedia.org"
MAIN_API_URL = build_api_url("Fisch_Wiki")
NAVIGATOR = [
    "Fish",
    "Fishing_Rods",
    "Bait",
    "Guide",
    "Mutations",
    "Spears",
    "Harpoon_Guns",
    "Locations",
    "Boats",
    "Events",
    "Weather",
    "NPCs",
    "Shop",
    "Items",
    "Codes",
    "Enchanting",
    "Badges",
    "Companions",
    "Status_Effects",
    "Bobbers",
    "Titles",
    "Lanterns",
    "Skins",
    "Emotes",
]

PARSERS: dict[str, tuple[Callable[[BeautifulSoup], list[dict]], str]] = {
    "Fish": (fish_soup, "fish"),
    "Locations": (location_soup, "locations"),
}


async def get_all_urls() -> list[str]:
    """Fetch Fisch_Wiki via MediaWiki API and extract unique URLs matching NAVIGATOR."""
    target_slugs = set(NAVIGATOR)
    soup = await fetch_wiki_api_soup(MAIN_API_URL)
    found_urls: dict[str, None] = {}

    for tag in soup.find_all("a", href=True):
        href = str(tag["href"]).strip().split("#", 1)[0].split("?", 1)[0]
        if "/wiki/" not in href:
            continue
        slug = href.rsplit("/wiki/", 1)[-1].strip("/")
        if slug in target_slugs:
            full_url = urljoin(BASE_URL, f"/wiki/{slug}")
            found_urls.setdefault(full_url, None)

    return list(found_urls.keys())


async def export_urls(output_path: str | Path = "data/urls.txt") -> list[str]:
    """Fetch NAVIGATOR-filtered URLs and write them to a .txt file."""
    urls = await get_all_urls()
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    print(f"Extracted {len(urls)} NAVIGATOR URLs -> {out_file}")
    return urls


async def _process_route(url: str, semaphore: asyncio.Semaphore) -> None:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    api_url = build_api_url(slug)
    async with semaphore:
        soup = await fetch_wiki_api_soup(api_url)
    if slug in PARSERS:
        parser, out_name = PARSERS[slug]
        res = parser(soup)
        if inspect.isawaitable(res):
            await res


async def router() -> None:
    """Export NAVIGATOR URLs, build MediaWiki API URLs, and fetch/parse each page."""
    urls = await export_urls()
    semaphore = asyncio.Semaphore(4)
    await asyncio.gather(*(_process_route(url, semaphore) for url in urls))


if __name__ == "__main__":
    asyncio.run(router())
