"""MarketBot — Gemini wrapper for StartupMarket news sentiment.

This implementation uses Google's Gemini API while maintaining the 
API surface requested by the user.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai

logger = logging.getLogger("marketbot")

# API Surface compatibility classes
class UserMessage:
    def __init__(self, text: str):
        self.text = text

class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.model_name = "gemini-1.5-flash"
        if api_key:
            genai.configure(api_key=api_key)

    def with_model(self, provider: str, name: str) -> LlmChat:
        # We always use Gemini, but we can switch models based on the name hint
        if "pro" in name.lower() or "4.5" in name.lower():
            self.model_name = "gemini-1.5-pro"
        else:
            self.model_name = "gemini-1.5-flash"
        return self

    async def send_message(self, msg: UserMessage) -> str:
        if not self.api_key:
            logger.warning("MarketBot API key missing; check EMERGENT_LLM_KEY or GEMINI_API_KEY")
            return "MarketBot is currently offline (API key not configured). (MarketBot estimate — for educational use only)"
        
        try:
            logger.info(f"MarketBot using model: {self.model_name}")
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_message
            )
            # Use generation_config to nudge it towards JSON when appropriate
            # but we'll keep it simple as the system prompt handles it.
            response = await model.generate_content_async(msg.text)
            return (response.text or "").strip()
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"I'm having trouble connecting to my brain right now. {e} (MarketBot estimate — for educational use only)"

def _key() -> str:
    k = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("GEMINI_API_KEY")
    if not k:
        # Fallback to local .env if available during dev
        return ""
    return k


MODEL_PROVIDER = "google"
MODEL_NAME = "gemini-1.5-flash"


NEWS_SYSTEM = (
    "You are MarketBot scoring Indian private startups on a -5 to +5 scale "
    "(-5: catastrophic, +5: IPO/acquisition). Reply ONLY: "
    '{"SYMBOL": {"score": int, "reason": "short sentence on the news driving score"}}'
)

LIVE_NEWS_SYSTEM = (
    "You are MarketBot. Score each company -5 to +5 based ONLY on given headlines."
    " -5: catastrophic, +5: IPO/acquisition. 0: neutral/no news. "
    "Reply ONLY: "
    '{"SYMBOL": {"score": int, "reason": "short sentence quoting the headline"}}'
)


def _offline_sentiment(items: list[dict], article_lookup: dict[str, list[dict]] | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    article_lookup = article_lookup or {}
    for it in items:
        sym = it["symbol"]
        articles = article_lookup.get(sym, [])
        if articles:
            headline = articles[0].get("title") or "Mixed market signals."
            score = 0
            pos = r"funding|profit|growth|launch|partnership|expands?|unicorn|ipo|deal"
            neg = r"layoff|lawsuit|breach|fire|probe|cuts?|markdown|loss|scandal"
            if re.search(pos, headline, re.I):
                score = 2
            elif re.search(neg, headline, re.I):
                score = -2
            out[sym] = {"score": score, "reason": headline[:240]}
        else:
            sector = it.get("sector", "Tech")
            out[sym] = {
                "score": 0,
                "reason": f"MarketBot analyzing {sector} sector signals for {sym}. No recent major headlines found.",
            }
    return out


async def fetch_news_sentiment(items: list[dict]) -> dict[str, dict[str, Any]]:
    """items: [{symbol, name, sector}, ...]
    Returns: {symbol: {score:int, reason:str}}
    Uses MarketBot's training knowledge — fallback when no live articles available.
    """
    if not items:
        return {}
    key = _key()
    if not key:
        return _offline_sentiment(items)
    listing = "\n".join(f"- {it['symbol']}: {it['name']} ({it.get('sector','')})" for it in items)
    user_text = "Score these:\n" + listing
    chat = (
        LlmChat(api_key=key, session_id=f"news-{items[0]['symbol']}", system_message=NEWS_SYSTEM)
        .with_model(MODEL_PROVIDER, MODEL_NAME)
    )
    try:
        raw = await chat.send_message(UserMessage(text=user_text))
    except Exception as e:
        logger.warning("news sentiment fetch failed: %s", e)
        return _offline_sentiment(items)
    return _parse_sentiment_json(raw)


async def fetch_live_news_sentiment(
    items: list[dict],
    article_lookup: dict[str, list[dict]],
) -> dict[str, dict[str, Any]]:
    """Score companies based on REAL headlines from live RSS feeds."""
    if not items:
        return {}
    key = _key()
    if not key:
        return _offline_sentiment(items, article_lookup)
    sections = []
    covered = []
    for it in items:
        sym = it["symbol"]
        articles = article_lookup.get(sym, [])
        if not articles:
            continue
        covered.append(it)
        bullets = []
        for a in articles[:3]:
            pub = a["published_at"]
            try:
                pub_str = pub.strftime("%Y-%m-%d") if hasattr(pub, "strftime") else str(pub)[:10]
            except Exception:
                pub_str = ""
            line = f"• [{a['source']} {pub_str}] {a['title']}"
            if a.get("summary"):
                line += f" — {a['summary'][:100]}"
            bullets.append(line)
        sections.append(f"{sym}:\n" + "\n".join(bullets))

    if not sections:
        return {}

    user_text = "Headlines:\n" + "\n\n".join(sections)
    chat = (
        LlmChat(api_key=key, session_id=f"live-news-{covered[0]['symbol']}", system_message=LIVE_NEWS_SYSTEM)
        .with_model(MODEL_PROVIDER, MODEL_NAME)
    )
    try:
        raw = await chat.send_message(UserMessage(text=user_text))
    except Exception as e:
        logger.warning("live news sentiment fetch failed: %s", e)
        return _offline_sentiment(covered, article_lookup)
    return _parse_sentiment_json(raw)


def _parse_sentiment_json(raw: str) -> dict[str, dict[str, Any]]:
    # Remove markdown code blocks if present
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
        return {
            str(k).upper(): {
                "score": int(v.get("score", 0)),
                "reason": str(v.get("reason", ""))[:240],
            }
            for k, v in parsed.items()
            if isinstance(v, dict)
        }
    except Exception as e:
        logger.warning("sentiment parse failed: %s — raw: %s", e, raw[:200])
        return {}
