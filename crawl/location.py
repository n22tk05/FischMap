import asyncio
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from to_json import to_json
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crawl.browser import build_api_url, fetch_wiki_api_soup

BASE_URL = "https://fischipedia.org"
LOCATION_API_URL = build_api_url("Locations")


def _parse_gallery(gallery: Tag) -> list[str]:
    """Extract unique location wiki URLs from a MediaWiki <ul class='gallery'> element."""
    found_urls: dict[str, None] = {}

    for li in gallery.select("li.gallerybox"):
        link = li.find("a", href=True)
        if link is None:
            continue
        href = str(link["href"]).strip().split("#", 1)[0]
        if not href:
            continue
        found_urls.setdefault(urljoin(BASE_URL, href), None)

    return list(found_urls.keys())

def location_detail_soup(soup: BeautifulSoup):
    """"""
    info = location_info(soup.find(class_="infobox"))

def sublocation_info(cell: Tag) -> dict:
    """"""
    headings = cell.find_all(class_="mw-heading3")
    


def location_info(cell: Tag) -> dict:
    if cell is None:
        return {}
    result: dict = {}
    result["Heading"] = cell.find(class_="heaing").get_text(strip=True)
    result["Image"] = cell.find('a').get("href")
    info_rows = cell.find_all(class_="infobox-datarow")
    for row in info_rows:
        title = row.find("p").get_text(strip=True)
        content = row.find(class_="data-content").get_text(strip=True)
        result["Infomation"][title] = content
    return result

async def location_soup(
    soup: BeautifulSoup,
    output_path: str | Path = "data/locations_url.txt",
) -> list[str]:
    """Extract unique main and sublocation URLs and write them to a .txt file."""
    galleries = soup.select("ul.gallery")
    if not galleries:
        return []

    found_urls: dict[str, None] = {}
    for url in _parse_gallery(galleries[0]):
        found_urls.setdefault(url, None)
    if len(galleries) > 1:
        for url in _parse_gallery(galleries[1]):
            found_urls.setdefault(url, None)

    urls = list(found_urls.keys())
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    print(f"Extracted {len(urls)} location URLs -> {out_file}")

    page_title = [url.split('/')[-1] for url in urls]

    result = []
    for idx, title in enumerate(page_title, start=1):
        api_url = build_api_url(title)
        soup = await fetch_wiki_api_soup(api_url)
        detail = await location_detail_soup(soup)
        result.append(detail)
        print(f"Location {idx:<4}: {detail.get('Name', title)}")
    to_json(result, "Location")
    return urls


async def fetch_locations(
    local_html: str | Path = "locations.html",
    output_path: str | Path = "data/locations_url.txt",
) -> list[str]:
    """Load locations HTML from a local file if present, otherwise fetch via MediaWiki API."""
    path = Path(local_html)
    if path.is_file():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    else:
        soup = await fetch_wiki_api_soup(LOCATION_API_URL)
    return location_soup(soup, output_path=output_path)


if __name__ == "__main__":
    urls = asyncio.run(fetch_locations())
    if urls:
        print("Sample:", urls[:5])
