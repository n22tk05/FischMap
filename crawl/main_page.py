import asyncio
from urllib.parse import parse_qs, urlparse

try:
    from crawl.browser import build_api_url, fetch_wiki_api_soup
    from crawl.fisch import fish_soup
except ModuleNotFoundError:
    from browser import build_api_url, fetch_wiki_api_soup
    from fisch import fish_soup

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


async def get_main_pages() -> list[str]:
    """Fetch Fisch_Wiki via MediaWiki API and return matching NAVIGATOR API URLs."""
    target_slugs = set(NAVIGATOR)
    found_urls: dict[str, None] = {}

    soup = await fetch_wiki_api_soup(MAIN_API_URL)

    for tag in soup.find_all("a", href=True):
        href = tag["href"].split("#", 1)[0].split("?", 1)[0]
        if "/wiki/" not in href:
            continue
        slug = href.rsplit("/wiki/", 1)[-1].strip("/")
        if slug in target_slugs:
            found_urls.setdefault(build_api_url(slug), None)

    return list(found_urls.keys())


async def crawl() -> None:
    """Run get_main_pages and dispatch crawling for each extracted MediaWiki API URL."""
    urls: list[str] = await get_main_pages()
    print(f"Discovered {len(urls)} main wiki API URLs")
    for url in urls:
        slug = parse_qs(urlparse(url).query).get("page", [""])[0]
        match slug:
            case "Fish":
                soup = await fetch_wiki_api_soup(url)
                fish_data = fish_soup(soup)
                print(f"Parsed {len(fish_data)} fish entries")
                if fish_data:
                    print("Sample:", fish_data[0])


if __name__ == "__main__":
    asyncio.run(crawl())
