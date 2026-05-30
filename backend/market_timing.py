"""IST-aware market session utilities."""
from datetime import datetime, timedelta
import os
import pytz

IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def _at(dt: datetime, h: int, m: int) -> datetime:
    return dt.replace(hour=h, minute=m, second=0, microsecond=0)


def force_market_open() -> bool:
    val = os.environ.get("FORCE_MARKET_OPEN", "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


def session_info(now: datetime | None = None) -> dict:
    """Return current market session info based on IST time."""
    n = now or now_ist()
    weekday = n.weekday()  # Mon=0 ... Sun=6

    open_start = _at(n, 9, 0)
    close_time = _at(n, 22, 0)

    is_trading_day = weekday < 6

    status = "CLOSED"
    session_type = "CLOSED"
    next_open = None
    countdown_to = None
    countdown_label = None

    if is_trading_day:
        if open_start <= n < close_time:
            status = "OPEN"
            session_type = "REGULAR"
            countdown_to = close_time
            countdown_label = "Closes in"
        elif n < open_start:
            status = "CLOSED"
            session_type = "CLOSED"
            next_open = open_start
        else:
            status = "CLOSED"
            session_type = "CLOSED"
            nxt = n + timedelta(days=1)
            while nxt.weekday() >= 6:
                nxt += timedelta(days=1)
            next_open = _at(nxt, 9, 0)
    else:
        status = "CLOSED"
        session_type = "CLOSED"
        nxt = n + timedelta(days=1)
        while nxt.weekday() >= 6:
            nxt += timedelta(days=1)
        next_open = _at(nxt, 9, 0)

    if next_open and not countdown_to:
        countdown_to = next_open
        countdown_label = "Opens in"

    if force_market_open():
        status = "OPEN"
        session_type = "REGULAR"
        countdown_to = None
        countdown_label = None

    return {
        "status": status,  # OPEN only during regular trading
        "sessionType": session_type,  # PRE_OPEN | REGULAR | POST_CLOSE | CLOSED
        "istTime": n.strftime("%H:%M:%S"),
        "istDate": n.strftime("%d %b %Y"),
        "nextOpen": next_open.isoformat() if next_open else None,
        "closesAt": close_time.isoformat() if is_trading_day else None,
        "countdownTo": countdown_to.isoformat() if countdown_to else None,
        "countdownLabel": countdown_label,
        "forcedOpen": force_market_open(),
    }


def is_market_open() -> bool:
    info = session_info()
    return info["sessionType"] == "REGULAR"
