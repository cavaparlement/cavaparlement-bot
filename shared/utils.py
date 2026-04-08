import os
import requests
from datetime import date

TELEGRAM_CHANNEL = "@cavaparlement"


def fmt_date(date_str: str) -> str:
    try:
        d = date.fromisoformat(date_str)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return date_str


def post_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("  ⚠️  TELEGRAM_BOT_TOKEN absent")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHANNEL, "text": text},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        print(f"  ✗ Telegram : {e}")


def make_session():
    import requests as req
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = req.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
