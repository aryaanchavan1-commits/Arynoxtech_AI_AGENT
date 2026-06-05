# MIT License
#
# Copyright (c) 2026 Aryan Chavan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
ArynoxTech AI Agent - Web Search Tool
======================================
Tool for searching the web using Google and extracting content
with intelligent filtering using LLM to return only high-quality, relevant results.
"""

import asyncio
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from tools.base_tool import BaseTool, ToolResult
from config.settings import TOOL_CONFIG


class WebSearchTool(BaseTool):
    """
    Tool for web search and content extraction.
    - Searches Google for real-time information
    - Extracts and cleans content from web pages
    - Uses LLM to filter and summarize results for high-quality answers
    - Returns only relevant, filtered information
    """

    name: str = "web_search_tool"
    description: str = "Search the web for real-time information, news, and knowledge. Provides filtered, high-quality results."
    version: str = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.config = TOOL_CONFIG.get("web_search", {})
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self._llm = None  # Lazily initialized

    @property
    def llm(self):
        """Lazy import LLM client for content filtering."""
        if self._llm is None:
            try:
                from utils.llm_factory import get_llm_client
                self._llm = get_llm_client()
            except Exception:
                self._llm = None
        return self._llm

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute web search operation.

        Args:
            action: 'search' (default), 'get_page_content', 'search_and_summarize'
            query: Search query string
            num_results: Number of results to return (default: 5)
            summarize: Whether to summarize the results using LLM (default: True)

        Returns:
            ToolResult with search results and filtered content
        """
        start_time = time.time()
        action = kwargs.get("action", "search_and_summarize")

        try:
            if action == "search":
                return await self._search_web(kwargs, start_time)
            elif action == "get_page_content":
                return await self._get_page_content(kwargs, start_time)
            elif action == "search_and_summarize":
                return await self._search_and_summarize(kwargs, start_time)
            else:
                return ToolResult.failure(
                    f"Unknown action: {action}",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            self.logger.exception(f"Web search tool error: {e}")
            return ToolResult.error_result(
                f"Web search failed: {str(e)}",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _search_web(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Search Google and return raw results."""
        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", 5)

        if not query:
            return ToolResult.failure(
                "No search query provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            results = await self._google_search(query, num_results)
            elapsed = (time.time() - start_time) * 1000

            return ToolResult.success(
                f"Found {len(results)} results for: {query}",
                data={
                    "query": query,
                    "results": results,
                    "result_count": len(results),
                },
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Search failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _search_and_summarize(self, kwargs: Dict, start_time: float) -> ToolResult:
        """
        Search the web, extract content from top results, and use LLM
        to provide a filtered, high-quality summary answer.
        """
        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", 5)
        summarize = kwargs.get("summarize", True)

        if not query:
            return ToolResult.failure(
                "No search query provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Step 1: Search Google
            search_results = await self._google_search(query, num_results)

            if not search_results:
                elapsed = (time.time() - start_time) * 1000
                return ToolResult.success(
                    f"No search results found for: {query}",
                    data={"query": query, "results": [], "summary": "No results found."},
                    execution_time_ms=elapsed,
                )

            # Step 2: Extract content from top results
            extracted_contents = []
            for result in search_results[:3]:  # Extract top 3 results
                try:
                    content = await self._extract_page_content(result["url"], max_chars=3000)
                    if content:
                        extracted_contents.append({
                            "title": result["title"],
                            "url": result["url"],
                            "snippet": result.get("snippet", ""),
                            "content": content[:2000],
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to extract {result['url']}: {e}")

            # Step 3: Use LLM to filter and summarize
            if summarize and extracted_contents:
                summary = await self._filter_and_summarize(query, extracted_contents)
            else:
                # Build a text summary from snippets
                summary_lines = [f"Results for: {query}\n"]
                for r in search_results:
                    summary_lines.append(f"• {r['title']}: {r.get('snippet', 'No description')}")
                    summary_lines.append(f"  URL: {r['url']}\n")
                summary = "\n".join(summary_lines)

            elapsed = (time.time() - start_time) * 1000

            return ToolResult.success(
                summary,
                data={
                    "query": query,
                    "results": search_results,
                    "extracted_contents": extracted_contents,
                    "summary": summary,
                    "result_count": len(search_results),
                },
                execution_time_ms=elapsed,
            )

        except Exception as e:
            self.logger.exception(f"Search and summarize failed: {e}")
            return ToolResult.error_result(
                f"Web search failed: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _google_search(self, query: str, num_results: int = 5) -> List[Dict]:
        """Perform a Google search and return structured results."""
        try:
            encoded_query = quote_plus(query)
            url = f"https://www.google.com/search?q={encoded_query}&num={num_results}&hl=en"

            response = await asyncio.to_thread(
                self.session.get, url, timeout=15
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Try multiple selectors for Google results
            # Modern Google uses div.g for results
            search_divs = soup.select("div.g")
            
            if not search_divs:
                # Try alternative selectors
                search_divs = soup.select("div[data-hveid]")
            
            if not search_divs:
                # Fallback: find all result-like divs
                search_divs = soup.find_all("div", class_=lambda c: c and "g" in c.split())

            for div in search_divs[:num_results]:
                title_elem = div.select_one("h3")
                link_elem = div.select_one("a")
                snippet_elem = div.select_one("div[data-sncf], span.aCOpRe, div.VwiC3b")

                if title_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    link = link_elem.get("href", "")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    # Clean Google redirect URLs
                    if link.startswith("/url?q="):
                        link = link.split("/url?q=")[1].split("&")[0]
                    elif link.startswith("/"):
                        link = f"https://www.google.com{link}"

                    # Decode URL encoding
                    from urllib.parse import unquote
                    link = unquote(link)

                    if title and link and "google.com" not in link:
                        results.append({
                            "title": title,
                            "url": link,
                            "snippet": snippet,
                        })

            return results

        except requests.RequestException as e:
            self.logger.error(f"Google search request failed: {e}")
            raise RuntimeError(f"Web search failed: {e}")
        except Exception as e:
            self.logger.error(f"Google search parsing failed: {e}")
            return []

    async def _get_page_content(self, kwargs: Dict, start_time: float) -> ToolResult:
        """Extract clean text content from a URL."""
        url = kwargs.get("url", "")
        max_chars = kwargs.get("max_chars", 5000)

        if not url:
            return ToolResult.failure(
                "No URL provided",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            content = await self._extract_page_content(url, max_chars)
            elapsed = (time.time() - start_time) * 1000

            return ToolResult.success(
                f"Extracted {len(content)} chars from {url}",
                data={"url": url, "content": content, "length": len(content)},
                execution_time_ms=elapsed,
            )
        except Exception as e:
            return ToolResult.error_result(
                f"Failed to extract page content: {e}", error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _extract_page_content(self, url: str, max_chars: int = 5000) -> str:
        """Fetch and extract clean readable text from a web page."""
        try:
            response = await asyncio.to_thread(
                self.session.get, url, timeout=15
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", 
                           "iframe", "noscript", "form", "button", "svg", "meta"]):
                tag.decompose()

            # Remove hidden elements
            for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
                tag.decompose()

            # Try to get main content first
            main_content = (
                soup.find("article") or 
                soup.find("main") or 
                soup.find("div", class_=lambda c: c and any(
                    x in (c or "").lower() for x in ["content", "article", "post", "main"]
                )) or
                soup.find("body")
            )

            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # Clean up the text
            lines = []
            for line in text.split("\n"):
                line = line.strip()
                # Skip very short or meaningless lines
                if len(line) < 20 or line.startswith(("http", "©", "Cookie", "Subscribe", "Share")):
                    continue
                lines.append(line)

            cleaned = "\n".join(lines)
            
            # Remove duplicate lines
            seen = set()
            unique_lines = []
            for line in cleaned.split("\n"):
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)
            
            cleaned = "\n".join(unique_lines)

            # Truncate to max_chars, but try to break at sentence boundary
            if len(cleaned) > max_chars:
                cleaned = cleaned[:max_chars]
                last_period = cleaned.rfind(".")
                if last_period > max_chars * 0.7:  # Only truncate at sentence if reasonable
                    cleaned = cleaned[:last_period + 1]

            return cleaned.strip()

        except Exception as e:
            self.logger.warning(f"Content extraction failed for {url}: {e}")
            return ""

    async def _filter_and_summarize(self, query: str, contents: List[Dict]) -> str:
        """
        Use LLM to filter, combine, and summarize web search results
        into a high-quality, concise answer.
        """
        try:
            # Build a prompt for the LLM to filter and summarize
            context_parts = []
            for i, item in enumerate(contents, 1):
                context_parts.append(
                    f"--- Source {i}: {item['title']} ---\n"
                    f"URL: {item['url']}\n"
                    f"Content:\n{item['content'][:1500]}\n"
                )

            context = "\n".join(context_parts)

            filter_prompt = (
                f"You are a knowledgeable research assistant. Based on the web search results below, "
                f"provide a comprehensive, accurate, and well-structured answer to the query: '{query}'\n\n"
                f"RULES:\n"
                f"1. Only use information from the provided search results - do not invent facts\n"
                f"2. Filter out irrelevant or low-quality information\n"
                f"3. Organize the answer in a clear, readable format with bullet points or sections\n"
                f"4. If the information is insufficient, clearly state what is known and what is uncertain\n"
                f"5. Include relevant source attributions where possible\n"
                f"6. Keep the answer concise but thorough\n"
                f"7. Remove any promotional, biased, or spammy content\n\n"
                f"Search Results:\n{context}\n\n"
                f"Filtered Answer:"
            )

            response = await self.llm.generate_async(
                prompt=filter_prompt,
                conversation_context="",
                temperature=0.3,  # Low temperature for factual accuracy
                max_tokens=1024,
            )

            return response.strip()

        except Exception as e:
            self.logger.error(f"LLM filtering failed: {e}")
            # Fallback: return raw snippet summary
            fallback = [f"• {c['title']}: {c.get('snippet', '')}" for c in contents]
            return "Summary generation unavailable. Raw results:\n" + "\n".join(fallback)

    def cleanup(self) -> None:
        """Close the HTTP session."""
        try:
            self.session.close()
        except Exception:
            pass