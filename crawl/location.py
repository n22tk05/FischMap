import asyncio
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from to_json import to_json
from crawl.browser import build_api_url, fetch_wiki_api_soup

BASE_URL = "https://fischipedia.org"
LOCATION_API_URL = build_api_url("Locations")

def has_class(el: Tag, target_class: str) -> bool:
    classes = el.get("class") or []
    return target_class in classes


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

def _normalize_image_url(src: str | None) -> str:
    if not src:
        return ""
    if src.startswith("//"):
        return f"https:{src}"
    return urljoin(BASE_URL, src)


def get_elements_between_headings(heading: Tag) -> dict:
    """Collect all sibling Tag elements after `heading` until the next mw-heading3/mw-heading2."""
    result: dict = {}
    for sibling in heading.find_next_siblings():
        if not isinstance(sibling, Tag):
            continue
        if (
            has_class(sibling, "mw-heading3")
            or has_class(sibling, "mw-heading2")
            or sibling.name in ("h2", "h3")
        ):
            break
        if sibling.name == "style":
            continue
        if not sibling.get("class"):
            match sibling.name:
                case "figure":
                    a_el = sibling.find("a", href=True)
                    cap_el = sibling.find("figcaption")
                    fig_path = urljoin(BASE_URL, a_el["href"]) if a_el else ""
                    fig_name = cap_el.get_text(" ", strip=True) if cap_el else ""
                    if fig_path or fig_name:
                        result.setdefault("Image", []).append({
                            "Name": fig_name,
                            "Path": fig_path,
                        })
                case "p":
                    text = sibling.get_text(" ", strip=True)
                    if text:
                        result.setdefault("Description", []).append(text)
        else:
            if has_class(sibling, "content-table-wrapper"):
                table = table_handle(sibling.find(class_="content-table"))
                if table:
                    result.setdefault("Tables", []).append(table)

    return result

def table_handle(table: Tag | None) -> dict:
    """Parse HTML table with rowspan/colspan support in tbody."""
    if table is None:
        return {}

    caption_el = table.find("caption")
    name = caption_el.get_text(" ", strip=True) if caption_el else ""
    headings: list[dict] = []
    body_content: list[dict[str, str]] = []

    def parse_span(el: Tag, default: int = 1) -> dict[str, int]:
        def to_int(val: object) -> int:
            try:
                num = int(str(val).strip())
                return num if num > 1 else default
            except (ValueError, TypeError):
                return default

        return {
            "colspan": to_int(el.get("colspan")),
            "rowspan": to_int(el.get("rowspan")),
        }

    header_els = table.find_all(attrs={"role": "columnheader"}) or table.select("thead tr:last-child th")
    for heading in header_els:
        headings.append({
            "heading": heading.get_text(" ", strip=True),
            "span": parse_span(heading),
        })

    col_names = [h["heading"] for h in headings]

    body = table.find("tbody") or table
    pending: dict[int, tuple[str, int]] = {}  # col_idx -> (value, remaining_rows)

    for row in body.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        row_values: dict[int, str] = {}
        col_idx = 0

        def fill_pending(idx: int) -> int:
            while idx in pending:
                val, rem = pending[idx]
                row_values[idx] = val
                if rem > 1:
                    pending[idx] = (val, rem - 1)
                else:
                    del pending[idx]
                idx += 1
            return idx

        for cell in cells:
            col_idx = fill_pending(col_idx)
            val = cell.get_text(" ", strip=True)
            span = parse_span(cell)

            for offset in range(span["colspan"]):
                target_col = col_idx + offset
                row_values[target_col] = val
                if span["rowspan"] > 1:
                    pending[target_col] = (val, span["rowspan"] - 1)

            col_idx += span["colspan"]

        fill_pending(col_idx)

        item = {
            (col_names[i] if i < len(col_names) else f"col_{i}"): row_values[i]
            for i in sorted(row_values)
        }
        body_content.append(item)

    return {
        "name": name,
        "headings": headings,
        "rows": body_content,
    }

def location_detail_soup(soup: BeautifulSoup) -> dict[str, object]:
    """Parse infobox and mw-heading3 sections from a location detail page."""
    info = location_info(soup.find(class_="infobox"))
    sublocation = sublocation_info(soup.find(class_="mw-parser-output"))
    return {
        "Name": info.get("Heading", ""),
        "Info": info,
        "Sublocations": sublocation,
    }


def sublocation_info(cell: Tag | None) -> list[dict[str, object]]:
    """Extract all sibling tags grouped under each div.mw-heading3 section."""
    if cell is None:
        return []

    sections: list[dict[str, object]] = []
    for heading in cell.select("div.mw-heading3"):
        for edit_span in heading.select(".mw-editsection"):
            edit_span.decompose()
        title_el = heading.find("h3") or heading
        title = title_el.get_text(" ", strip=True)

        elements = get_elements_between_headings(heading)
        sections.append({
            "Name": title,
            **elements,
        })

    return sections


def location_info(cell: Tag | None) -> dict[str, object]:
    if cell is None:
        return {}
    result: dict[str, object] = {}
    heading_el = cell.find(class_="heading")
    result["Heading"] = heading_el.get_text(" ", strip=True) if heading_el else ""
    img_link = cell.find("a", href=True)
    result["Image"] = urljoin(BASE_URL, img_link["href"]) if img_link else ""

    information: dict[str, str] = {}
    for row in cell.find_all(class_="infobox-datarow"):
        title_el = row.find("p")
        content_el = row.find(class_="data-content")
        if title_el is None or content_el is None:
            continue
        information[title_el.get_text(" ", strip=True)] = content_el.get_text(" ", strip=True)
    result["Information"] = information
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
        detail = location_detail_soup(soup)
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
    return await location_soup(soup, output_path=output_path)


async def fetch_location_by_url(target_url: str) -> dict[str, object]:
    """Fetch and parse a single location detail page directly via fetch_wiki_api_soup."""
    soup = await fetch_wiki_api_soup(target_url)
    detail = location_detail_soup(soup)
    # to_json(detail, slug)
    return detail


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else input("Nhập URL/tên trang Location (Enter để chạy toàn bộ): ").strip()
    if target:
        detail = asyncio.run(fetch_location_by_url(target))
        print("Parsed:", detail.get("Name", target), "| Sublocations:", len(detail.get("Sublocations", [])))
    else:
        urls = asyncio.run(fetch_locations())
        if urls:
            print("Sample:", urls[:5])
