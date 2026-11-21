import asyncio
from pathlib import Path
from bs4 import BeautifulSoup

try:
    from crawl.browser import build_api_url, fetch_wiki_api_soup
except ModuleNotFoundError:
    from browser import build_api_url, fetch_wiki_api_soup

FISH_API_URL = build_api_url("Fish")


def fish_soup(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Parse the main fish table from the Fish wiki page."""
    table = soup.find("table", id="fish-table-main")
    if table is None:
        return []

    header_rows = table.select("thead tr")
    if not header_rows:
        return []

    headers = [th.get_text(strip=True) for th in header_rows[-1].find_all("th")]
    data: list[dict[str, str]] = []

    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        values = [
            text if (text := td.get_text(" ", strip=True)) not in ("-", "—", "None") else ""
            for td in cells
        ]
        data.append(dict(zip(headers, values)))

    return data


async def fetch_fish(local_html: str | Path = "fish.html") -> list[dict[str, str]]:
    """Load fish HTML from a local file if present, otherwise fetch via MediaWiki API URL."""
    path = Path(local_html)
    if path.is_file():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    else:
        soup = await fetch_wiki_api_soup(FISH_API_URL)
    return fish_soup(soup)


if __name__ == "__main__":
    fish_data = asyncio.run(fetch_fish())
    print(f"Parsed {len(fish_data)} fish entries")
    if fish_data:
        print("Sample:", fish_data[0])
