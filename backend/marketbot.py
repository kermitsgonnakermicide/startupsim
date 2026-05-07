"""MarketBot wrapper for StartupMarket.

Two responsibilities:
  1. multi-turn chat
  2. one-shot JSON sentiment batch for news-driven price drift

If OPENAI credentials are configured we use the OpenAI Responses API.
Otherwise, the module falls back to deterministic local responses so the
app can still run in Docker without an LLM key.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger("marketbot")

MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
DISCLAIMER = "(MarketBot estimate - for educational use only)"


def _client() -> AsyncOpenAI | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return AsyncOpenAI(api_key=api_key)


CHAT_SYSTEM = (
    "You are MarketBot, an AI assistant for SCALE India Investment - an educational "
    "private-startup-valuation simulator for high-school students in India. You explain "
    "private startup valuations, funding rounds, unit economics, and market "
    "concepts in simple, friendly language. All prices on this platform are "
    "AI-estimated simulations, not real market data; prices also reflect "
    "supply and demand from real student trades on the platform. Always end "
    f"your response with: '{DISCLAIMER}'. "
    "Keep responses under 120 words."
)

NEWS_SYSTEM = (
    "You are MarketBot, a private-startup-valuation analyst for an educational "
    "simulator. For each company, give a sentiment score reflecting recent "
    "(last ~12 months) momentum from public knowledge - funding rounds, revenue "
    "milestones, layoffs, regulatory issues, founder departures, fires, lawsuits, "
    "data breaches, IPO filings, acquisitions, partnership announcements, etc. "
    "Use the FULL range and be decisive: "
    "score -5 for catastrophic events (fire/data-breach/fraud/enforcement), "
    "score -3 to -4 for significant negatives (layoffs/markdown/scandal/lawsuit), "
    "score -1 to -2 for mild headwinds, "
    "0 only if genuinely no news, "
    "+1 to +2 for small positives, "
    "+3 to +4 for major wins (large funding round/profitable quarter/big partnership), "
    "+5 for company-defining events (IPO/acquisition/billion-dollar-round). "
    "Reply ONLY with valid JSON, no markdown, no prose. Format: "
    '{"SYMBOL": {"score": int, "reason": "one short sentence describing the actual news driving the score"}}'
)


LIVE_NEWS_SYSTEM = (
    "You are MarketBot, a private-startup-valuation analyst for an educational "
    "simulator. You are given REAL Indian-news headlines from verified national "
    "publishers (Inc42, YourStory, Moneycontrol, LiveMint, Economic Times, "
    "Hindu BusinessLine, Indian Express, CNBC-TV18). Score each company based "
    "ONLY on the headlines provided (do not invent news). "
    "Use the FULL range and be decisive: "
    "score -5 for catastrophic events (fire/data-breach/fraud/enforcement action), "
    "score -3 to -4 for significant negatives (layoffs/markdown/scandal/lawsuit), "
    "score -1 to -2 for mild headwinds, "
    "0 if the headlines are neutral, irrelevant, or no headlines were provided, "
    "+1 to +2 for small positives, "
    "+3 to +4 for major wins (funding round/profitable quarter/big partnership), "
    "+5 for company-defining events (IPO/acquisition/billion-dollar round). "
    "Reply ONLY with valid JSON, no markdown, no prose. Format: "
    '{"SYMBOL": {"score": int, "reason": "one short sentence quoting or paraphrasing the actual headline"}}'
)


async def _responses_text(system: str, user_text: str) -> str:
    client = _client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not configured")
    resp = await client.responses.create(
        model=MODEL_NAME,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        temperature=0.4,
    )
    return (resp.output_text or "").strip()


def _trim(text: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _ensure_disclaimer(text: str) -> str:
    body = (text or "").strip()
    if DISCLAIMER in body:
        return body
    if not body:
        body = "This simulator tracks startup narratives, funding signals, and trading activity to explain price moves."
    return f"{body.rstrip('. ')}. {DISCLAIMER}"


def _offline_chat_reply(user_text: str) -> str:
    lower = (user_text or "").strip().lower()
    company_match = re.search(r"(what is|about|explain)\s+([a-z0-9 .&-]+)\??$", lower)
    if company_match:
        company = company_match.group(2).strip().title()
        reply = (
            f"{company} is treated here as a private Indian startup proxy, so its price reflects "
            "simulated valuation changes, investor demand, and recent news signals inside the learning market"
        )
        return _ensure_disclaimer(_trim(reply))
    if "price" in lower or "moved" in lower or "move" in lower:
        reply = (
            "Prices usually move because the simulator blends startup narrative shifts, news sentiment, "
            "and buy or sell pressure from student trades"
        )
        return _ensure_disclaimer(_trim(reply))
    reply = (
        "I can help explain startup valuations, funding rounds, unit economics, and why a company in this "
        "simulator may be rising or falling"
    )
    return _ensure_disclaimer(_trim(reply))


def _offline_sentiment(items: list[dict], article_lookup: dict[str, list[dict]] | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    article_lookup = article_lookup or {}
    for it in items:
        sym = it["symbol"]
        articles = article_lookup.get(sym, [])
        if articles:
            headline = articles[0].get("title") or "Recent headlines were mixed."
            score = 1 if re.search(r"funding|profit|growth|launch|partnership|expands?", headline, re.I) else 0
            if re.search(r"layoff|lawsuit|breach|fire|probe|cuts?", headline, re.I):
                score = -2
            out[sym] = {"score": score, "reason": headline[:240]}
        else:
            out[sym] = {
                "score": 0,
                "reason": f"No live model key configured; keeping {sym} neutral until fresh analysis is available.",
            }
    return out


async def chat_send(session_id: str, user_text: str) -> str:
    del session_id
    try:
        return _ensure_disclaimer(await _responses_text(CHAT_SYSTEM, user_text))
    except Exception as e:
        logger.warning("chat fallback engaged: %s", e)
        return _offline_chat_reply(user_text)


async def chat_with_history(session_id: str, history: list[dict], user_text: str) -> str:
    del session_id
    if history:
        preamble_lines = []
        for h in history[-6:]:
            role = h.get("role", "user")
            content = (h.get("content") or "").strip()
            if not content:
                continue
            preamble_lines.append(f"{role.upper()}: {content}")
        if preamble_lines:
            user_text = (
                "Recent conversation context:\n"
                + "\n".join(preamble_lines)
                + f"\n\nCurrent question:\n{user_text}"
            )
    return await chat_send("history", user_text)


async def fetch_news_sentiment(items: list[dict]) -> dict[str, dict[str, Any]]:
    """items: [{symbol, name, sector}, ...]
    Returns: {symbol: {score:int, reason:str}}
    Uses MarketBot's model knowledge when configured, otherwise local fallback.
    """
    if not items:
        return {}
    listing = "\n".join(f"- {it['symbol']}: {it['name']} ({it.get('sector', '')})" for it in items)
    user_text = (
        "Score the following Indian private startups for current momentum:\n\n"
        + listing
        + "\n\nReturn ONLY a JSON object keyed by symbol."
    )
    try:
        raw = await _responses_text(NEWS_SYSTEM, user_text)
    except Exception as e:
        logger.warning("news sentiment fetch failed: %s", e)
        return _offline_sentiment(items)
    return _parse_sentiment_json(raw)


async def fetch_live_news_sentiment(
    items: list[dict],
    article_lookup: dict[str, list[dict]],
) -> dict[str, dict[str, Any]]:
    """Score companies based on real headlines from live RSS feeds."""
    if not items:
        return {}
    sections = []
    covered = []
    for it in items:
        sym = it["symbol"]
        articles = article_lookup.get(sym, [])
        if not articles:
            continue
        covered.append(it)
        bullets = []
        for a in articles[:5]:
            pub = a["published_at"]
            try:
                pub_str = pub.strftime("%Y-%m-%d") if hasattr(pub, "strftime") else str(pub)[:10]
            except Exception:
                pub_str = ""
            line = f"  - [{a['source']} {pub_str}] {a['title']}"
            if a.get("summary"):
                line += f" - {a['summary'][:200]}"
            bullets.append(line)
        sections.append(f"{sym} ({it['name']}, {it.get('sector', '')}):\n" + "\n".join(bullets))

    if not sections:
        return {}

    user_text = (
        "Recent verified headlines about these Indian private startups:\n\n"
        + "\n\n".join(sections)
        + "\n\nScore each company based ONLY on these headlines. "
        "Return JSON keyed by symbol."
    )
    try:
        raw = await _responses_text(LIVE_NEWS_SYSTEM, user_text)
    except Exception as e:
        logger.warning("live news sentiment fetch failed: %s", e)
        return _offline_sentiment(covered, article_lookup)
    return _parse_sentiment_json(raw)


def _parse_sentiment_json(raw: str) -> dict[str, dict[str, Any]]:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
        return {
            k: {
                "score": int(v.get("score", 0)),
                "reason": str(v.get("reason", ""))[:240],
            }
            for k, v in parsed.items()
            if isinstance(v, dict)
        }
    except Exception as e:
        logger.warning("sentiment parse failed: %s - raw: %s", e, raw[:200])
        return {}
