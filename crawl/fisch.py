import asyncio
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, Tag
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from to_html import to_html
from crawl.browser import build_api_url, fetch_wiki_api_soup

FISH_API_URL = build_api_url("Fish")


def _clean_hidden_elements(node: Tag) -> None:
    """Remove tooltip popups and hidden filter/sort spans inside a table."""
    for hidden in node.select(".ext-floatingui-content, .sortkey"):
        hidden.decompose()


def _clean_text(node: Tag, join_sep: str = " ") -> str:
    text = node.get_text(join_sep, strip=True)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if text in ("-", "—", "None") else text


def fish_soup(soup: BeautifulSoup) -> list[dict[str, object]]:
    """Parse the main fish table (with 2-row grouped headers) into clean nested dicts."""
    table = soup.find("table", id="fish-table-main")
    if table is None:
        return []
    to_html(str(table))
    _clean_hidden_elements(table)
    header_rows = table.select("thead tr")
    if len(header_rows) < 2:
        all_rows = table.find_all("tr")
        if len(all_rows) < 2:
            return []
        header_rows = all_rows[:2]
        body_rows = all_rows[2:]
    else:
        body_rows = table.select("tbody tr")
    # Map each column index -> (start_col, end_col, parent_name) from row 0
    groups: list[tuple[int, int, str]] = []
    col_idx = 0
    for th in header_rows[0].find_all("th"):
        name = _clean_text(th)
        colspan = int(th.get("colspan", 1))
        groups.append((col_idx, col_idx + colspan, name))
        col_idx += colspan
    # Map each leaf column index -> (parent_name, child_name, is_grouped) from row 1
    leaf_ths = header_rows[1].find_all("th")
    col_map: list[tuple[str, str, bool]] = []
    for idx, th in enumerate(leaf_ths):
        child_name = _clean_text(th, join_sep="")
        parent_name, is_grouped = child_name, False
        for start, end, grp_name in groups:
            if start <= idx < end:
                parent_name = grp_name
                is_grouped = (end - start) > 1
                break
        col_map.append((parent_name, child_name, is_grouped))
    result: list[dict[str, object]] = []
    for row in body_rows:
        cells = row.find_all("td")
        if not cells:
            continue
        item: dict[str, object] = {}
        for idx, cell in enumerate(cells):
            if idx >= len(col_map):
                break
            value = _clean_text(cell)
            parent_name, child_name, is_grouped = col_map[idx]
            if is_grouped:
                match child_name:
                    case "Location":
                        item.setdefault(parent_name, {})["Locations"] = locations_soup(cell)  # type: ignore[index]
                    case _:
                        item.setdefault(parent_name, {})[child_name] = value  # type: ignore[index]
            else:
                name, rarity = name_rarity_soup(cell)
                item[parent_name] = name
                item["Rarity"] = rarity
        result.append(item)

    return result


def locations_soup(cell: Tag) -> list[str]:
    """Extract formatted 'Location - Sublocation' entries from a Location cell."""
    locations: list[str] = []
    location_texts = cell.get_text(" ", strip=True)
    for text in location_texts.split(";"):
        text = text.strip()
        if not text or ":" not in text:
            continue
        locations.append(text.replace(":", " -"))
    return list(dict.fromkeys(locations))

def name_rarity_soup(cell: Tag) -> [str, str]:
    """Extract formatted Rarity"""
    name = cell.find("a").get_text(strip=True)
    rarity = cell.find("span").get_text(strip=True).split('-')[1][:-1]
    print(name, rarity)
    return name, rarity
    
    

async def fetch_fish(local_html: str | Path = "fish.html") -> list[dict[str, object]]:
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
    out_path = Path("data/fish.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fish_data, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Created {out_path}")
