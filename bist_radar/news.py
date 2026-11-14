# ============================================================
# BIST Tavan Radarı — Haber / KAP taraması
#
# Kaynak: Google News RSS (Türkçe, son 24 saat). KAP bildirimleri
# genellikle haber sitelerinde "KAP" ibaresiyle dakikalar içinde
# yer alır. Başlıklar Türkçe anahtar kelimelerle puanlanır.
#
# Not: KAP'ın resmî, belgelenmiş bir halka açık API'si yoktur.
# Doğrudan KAP entegrasyonu istenirse `fetch_news` yerine
# aynı formatta liste döndüren bir fonksiyon yazmak yeterlidir:
#   [{"title", "link", "published", "source", "weight"}, ...]
# ============================================================

from __future__ import annotations

import email.utils
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

# (anahtar kelime, ağırlık) — küçük harf, Türkçe karakterli
POSITIVE = [
    ("bedelsiz", 4),
    ("pay geri alım", 3), ("geri alım", 3),
    ("sözleşme imzala", 3), ("sözleşme", 3),
    ("iş ilişkisi", 3), ("yeni iş", 3),
    ("ihale", 3), ("sipariş", 3),
    ("ihracat", 2), ("anlaşma", 2), ("ortaklık", 2),
    ("satın al", 2), ("devral", 2),
    ("temettü", 2), ("kâr payı", 2), ("kar payı", 2),
    ("rekor", 2), ("net kâr", 2), ("net kar", 2), ("kârını artırdı", 2),
    ("yatırım teşvik", 2), ("patent", 2), ("onay aldı", 2),
    ("al tavsiyesi", 2), ("hedef fiyat", 1),
    ("tavan", 2), ("yükseliş", 1), ("kapasite artış", 2),
]

NEGATIVE = [
    ("konkordato", -5), ("iflas", -5),
    ("işlem yasağı", -4), ("tedbir", -4), ("brüt takas", -3),
    ("soruşturma", -3), ("ceza", -3), ("iptal", -3), ("zarar", -3),
    ("dava", -2), ("taban", -2), ("satış baskısı", -2),
    ("bedelli", -1), ("düşüş", -1), ("geriledi", -1),
]


def tr_lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def score_headline(title: str) -> tuple[int, list[str]]:
    t = tr_lower(title)
    weight = 0
    hits: list[str] = []
    used_spans: list[tuple[int, int]] = []
    for kw, w in POSITIVE + NEGATIVE:
        idx = t.find(kw)
        if idx < 0:
            continue
        span = (idx, idx + len(kw))
        # "pay geri alım" bulunduysa "geri alım"ı ikinci kez sayma
        if any(s <= span[0] and span[1] <= e for s, e in used_spans):
            continue
        used_spans.append(span)
        weight += w
        hits.append(kw)
    return max(-5, min(5, weight)), hits


def _parse_rss(xml_text: str, max_age_hours: float) -> list[dict]:
    root = ET.fromstring(xml_text)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        pub_raw = item.findtext("pubDate") or ""
        try:
            published = email.utils.parsedate_to_datetime(pub_raw)
        except (TypeError, ValueError):
            published = None
        if published and published < cutoff:
            continue
        weight, hits = score_headline(title)
        items.append({
            "title": title,
            "link": item.findtext("link") or "",
            "published": published.isoformat() if published else "",
            "source": item.findtext("source") or "",
            "weight": weight,
            "keywords": hits,
        })
    return items


def fetch_news(code: str, max_age_hours: float = 24, timeout: float = 8) -> list[dict]:
    """Bir hisse koduyla ilgili son haberleri getirir ve puanlar."""
    query = f'"{code}" (hisse OR KAP OR borsa) when:1d'
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + "&hl=tr&gl=TR&ceid=TR:tr"
    )
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    items = _parse_rss(resp.text, max_age_hours)
    # Başlıkta kod geçmeyen ve hiçbir anahtar kelime içermeyenleri at
    return [i for i in items if code in i["title"].upper() or i["weight"] != 0][:10]
