#!/usr/bin/env python3
"""Search the web for ATHENA and keep the source URLs."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from athena_common import clip, redact_secrets


USER_AGENT = "ATHENA-local/1.0 (personal research assistant)"
ALLOWED_HOSTS = {"lite.duckduckgo.com", "en.wikipedia.org"}
MAX_BODY_BYTES = 1_000_000


def decode_result_url(href: str) -> str | None:
    if not href:
        return None

    parsed = urllib.parse.urlparse(href)
    uddg = urllib.parse.parse_qs(parsed.query).get("uddg", [])
    if uddg:
        target = urllib.parse.unquote(uddg[0])
        target_parsed = urllib.parse.urlparse(target)
        if target_parsed.scheme in {"http", "https"}:
            return target
        return None

    host = (parsed.hostname or "").lower()
    if parsed.scheme in {"http", "https"} and host and "duckduckgo.com" not in host:
        return href
    return None


class DuckDuckGoLiteParser(HTMLParser):
    """Parse the simple DuckDuckGo lite results page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "a":
            url = decode_result_url(attributes.get("href", ""))
            if url:
                self._current = {"title": "", "url": url, "snippet": "", "source": "duckduckgo"}
                self._capture = "title"
                self._buffer = []
            return

        if tag == "td" and "result-snippet" in attributes.get("class", ""):
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a" and self._current is not None:
            self._current["title"] = " ".join("".join(self._buffer).split())
            self.results.append(self._current)
            self._current = None
            self._capture = None
            self._buffer = []
            return

        if self._capture == "snippet" and tag == "td":
            snippet = " ".join("".join(self._buffer).split())
            if snippet and self.results and not self.results[-1]["snippet"]:
                self.results[-1]["snippet"] = snippet
            self._capture = None
            self._buffer = []


def parse_duckduckgo_lite(html: str) -> list[dict[str, str]]:
    parser = DuckDuckGoLiteParser()
    parser.feed(html)
    parser.close()
    unique: list[dict[str, str]] = []
    seen = set()
    for result in parser.results:
        if not result["title"] or result["url"] in seen:
            continue
        seen.add(result["url"])
        unique.append(result)
    return unique


def fetch_url(url: str, data: bytes | None = None, timeout: int = 12) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise RuntimeError(f"Blocked web address: {parsed.hostname or url}")

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final = urllib.parse.urlparse(response.geturl())
            if (final.hostname or "").lower() not in ALLOWED_HOSTS:
                raise RuntimeError("Search redirect was blocked.")
            return response.read(MAX_BODY_BYTES)
    except urllib.error.HTTPError as exc:
        detail = redact_secrets(exc.read().decode("utf-8", errors="replace")[:300])
        raise RuntimeError(f"Web search returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Web search could not connect: {exc.reason}") from exc


def search_duckduckgo(query: str, limit: int = 5) -> list[dict[str, str]]:
    body = urllib.parse.urlencode({"q": query}).encode("utf-8")
    html = fetch_url("https://lite.duckduckgo.com/lite/", data=body).decode("utf-8", errors="replace")
    return parse_duckduckgo_lite(html)[:limit]


def search_wikipedia(query: str, limit: int = 3) -> list[dict[str, str]]:
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(limit),
            "format": "json",
            "utf8": "1",
        }
    )
    payload = json.loads(fetch_url(f"https://en.wikipedia.org/w/api.php?{params}").decode("utf-8", errors="replace"))
    results = []
    for item in payload.get("query", {}).get("search", []):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        snippet = re.sub(r"<[^>]+>", "", str(item.get("snippet", "")))
        snippet = " ".join(snippet.split())
        slug = urllib.parse.quote(title.replace(" ", "_"), safe="()_!'")
        results.append(
            {
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{slug}",
                "snippet": snippet,
                "source": "wikipedia",
            }
        )
    return results


def collect_web_results(query: str, limit: int = 5) -> tuple[list[dict[str, str]], list[str]]:
    results: list[dict[str, str]] = []
    notes: list[str] = []
    try:
        results.extend(search_duckduckgo(query, limit=limit))
        if not results:
            notes.append("DuckDuckGo returned no parseable results.")
    except RuntimeError as exc:
        notes.append(str(exc))

    seen = {item["url"] for item in results}
    if len(results) < limit:
        try:
            for item in search_wikipedia(query, limit=min(3, limit)):
                if item["url"] not in seen:
                    results.append(item)
                    seen.add(item["url"])
        except RuntimeError as exc:
            notes.append(str(exc))

    if not results and notes:
        raise RuntimeError(" ".join(notes))
    return results[:limit], notes


def format_web_results(results: list[dict[str, str]], notes: list[str] | None = None) -> str:
    lines = [note for note in (notes or []) if note]
    if not results:
        lines.append("No web results found.")
        return "\n".join(lines)

    for number, result in enumerate(results, start=1):
        lines.append(f"[{number}] {result['title']}")
        lines.append(result["url"])
        if result.get("snippet"):
            lines.append(clip(result["snippet"], 500))
        lines.append(f"source: {result['source']}")
        lines.append("")
    return "\n".join(lines).strip()


def search_web(query: str, limit: int = 5) -> str:
    results, notes = collect_web_results(query, limit=limit)
    return format_web_results(results, notes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the web and print sources.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    search_parser = subparsers.add_parser("search", help="Search DuckDuckGo lite and Wikipedia.")
    search_parser.add_argument("query", nargs="+")
    search_parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    try:
        print(search_web(" ".join(args.query), limit=max(1, args.limit)))
    except RuntimeError as exc:
        print(redact_secrets(str(exc)))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
