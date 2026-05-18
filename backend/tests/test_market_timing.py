from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_timing import IST, session_info


def at_ist(hour, minute):
    return IST.localize(datetime(2026, 5, 18, hour, minute))


def test_regular_session_is_open_for_trading():
    info = session_info(at_ist(10, 0))

    assert info["status"] == "OPEN"
    assert info["sessionType"] == "REGULAR"
    assert info["countdownLabel"] == "Closes in"


def test_pre_open_is_not_tradable():
    info = session_info(at_ist(9, 5))

    assert info["status"] == "CLOSED"
    assert info["sessionType"] == "PRE_OPEN"
    assert info["countdownLabel"] == "Opens in"


def test_post_close_is_not_tradable():
    info = session_info(at_ist(15, 45))

    assert info["status"] == "CLOSED"
    assert info["sessionType"] == "POST_CLOSE"
    assert info["countdownLabel"] == "Fully closes in"
