#!/usr/bin/env python3
# ============================================================
# BIST Tavan Radarı — Komut satırı sürümü
#
#   python bist_scan.py                      # BIST 100, tek tarama
#   python bist_scan.py --index "BIST 30"
#   python bist_scan.py --codes ASELS THYAO SASA
#   python bist_scan.py --loop 5 --telegram  # 5 dk'da bir tara, Telegram'a gönder
#
# Telegram için ortam değişkenleri: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# ============================================================

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime

import pandas as pd

from bist_radar.data import fetch_daily
from bist_radar.news import fetch_news
from bist_radar.notify import format_alert, send_telegram
from bist_radar.scanner import scan, to_frame
from bist_radar.scoring import TR_TZ
from bist_radar.symbols import INDEXES


def run_once(codes, args, alerted: set) -> None:
    results = scan(
        codes,
        price_fetcher=fetch_daily,
        news_fetcher=None if args.no_news else fetch_news,
        news_top_n=args.news_top,
    )
    df = to_frame(results)
    now = datetime.now(TR_TZ)
    print(f"\n=== BIST Tavan Radarı — {now:%d.%m.%Y %H:%M} — {len(df)} hisse ===")
    if df.empty:
        print("Veri alınamadı.")
        return
    show = df[df["Skor"] >= args.min_score]
    cols = ["Hisse", "Durum", "Skor", "Fiyat", "Değişim %", "Tavana kalan %", "Hacim x", "Gerekçeler"]
    with pd.option_context("display.max_colwidth", 120, "display.width", 250):
        print(show[cols].to_string(index=False) if not show.empty else "Eşiği geçen hisse yok.")

    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    for row in df.to_dict("records"):
        hot = row["Skor"] >= args.alert_score or row["Durum"] == "🔒 TAVANDA"
        if hot and row["Hisse"] not in alerted:
            alerted.add(row["Hisse"])
            if args.telegram:
                send_telegram(token, chat, format_alert(row))


def main() -> None:
    p = argparse.ArgumentParser(description="BIST tavan adayı tarayıcı")
    p.add_argument("--index", default="BIST 100", choices=list(INDEXES))
    p.add_argument("--codes", nargs="*", help="Özel hisse listesi (örn. ASELS THYAO)")
    p.add_argument("--min-score", type=float, default=35)
    p.add_argument("--alert-score", type=float, default=75)
    p.add_argument("--news-top", type=int, default=15)
    p.add_argument("--no-news", action="store_true")
    p.add_argument("--telegram", action="store_true")
    p.add_argument("--loop", type=float, default=0, help="Dakika cinsinden tekrar aralığı")
    args = p.parse_args()

    codes = [c.upper() for c in args.codes] if args.codes else INDEXES[args.index]
    alerted: set = set()
    while True:
        run_once(codes, args, alerted)
        if not args.loop:
            break
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    main()
