import asyncio
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import re
from crawl.browser import build_api_url, fetch_wiki_api_soup

BASE_URL = "https://fischipedia.org"
FISH_API_URL = build_api_url("Fish")



async def fish_soup(soup: BeautifulSoup, output_path: str | Path = "data/fish_urls.txt") -> list[str]:
    """Extract unique fish wiki URLs from #fish-table-main and write them to a .txt file."""
    table = soup.find("table", id="fish-table-main")
    if table is None:
        return []

    rows = table.select("tbody tr") or table.find_all("tr")[2:]
    found_urls: dict[str, None] = {}

    for row in rows:
        first_cell = row.find("td")
        if first_cell is None:
            continue
        link = first_cell.find("a", href=True)
        if link is None:
            continue
        href = str(link["href"]).strip().split("#", 1)[0]
        if not href:
            continue
        found_urls.setdefault(urljoin(BASE_URL, href), None)

    urls = list(found_urls.keys())
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    print(f"Extracted {len(urls)} fish URLs -> {out_file}")

    page_titles = [url.split('/')[-1] for  url in urls]

    result = []
    for title in page_titles: 
        api_url = build_api_url(title)
        soup = await fetch_wiki_api_soup(api_url)
        result.append(fish_detail_soup(soup))    
    return urls


def fish_detail_soup(soup:BeautifulSoup) -> list[dict]: 
    """"""
    result = []
    info = fish_info(soup.find(class_="infobox"))
    # print(info)

    return result

def fish_info(cell: Tag | None) -> dict:
    """Extract key-value metadata from a fish infobox."""
    if cell is None:
        return {}

    result: dict[str, object] = {}
    heading_el = cell.find(class_="heading")
    result["Name"] = heading_el.get_text(" ", strip=True) if heading_el else ""

    for row in cell.find_all(class_="infobox-datarow"):
        for hidden in row.select('.ext-floatingui-content, [aria-hidden="true"]'):
            hidden.decompose()

        heading_node = row.select_one(".data-heading")
        content_node = row.select_one(".data-content")
        if heading_node is None or content_node is None:
            continue

        data_title = heading_node.get_text(" ", strip=True)
        li_items = content_node.select("ul li")
        if li_items:
            result[data_title] = [li.get_text(" ", strip=True) for li in li_items]
        else:
            result[data_title] = content_node.get_text(" ", strip=True)

    print(result)
    return result


async def fetch_fish_urls(
    local_html: str | Path = "fish.html",
    output_path: str | Path = "data/fish_urls.txt",
) -> list[str]:
    """Load Fish HTML locally if present, otherwise fetch via MediaWiki API and export URLs."""
    path = Path(local_html)
    if path.is_file():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    else:
        soup = await fetch_wiki_api_soup(FISH_API_URL)
    return await fish_soup(soup, output_path=output_path)


if __name__ == "__main__":
    asyncio.run(fetch_fish_urls())
