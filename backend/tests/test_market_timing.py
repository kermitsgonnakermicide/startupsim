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


def test_opening_time_is_tradable():
    info = session_info(at_ist(9, 0))

    assert info["status"] == "OPEN"
    assert info["sessionType"] == "REGULAR"


def test_before_open_is_not_tradable():
    info = session_info(at_ist(8, 59))

    assert info["status"] == "CLOSED"
    assert info["sessionType"] == "CLOSED"
    assert info["countdownLabel"] == "Opens in"


def test_closing_time_is_not_tradable():
    info = session_info(at_ist(22, 0))

    assert info["status"] == "CLOSED"
    assert info["sessionType"] == "CLOSED"
    assert info["countdownLabel"] == "Opens in"


def test_saturday_is_tradable():
    saturday = IST.localize(datetime(2026, 5, 23, 12, 0))
    info = session_info(saturday)

    assert info["status"] == "OPEN"
    assert info["sessionType"] == "REGULAR"


def test_force_market_open_override(monkeypatch):
    monkeypatch.setenv("FORCE_MARKET_OPEN", "true")

    info = session_info(at_ist(15, 45))

    assert info["status"] == "OPEN"
    assert info["sessionType"] == "REGULAR"
    assert info["forcedOpen"] is True
    assert info["countdownLabel"] is None
