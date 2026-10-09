from datetime import date, datetime, timedelta, timezone

_offset = timedelta()

def now() -> datetime:
    return datetime.now(timezone.utc) + _offset

def today() -> date:
    return now().date()

def advance(days: int) -> None:
    global _offset
    _offset += timedelta(days=days)

def reset() -> None:
    global _offset
    _offset = timedelta()
