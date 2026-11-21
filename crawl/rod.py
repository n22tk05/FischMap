import asyncio

try:
    from crawl.browser import build_api_url, fetch_wiki_api_soup
except ModuleNotFoundError:
    from browser import build_api_url, fetch_wiki_api_soup

ROD_API_URL = build_api_url("Fishing_Rods")


async def run_rod() -> None:
    """Fetch the Fishing Rods wiki page via MediaWiki API URL."""
    soup = await fetch_wiki_api_soup(ROD_API_URL)
    tables = soup.find_all("table")
    print(f"Fetched '{ROD_API_URL}' ({len(tables)} tables)")


if __name__ == "__main__":
    asyncio.run(run_rod())
