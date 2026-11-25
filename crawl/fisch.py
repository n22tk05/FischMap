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
from to_json import to_json
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
    for idx, title in enumerate(page_titles, start=1):
        api_url = build_api_url(title)
        soup = await fetch_wiki_api_soup(api_url)
        detail = fish_detail_soup(soup)
        result.append(detail)
        print(f"Fish {idx:<4}: {detail.get('Name', title)}")
    to_json(result, "fish")
    return urls


def fish_detail_soup(soup: BeautifulSoup) -> dict:
    """Parse infobox, description, and availability from a fish detail page."""
    info = fish_info(soup.find(class_="infobox"))
    desc_el = soup.find(class_="bestiary-description-content")
    desc = desc_el.get_text(" ", strip=True) if desc_el else ""
    obt = fish_obt(soup.find(class_="fish-availability"))
    return {
        **info,
        "Description": desc,
        "Obtainment": obt,
    }


def fish_obt(cell: Tag | None) -> dict[str, object]:
    """Extract tabber obtainment methods and locations from .fish-availability."""
    if cell is None:
        return {}

    result: dict[str, object] = {}
    tabs = cell.select("header .tabber__tab")
    panels = cell.select("section .tabber__panel")

    if tabs and panels:
        panel_by_id = {p.get("id"): p for p in panels if p.get("id")}
        for idx, tab in enumerate(tabs):
            tab_name = tab.get_text(" ", strip=True)
            target_id = tab.get("aria-controls") or str(tab.get("href", "")).lstrip("#")
            panel = panel_by_id.get(target_id) or (panels[idx] if idx < len(panels) else None)
            if panel is None:
                continue
            li_items = panel.select("ul li")
            if li_items:
                result[tab_name] = [li.get_text(" ", strip=True) for li in li_items]
            else:
                result[tab_name] = panel.get_text(" ", strip=True)
        return result

    li_items = cell.select("ul li")
    if li_items:
        result["Default"] = [li.get_text(" ", strip=True) for li in li_items]
    else:
        text = cell.get_text(" ", strip=True)
        if text:
            result["Default"] = text
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

    return result

def format_fish_json(data: dict | None) -> dict:
    if data is None:
        return {}

    preferences = ["Weather", "Time", "Season", "Bait"]
    value_keys = ["XP", "C$/kg"]
    size_tiers = [
        ("Min", "Min."),
        ("Avg", "Avg."),
        ("Base", "Base"),
        ("Max", "Max."),
    ]
    size_labels = ["Tiny", "Small", "Big", "Giant"]

    data["Preferences"] = {k: data.pop(k) for k in preferences if k in data}

    value_section: dict[str, object] = {k: data.pop(k) for k in value_keys if k in data}
    value_range: dict[str, dict[str, object]] = {}
    for label, prefix in size_tiers:
        tier_data = {
            unit: data.pop(f"{prefix} {unit}")
            for unit in ("Kg", "C$")
            if f"{prefix} {unit}" in data
        }
        if tier_data:
            value_range[label] = tier_data
    if value_range:
        value_section["Value Range"] = value_range

    sizes = {k: data.pop(k) for k in size_labels if k in data}
    if sizes:
        value_section["Sizes"] = sizes

    data["Value"] = value_section
    return data


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
