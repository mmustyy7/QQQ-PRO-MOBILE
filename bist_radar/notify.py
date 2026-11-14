# ============================================================
# BIST Tavan Radarı — Telegram bildirimi (telefona anlık uyarı)
#
# Kurulum:
#   1) Telegram'da @BotFather -> /newbot -> TOKEN alın
#   2) Botunuza bir mesaj atın, sonra
#      https://api.telegram.org/bot<TOKEN>/getUpdates adresinden chat id'yi alın
#   3) Streamlit Secrets (veya ortam değişkeni):
#        TELEGRAM_BOT_TOKEN = "..."
#        TELEGRAM_CHAT_ID   = "..."
# ============================================================

from __future__ import annotations

import requests


def format_alert(row: dict) -> str:
    lines = [
        f"{row['Durum']}  #{row['Hisse']}  Skor {row['Skor']:.0f}/100",
        f"Fiyat {row['Fiyat']:.2f}  ({row['Değişim %']:+.2f}%)  Tavan {row['Tavan']:.2f}",
    ]
    if row.get("Gerekçeler"):
        lines.append("• " + row["Gerekçeler"].replace(" • ", "\n• "))
    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, text: str, timeout: float = 10) -> bool:
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=timeout,
        )
        return resp.ok
    except requests.RequestException:
        return False
