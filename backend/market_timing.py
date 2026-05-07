"""IST-aware market session utilities."""
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def _at(dt: datetime, h: int, m: int) -> datetime:
    return dt.replace(hour=h, minute=m, second=0, microsecond=0)


def session_info(now: datetime | None = None) -> dict:
    """Return current market session info based on IST time."""
    n = now or now_ist()
    weekday = n.weekday()  # Mon=0 ... Sun=6

    pre_open_start = _at(n, 9, 0)
    open_start = _at(n, 9, 15)
    close_time = _at(n, 15, 30)
    post_close_end = _at(n, 16, 0)

    is_weekday = weekday < 5

    status = "CLOSED"
    session_type = "CLOSED"
    next_open = None
    countdown_to = None
    countdown_label = None

    if is_weekday:
        if pre_open_start <= n < open_start:
            status = "OPEN"
            session_type = "PRE_OPEN"
            countdown_to = open_start
            countdown_label = "Opens in"
        elif open_start <= n < close_time:
            status = "OPEN"
            session_type = "REGULAR"
            countdown_to = close_time
            countdown_label = "Closes in"
        elif close_time <= n < post_close_end:
            status = "OPEN"
            session_type = "POST_CLOSE"
            countdown_to = post_close_end
            countdown_label = "Fully closes in"
        elif n < pre_open_start:
            status = "CLOSED"
            session_type = "CLOSED"
            next_open = open_start
        else:
            status = "CLOSED"
            session_type = "CLOSED"
            # next weekday
            nxt = n + timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
            next_open = _at(nxt, 9, 15)
    else:
        status = "CLOSED"
        session_type = "CLOSED"
        nxt = n + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        next_open = _at(nxt, 9, 15)

    if next_open and not countdown_to:
        countdown_to = next_open
        countdown_label = "Opens in"

    return {
        "status": status,  # OPEN or CLOSED
        "sessionType": session_type,  # PRE_OPEN | REGULAR | POST_CLOSE | CLOSED
        "istTime": n.strftime("%H:%M:%S"),
        "istDate": n.strftime("%d %b %Y"),
        "nextOpen": next_open.isoformat() if next_open else None,
        "closesAt": close_time.isoformat() if is_weekday else None,
        "countdownTo": countdown_to.isoformat() if countdown_to else None,
        "countdownLabel": countdown_label,
    }


def is_market_open() -> bool:
    info = session_info()
    return info["sessionType"] == "REGULAR"
