from datetime import date, timedelta
from hashlib import sha256
from urllib.parse import urlsplit


def choose_window(start: date, width: int, year: int) -> tuple[date, date]:
    first_day, after_last_day = date(year, 1, 1), date(year + 1, 1, 1)
    if not first_day <= start < after_last_day:
        raise ValueError("Date outside selected year")
    if width not in (1, 2, 3):
        raise ValueError("Window width must be 1, 2, or 3 days")
    return start, min(start + timedelta(days=width), after_last_day)


def iso_utc(day: date) -> str:
    return f"{day.isoformat()}T00:00:00Z"


def normalize_page_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme != "https" or parsed.hostname not in ("facebook.com", "www.facebook.com", "m.facebook.com"):
        raise ValueError("Enter a public Facebook page URL beginning with https://facebook.com/")
    path = parsed.path.rstrip("/")
    if not path or path == "/":
        raise ValueError("Enter a Facebook page URL, not the Facebook home page")
    if parsed.username or parsed.password or parsed.port:
        raise ValueError("Unexpected credentials or port in URL")
    if parsed.query or parsed.fragment:
        raise ValueError("Remove query parameters and fragments from the page URL")
    return f"https://www.facebook.com{path}"


def storage_suffix(page_url: str, year: int) -> str:
    return f"{year}-{sha256(page_url.encode('utf-8')).hexdigest()[:12]}"
