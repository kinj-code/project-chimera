"""WebBrowserManager — web search using DuckDuckGo HTML scraping.

Provides web search capability for the LLM to answer questions about
current events, recent information, or topics beyond its knowledge cutoff.

Author: Project Chimera Engineering Team
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup

from loguru import logger

if TYPE_CHECKING:
    pass


class WebBrowserManager:
    """Manages web search via DuckDuckGo HTML scraping.

    Provides a search_web() method that fetches results from DuckDuckGo
    HTML interface and extracts text snippets from top results.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    DDG_HTML_URL = "https://html.duckduckgo.com/html/"

    def __init__(self) -> None:
        self._session: requests.Session | None = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the HTTP session."""
        if self._session is not None:
            return
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._initialized = True
        logger.info("WebBrowserManager initialized")

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("WebBrowserManager not initialized. Call initialize() first.")

    async def search_web(self, query: str, max_results: int = 3) -> str:
        """Search the web and return formatted results.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.

        Returns:
            Formatted string with search results, or error message.
        """
        if not query or not query.strip():
            return ""

        logger.info(f"Web search: '{query}'")

        # Ensure initialized
        if not self._initialized:
            await self.initialize()

        # DuckDuckGo HTML endpoint
        params = {"q": query, "kl": "us-en"}
        url = self.DDG_HTML_URL + "?" + urllib.parse.urlencode(params)

        try:
            # Run the HTTP request in a thread
            html = await self._fetch_html(url)
            if not html:
                return "[SEARCH FAILED: Empty response]"

            results = self._parse_results(html, max_results)
            if not results:
                return "[SEARCH] No results found."

            # Format results
            formatted = "WEB SEARCH RESULTS:\n"
            for i, result in enumerate(results, 1):
                formatted += f"{i}. {result['title']}\n"
                formatted += f"   URL: {result['url']}\n"
                formatted += f"   Snippet: {result['snippet']}\n\n"

            logger.info(f"Web search returned {len(results)} results")
            return formatted.strip()

        except Exception as exc:
            logger.error(f"Web search failed: {exc}")
            return f"[SEARCH ERROR: {exc}]"

    async def _fetch_html(self, url: str) -> str | None:
        """Fetch HTML content from URL in a background thread."""
        self._ensure_session()
        try:
            response = self._session.get(
                url,
                timeout=15,
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            logger.error(f"Failed to fetch {url}: {exc}")
            return None

    def _ensure_session(self) -> None:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }

    def _parse_results(self, html: str, max_results: int) -> list[dict[str, str]]:
        """Parse DuckDuckGo HTML results."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[dict[str, str]] = []

        # Find result containers
        result_divs = soup.find_all("a", class_="result__snippet")

        count = 0
        for div in soup.find_all("a", class_="result__snippet"):
            if count >= 10:
                break
            # Find the parent result container
            parent = div.find_parent("div", class_="result")
            if not parent:
                continue
            title_elem = parent.find("a", class_="result__url")
            title = title_elem.get_text(strip=True) if title_elem else ""
            url_elem = parent.find("a", class_="result__url")
            url = url_elem.get("href", "") if url_elem else ""
            snippet_elem = div
            snippet = snippet_elem.get_text(strip=True)[:300]

            if snippet:
                results.append({
                    "title": title or "Result",
                    "url": url,
                    "snippet": snippet,
                })
                if len(results) >= 3:
                    break

        return results[:3]

    def _ensure_session(self) -> None:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }

    def search_web(self, query: str, max_results: int = 3) -> str:
        """Synchronous wrapper for search_web (for thread use)."""
        import requests
        import urllib.parse
        from bs4 import BeautifulSoup

        if not query.strip():
            return ""

        logger.info(f"Web search: '{query}'")

        params = {"q": query, "kl": "us-en", "kp": "-1"}
        url = self.DDG_HTML_URL + "?" + urllib.parse.urlencode(params)

        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Chimera/0.2)"}
            response = requests.get(
                self.DDG_HTML_URL,
                params={"q": query, "kl": "us-en"},
                timeout=15,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            results = []
            # DuckDuckGo result structure
            for result in soup.find_all("a", class_="result__snippet"):
                parent = result.find_parent("div", class_="result")
                if not parent:
                    continue
                title_elem = parent.find("a", class_="result__url")
                title = title_elem.get_text(strip=True) if title_elem else ""
                snippet = result.get_text(strip=True)[:300]
                if snippet:
                    results.append({
                        "title": title or "Result",
                        "snippet": snippet,
                    })
                    if len(results) >= 3:
                        break

            if not results:
                return "[SEARCH] No results found."

            formatted = "WEB SEARCH RESULTS:\n"
            for i, r in enumerate(results[:3], 1):
                formatted += f"{i}. {r['title']}\n   {r['snippet']}\n\n"
            return formatted.strip()

        except Exception as exc:
            logger.error(f"Web search failed: {exc}")
            return f"[SEARCH ERROR: {exc}]"