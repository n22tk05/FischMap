import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from crawl.browser import build_api_url, fetch_wiki_api_soup

BASE_URL = "https://fischipedia.org"
LOCATION_API_URL = build_api_url("Locations")


def _normalize_image_url(src: str | None) -> str:
    if not src:
        return ""
    if src.startswith("//"):
        return f"https:{src}"
    return urljoin(BASE_URL, src)


def _parse_gallery(gallery: Tag, location_type: str) -> list[dict[str, str]]:
    """Parse a single MediaWiki <ul class='gallery'> element into location dicts."""
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for li in gallery.select("li.gallerybox"):
        a = li.find("a", href=True)
        img = li.find("img")
        gallery_text = li.select_one(".gallerytext")

        href = a["href"] if a else ""
        link = urljoin(BASE_URL, href) if href else ""

        name = ""
        if a and a.get("title"):
            name = str(a["title"]).strip()
        elif gallery_text:
            name = gallery_text.get_text(" ", strip=True)
        elif img and img.get("alt"):
            name = str(img["alt"]).strip()

        img_src = _normalize_image_url(img.get("src") if img else None)

        if not name and not link:
            continue
        key = (name, link)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "Name": name,
            "Type": location_type,
            "Link": link,
            "Image": img_src,
        })

    return items


def main_location_soup(gallery: Tag) -> list[dict[str, str]]:
    """Extract formatted main locations from the first gallery."""
    return _parse_gallery(gallery, "Main")


def sub_location_soup(gallery: Tag) -> list[dict[str, str]]:
    """Extract formatted sublocations from the second gallery."""
    return _parse_gallery(gallery, "Sublocation")


def location_soup(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Parse main and sub-location galleries into a combined list of dicts."""
    galleries = soup.select("ul.gallery")
    if not galleries:
        return []

    result = main_location_soup(galleries[0])
    if len(galleries) > 1:
        result.extend(sub_location_soup(galleries[1]))
    return result


async def fetch_locations(local_html: str | Path = "locations.html") -> list[dict[str, str]]:
    """Load locations HTML from a local file if present, otherwise fetch via MediaWiki API."""
    path = Path(local_html)
    if path.is_file():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    else:
        soup = await fetch_wiki_api_soup(LOCATION_API_URL)
    return location_soup(soup)


if __name__ == "__main__":
    locations_data = asyncio.run(fetch_locations())
    print(f"Parsed {len(locations_data)} location entries")
    out_path = Path("data/locations.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(locations_data, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Created {out_path}")
    if locations_data:
        print(json.dumps(locations_data[0], ensure_ascii=False, indent=2))
