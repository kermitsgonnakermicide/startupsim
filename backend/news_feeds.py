"""Live news ingestion from verified Indian national publications + Google News
per-company feeds.

Two-stream pipeline:
  (A) General Indian business/tech RSS — catches market-wide news and cross-company stories.
  (B) Google News RSS per listed startup — fetched in round-robin cycles, guarantees
      every listed company in the simulator gets covered regardless of how niche it is.
      Each Google News result carries the real publisher name (Inc42, Moneycontrol,
      Business Standard, The Hindu, etc.) in its <source> tag, which we preserve.

All sources are public RSS endpoints. No API keys. Fail-soft on individual feed errors.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import urllib.parse
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

from data.stocks import STOCKS

logger = logging.getLogger("news_feeds")

# General-purpose Indian business / tech RSS feeds (reachability tested).
GENERAL_FEEDS: list[tuple[str, str]] = [
    ("Inc42",                "https://inc42.com/feed/"),
    ("YourStory",            "https://yourstory.com/feed"),
    ("Moneycontrol",         "https://www.moneycontrol.com/rss/MCtopnews.xml"),
    ("LiveMint Companies",   "https://www.livemint.com/rss/companies"),
    ("LiveMint Markets",     "https://www.livemint.com/rss/markets"),
    ("LiveMint Tech",        "https://www.livemint.com/rss/technology"),
    ("ET Tech",              "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"),
    ("ET Markets",           "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Hindu BusinessLine",   "https://www.thehindubusinessline.com/companies/feeder/default.rss"),
    ("The Hindu Business",   "https://www.thehindu.com/business/feeder/default.rss"),
    ("Indian Express Biz",   "https://indianexpress.com/section/business/feed/"),
    ("CNBC-TV18 Business",   "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/business.xml"),
]

GENERAL_REFRESH_INTERVAL = 300              # 5 minutes
PER_COMPANY_BATCH_SIZE = 10                 # Google News queries per cycle
PER_COMPANY_CYCLE_INTERVAL = 180            # 3 minutes per batch — full 90-company cycle ≈ 27 min
WARMUP_CONCURRENCY = 12                     # max parallel Google News fetches during startup warmup
ARTICLE_RETENTION_HOURS = 24 * 30           # 30 days
MAX_BUFFER = 5000                           # cap total articles in memory

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    "?q=%22{q}%22+India&hl=en-IN&gl=IN&ceid=IN%3Aen"
)


# ----- alias index (for filtering matched articles client-side) -----
STOP_ALIASES = {
    "care", "tech", "with", "your", "country",
    "raise", "ruby", "sun", "bounce", "freo", "yap", "jupiter", "heads",
    "bombay", "mumbai", "delhi", "bangalore", "chennai", "hyderabad",
    "kolkata", "pune", "ahmedabad", "noida", "gurgaon", "gurugram",
    "indian", "india", "bharat",
}


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _alias_set(stock: dict[str, Any]) -> set[str]:
    """Case-insensitive aliases for headline matching. Only distinctive
    multi-word / long-name brands contribute single-word aliases."""
    aliases = set()
    symbol = stock["symbol"].lower()
    name = stock["name"]
    name_lc = name.lower()
    aliases.add(name_lc)
    if len(symbol) >= 3:
        aliases.add(symbol)
    for suffix in (" Corporation", " Pvt", " Private", " Ltd", " Limited", " Inc",
                   " Technologies", " Therapeutics", " Networks", " Payments",
                   " Aerospace", " Electric", " Eduversity", " Cosmos", " Foods",
                   " Money", " Cards", " Academy", " Financial", " Games", " Teas",
                   " Company"):
        if name.endswith(suffix):
            short = name[: -len(suffix)].strip().lower()
            if len(short) >= 4:
                aliases.add(short)
    bare = re.sub(r"\s+", " ", re.sub(r"[\(\)\.]", " ", name)).strip().lower()
    if bare:
        aliases.add(bare)
    first_word = name.split()[0].lower()
    if len(first_word) >= 5 and first_word not in STOP_ALIASES and len(name.split()) >= 2:
        aliases.add(first_word)
    return {a for a in aliases if len(a) >= 3 and a not in STOP_ALIASES}


ALIAS_INDEX: dict[str, set[str]] = {s["symbol"]: _alias_set(s) for s in STOCKS}


def _compile_patterns(aliases: set[str]) -> list[re.Pattern]:
    return [re.compile(r"\b" + re.escape(a) + r"\b", re.IGNORECASE) for a in aliases]


COMPILED_PATTERNS: dict[str, list[re.Pattern]] = {
    sym: _compile_patterns(aliases) for sym, aliases in ALIAS_INDEX.items()
}


def _google_news_url(company_name: str) -> str:
    q = urllib.parse.quote(company_name)
    return GOOGLE_NEWS_RSS.format(q=q)


def _parse_pub_date(entry) -> datetime:
    for k in ("published_parsed", "updated_parsed"):
        v = entry.get(k)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _extract_source(entry) -> str:
    src = entry.get("source")
    if isinstance(src, dict):
        return src.get("title") or src.get("href") or "Unknown"
    if hasattr(src, "get"):
        return src.get("title") or "Unknown"
    if hasattr(src, "title"):
        return src.title or "Unknown"
    return "Unknown"


class NewsFeedAggregator:
    def __init__(self):
        self.articles: deque[dict[str, Any]] = deque(maxlen=MAX_BUFFER)
        self._seen_links: set[str] = set()
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._last_refresh: datetime | None = None
        self._company_cursor = 0  # round-robin pointer into STOCKS

    def start(self):
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._warmup()))
        self._tasks.append(asyncio.create_task(self._general_loop()))
        self._tasks.append(asyncio.create_task(self._per_company_loop()))

    async def _warmup(self):
        """On startup, fetch every listed company's Google News feed once
        (bounded concurrency) so every sector has articles within ~60-90s
        instead of waiting for the 27-minute round-robin cycle."""
        await asyncio.sleep(2)
        sem = asyncio.Semaphore(WARMUP_CONCURRENCY)
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True,
            headers={"User-Agent": "SCALEIndiaInvestment/1.0 (educational)"},
        ) as client:
            async def bound(stock):
                async with sem:
                    try:
                        return await self._fetch_rss(
                            client, None, _google_news_url(stock["name"]), stock["symbol"]
                        )
                    except Exception:
                        return 0
            results = await asyncio.gather(*[bound(s) for s in STOCKS], return_exceptions=True)
        self._prune_and_mark()
        # round-robin continues from where warmup left off; set cursor past warmup so
        # the per-company loop covers any newly-listed companies first.
        self._company_cursor = 0
        total = sum(r for r in results if isinstance(r, int))
        logger.info("Warmup fetched %d articles across %d companies", total, len(STOCKS))

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except Exception:
                pass

    # ------------- fetch loops -------------
    async def _general_loop(self):
        await asyncio.sleep(1)
        while self._running:
            try:
                await self._fetch_general()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("General news refresh failed: %s", e)
            await asyncio.sleep(GENERAL_REFRESH_INTERVAL)

    async def _per_company_loop(self):
        await asyncio.sleep(3)  # stagger so general + per-company don't collide
        while self._running:
            try:
                await self._fetch_per_company_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Per-company news refresh failed: %s", e)
            await asyncio.sleep(PER_COMPANY_CYCLE_INTERVAL)

    async def _fetch_general(self):
        async with httpx.AsyncClient(
            timeout=12, follow_redirects=True,
            headers={"User-Agent": "SCALEIndiaInvestment/1.0 (educational)"},
        ) as client:
            tasks = [self._fetch_rss(client, src, url, None) for src, url in GENERAL_FEEDS]
            await asyncio.gather(*tasks, return_exceptions=True)
        self._prune_and_mark()

    async def _fetch_per_company_batch(self):
        start = self._company_cursor
        end = start + PER_COMPANY_BATCH_SIZE
        batch = STOCKS[start:end]
        if len(batch) < PER_COMPANY_BATCH_SIZE:
            batch = batch + STOCKS[: (PER_COMPANY_BATCH_SIZE - len(batch))]
            self._company_cursor = PER_COMPANY_BATCH_SIZE - len(STOCKS[start:end])
        else:
            self._company_cursor = end % len(STOCKS)
        async with httpx.AsyncClient(
            timeout=12, follow_redirects=True,
            headers={"User-Agent": "SCALEIndiaInvestment/1.0 (educational)"},
        ) as client:
            tasks = [
                self._fetch_rss(client, None, _google_news_url(s["name"]), s["symbol"])
                for s in batch
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        self._prune_and_mark()
        logger.info(
            "Per-company news batch done: %s (cursor now %d/%d)",
            [s["symbol"] for s in batch], self._company_cursor, len(STOCKS),
        )

    async def _fetch_rss(
        self,
        client: httpx.AsyncClient,
        source_hint: str | None,
        url: str,
        symbol_hint: str | None,
    ) -> int:
        try:
            r = await client.get(url)
            if r.status_code != 200:
                return 0
            parsed = feedparser.parse(r.content)
            added = 0
            for entry in parsed.entries[:40]:
                link = entry.get("link") or ""
                if not link or link in self._seen_links:
                    continue
                title = _strip_html(entry.get("title", "")).strip()
                summary = _strip_html(entry.get("summary", "")).strip()[:600]
                if not title:
                    continue
                pub = _parse_pub_date(entry)
                # For Google News items, the publisher name lives in <source>;
                # for direct RSS feeds, prefer the hint we passed in.
                src = source_hint or _extract_source(entry)
                self.articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": src,
                    "published_at": pub,
                    "symbol_hint": symbol_hint,  # the company we queried for
                })
                self._seen_links.add(link)
                added += 1
            if added > 0:
                logger.info("Fetched %d new articles from %s", added, source_hint or url[:60])
            return added
        except Exception as e:
            logger.warning("feed fail (%s): %s", source_hint or url[:60], e)
            return 0

    def _prune_and_mark(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ARTICLE_RETENTION_HOURS)
        new_buf = deque(maxlen=MAX_BUFFER)
        for art in self.articles:
            if art["published_at"] >= cutoff:
                new_buf.append(art)
        self.articles = new_buf
        self._last_refresh = datetime.now(timezone.utc)

    # ------------- query API -------------

    def find_for(self, symbol: str, max_age_hours: int = 72, limit: int = 5) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        patterns = COMPILED_PATTERNS.get(symbol, [])
        hits = []
        for art in reversed(self.articles):
            if art["published_at"] < cutoff:
                continue
            # If the article was fetched via Google News for this specific symbol,
            # it's guaranteed relevant — include without regex check.
            if art.get("symbol_hint") == symbol:
                hits.append(art)
                if len(hits) >= limit:
                    return hits
                continue
            haystack = art["title"] + " " + art["summary"]
            if any(p.search(haystack) for p in patterns):
                hits.append(art)
                if len(hits) >= limit:
                    break
        return hits

    def latest(self, limit: int = 25, matched_only: bool = False, min_per_sector: int = 0) -> list[dict[str, Any]]:
        """Returns latest headlines with matched startup + sector metadata.
        When matched_only=True, drops everything that doesn't mention a listed company.
        When min_per_sector>0, guarantees up to `min_per_sector` freshest items from each
        sector (when available) at the top of the response before filling with chronology."""
        from data.stocks import STOCK_MAP as _SM
        # Build full-sorted list first (by published_at desc)
        all_sorted = sorted(self.articles, key=lambda a: a["published_at"], reverse=True)
        enriched: list[dict[str, Any]] = []
        for a in all_sorted:
            haystack = a["title"] + " " + a["summary"]
            matched_symbols: list[str] = []
            matched_sectors: set[str] = set()
            hint = a.get("symbol_hint")
            if hint:
                matched_symbols.append(hint)
                sec = _SM.get(hint, {}).get("sector")
                if sec:
                    matched_sectors.add(sec)
            for sym, patterns in COMPILED_PATTERNS.items():
                if sym in matched_symbols:
                    continue
                if any(p.search(haystack) for p in patterns):
                    matched_symbols.append(sym)
                    sec = _SM.get(sym, {}).get("sector")
                    if sec:
                        matched_sectors.add(sec)
            if matched_only and not matched_symbols:
                continue
            enriched.append({
                "title": a["title"],
                "summary": a["summary"][:320],
                "source": a["source"],
                "link": a["link"],
                "publishedAt": a["published_at"].isoformat(),
                "matchedSymbols": matched_symbols[:4],
                "matchedSectors": sorted(matched_sectors),
            })

        # Sector-balance pass — guarantee at least N freshest items per sector.
        if min_per_sector > 0:
            by_sector: dict[str, list[dict]] = {}
            for art in enriched:
                for sec in art["matchedSectors"]:
                    by_sector.setdefault(sec, []).append(art)
            picked: list[dict] = []
            seen_links: set[str] = set()
            for sec, arts in by_sector.items():
                for art in arts[:min_per_sector]:
                    if art["link"] not in seen_links:
                        seen_links.add(art["link"])
                        picked.append(art)
            # Fill remaining slots from chronological list, skipping dupes.
            for art in enriched:
                if len(picked) >= limit:
                    break
                if art["link"] in seen_links:
                    continue
                seen_links.add(art["link"])
                picked.append(art)
            # Re-sort the final picked list by publish date so the UI still reads chronologically.
            picked.sort(key=lambda a: a["publishedAt"], reverse=True)
            return picked[:limit]

        return enriched[:limit]

    def status(self) -> dict[str, Any]:
        return {
            "articleCount": len(self.articles),
            "lastRefresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "sourceCount": len(GENERAL_FEEDS) + 1,  # +1 for Google News aggregate
            "sources": [s for s, _ in GENERAL_FEEDS] + ["Google News (per-company)"],
        }


news_feeds = NewsFeedAggregator()
