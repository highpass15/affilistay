import html
import os

import httpx


TELEGRAM_API_BASE = "https://api.telegram.org"


def format_krw(value):
    try:
        return f"{int(value or 0):,}원"
    except (TypeError, ValueError):
        return "-"


def _escape(value):
    return html.escape(str(value if value not in (None, "") else "-"), quote=False)


def telegram_configured():
    return bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip() and os.getenv("TELEGRAM_CHAT_ID", "").strip())


def send_telegram_notification(title, rows=None, action_url=None):
    """Owner alert via Telegram Bot API. Missing credentials should never block app flow."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[Telegram Notification Skipped] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없습니다.")
        return False

    lines = [f"<b>{_escape(title)}</b>"]
    for label, value in rows or []:
        if value not in (None, ""):
            lines.append(f"{_escape(label)}: {_escape(value)}")
    if action_url:
        lines.append(f'<a href="{html.escape(action_url, quote=True)}">관리자에서 확인</a>')

    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3790] + "..."

    try:
        response = httpx.post(
            f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=6,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"[Telegram Notification Error] {exc}")
        return False
