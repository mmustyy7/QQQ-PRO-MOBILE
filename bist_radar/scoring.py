# ============================================================
# BIST Tavan Radarı — Skor motoru
#
# Girdi : Günlük OHLCV DataFrame (Open, High, Low, Close, Volume)
# Çıktı : 0-100 "Tavan Aday Skoru" + Türkçe gerekçe listesi
#
# ÖNEMLİ: Skor bir OLASILIK değildir. Kurallı (heuristic) bir
# sıralama puanıdır. "%90 tavan olur" gibi bir kesinlik yoktur;
# skor sadece hangi hisselere önce bakmanız gerektiğini söyler.
# ============================================================

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

TR_TZ = ZoneInfo("Europe/Istanbul")

# BIST pay piyasası günlük fiyat limiti (Yıldız / Ana Pazar): ±%10
PRICE_LIMIT = 0.10

SESSION_OPEN = time(10, 0)
SESSION_CLOSE = time(18, 0)


# ------------------------------------------------------------
# BIST fiyat adımı (tick) ve tavan fiyatı
# ------------------------------------------------------------

def tick_size(price: float) -> float:
    """BIST pay piyasası fiyat adımları."""
    if price < 20:
        return 0.01
    if price < 50:
        return 0.02
    if price < 100:
        return 0.05
    if price < 250:
        return 0.10
    if price < 500:
        return 0.25
    if price < 1000:
        return 0.50
    if price < 2500:
        return 1.00
    return 2.50


def ceiling_price(base_price: float) -> float:
    """Yaklaşık tavan fiyatı: baz fiyat × 1.10, fiyat adımına aşağı yuvarlanır."""
    raw = base_price * (1 + PRICE_LIMIT)
    step = tick_size(raw)
    return round(math.floor(raw / step + 1e-9) * step, 2)


def floor_price(base_price: float) -> float:
    raw = base_price * (1 - PRICE_LIMIT)
    step = tick_size(raw)
    return round(math.ceil(raw / step - 1e-9) * step, 2)


# ------------------------------------------------------------
# Seans zamanı
# ------------------------------------------------------------

def session_fraction(now: datetime | None = None) -> float:
    """Seansın ne kadarının geçtiği (0-1). Seans dışı -> 1.0."""
    now = (now or datetime.now(TR_TZ)).astimezone(TR_TZ)
    if now.weekday() >= 5:
        return 1.0
    start = now.replace(hour=SESSION_OPEN.hour, minute=0, second=0, microsecond=0)
    end = now.replace(hour=SESSION_CLOSE.hour, minute=0, second=0, microsecond=0)
    if now <= start or now >= end:
        return 1.0
    return (now - start) / (end - start)


def is_market_open(now: datetime | None = None) -> bool:
    now = (now or datetime.now(TR_TZ)).astimezone(TR_TZ)
    if now.weekday() >= 5:
        return False
    return SESSION_OPEN <= now.time() < time(18, 10)


# ------------------------------------------------------------
# İndikatörler
# ------------------------------------------------------------

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100.0)


# ------------------------------------------------------------
# Sonuç yapısı
# ------------------------------------------------------------

@dataclass
class ScanResult:
    code: str
    last: float = float("nan")
    prev_close: float = float("nan")
    change_pct: float = float("nan")
    ceiling: float = float("nan")
    dist_to_ceiling_pct: float = float("nan")
    volume_ratio: float = float("nan")
    resistance_20d: float = float("nan")
    support_20d: float = float("nan")
    rsi14: float = float("nan")
    at_ceiling: bool = False
    technical_score: float = 0.0
    news_score: float = 0.0
    score: float = 0.0
    label: str = "—"
    reasons: list[str] = field(default_factory=list)
    news: list[dict] = field(default_factory=list)
    error: str = ""

    def finalize(self) -> "ScanResult":
        self.score = float(np.clip(self.technical_score + self.news_score, 0, 100))
        if self.at_ceiling:
            self.label = "🔒 TAVANDA"
        elif self.score >= 75:
            self.label = "🔥 Güçlü aday"
        elif self.score >= 55:
            self.label = "⚡ Aday"
        elif self.score >= 35:
            self.label = "👀 İzle"
        else:
            self.label = "—"
        return self

    def as_row(self) -> dict:
        return {
            "Hisse": self.code,
            "Durum": self.label,
            "Skor": round(self.score, 1),
            "Fiyat": round(self.last, 2),
            "Değişim %": round(self.change_pct, 2),
            "Tavan": self.ceiling,
            "Tavana kalan %": round(self.dist_to_ceiling_pct, 2),
            "Hacim x": round(self.volume_ratio, 2),
            "Direnç 20g": round(self.resistance_20d, 2),
            "Destek 20g": round(self.support_20d, 2),
            "RSI": round(self.rsi14, 1),
            "Haber puanı": round(self.news_score, 1),
            "Gerekçeler": " • ".join(self.reasons),
        }


# ------------------------------------------------------------
# Ana analiz
# ------------------------------------------------------------

MIN_BARS = 30


def analyze(code: str, df: pd.DataFrame, now: datetime | None = None) -> ScanResult:
    """Tek bir hisse için teknik tavan skoru hesaplar."""
    res = ScanResult(code=code)

    if df is None or df.empty:
        res.error = "veri yok"
        return res.finalize()

    df = df.dropna(subset=["Close"]).copy()
    if len(df) < MIN_BARS:
        res.error = f"yetersiz veri ({len(df)} bar)"
        return res.finalize()

    close, high, low = df["Close"], df["High"], df["Low"]
    vol = df["Volume"].fillna(0)

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    day_high = float(high.iloc[-1])
    day_low = float(low.iloc[-1])

    res.last = last
    res.prev_close = prev
    res.change_pct = (last / prev - 1) * 100
    res.ceiling = ceiling_price(prev)
    res.dist_to_ceiling_pct = (res.ceiling / last - 1) * 100
    res.at_ceiling = last >= res.ceiling - tick_size(res.ceiling) / 2

    # --- Hacim: seans içindeysek günün geçen kısmına göre normalize et
    now_tr = (now or datetime.now(TR_TZ)).astimezone(TR_TZ)
    last_bar_date = pd.Timestamp(df.index[-1]).date()
    frac = 1.0
    if last_bar_date == now_tr.date() and is_market_open(now_tr):
        frac = max(session_fraction(now_tr), 0.15)
    avg_vol = float(vol.iloc[-21:-1].mean())
    res.volume_ratio = (float(vol.iloc[-1]) / (avg_vol * frac)) if avg_vol > 0 else float("nan")

    # --- Destek / direnç (bugün hariç son 20 gün)
    res.resistance_20d = float(high.iloc[-21:-1].max())
    res.support_20d = float(low.iloc[-21:-1].min())
    high_52w = float(high.iloc[-253:-1].max())

    ema20 = float(ema(close, 20).iloc[-1])
    ema50 = float(ema(close, 50).iloc[-1])
    res.rsi14 = float(rsi(close).iloc[-1])

    rng = day_high - day_low
    close_pos = (last - day_low) / rng if rng > 0 else 1.0

    pts = 0.0
    why: list[str] = []

    # 1) Günlük momentum (0-30): tavana ne kadar yakın
    if res.change_pct > 0:
        pts += min(res.change_pct / (PRICE_LIMIT * 100), 1.0) * 30
    if res.at_ceiling:
        why.append(f"TAVANDA ({res.ceiling:.2f})")
    elif res.change_pct >= 3:
        why.append(
            f"Günlük %{res.change_pct:+.1f}, tavana %{res.dist_to_ceiling_pct:.1f} kaldı"
        )

    # 2) Hacim patlaması (0-20)
    vr = res.volume_ratio
    if not math.isnan(vr):
        if vr >= 3:
            pts += 20
        elif vr >= 2:
            pts += 15
        elif vr >= 1.5:
            pts += 10
        elif vr >= 1.2:
            pts += 5
        if vr >= 1.5:
            why.append(f"Hacim 20g ortalamanın {vr:.1f} katı (yoğun alım ilgisi)")

    # 3) Direnç kırılımı (0-15)
    if last > res.resistance_20d:
        pts += 10
        why.append(f"20 günlük direnç ({res.resistance_20d:.2f}) kırıldı")
        if last > high_52w:
            pts += 5
            why.append(f"52 haftalık zirve aşıldı ({high_52w:.2f})")

    # 4) Trend (0-10)
    if last > ema20 > ema50:
        pts += 10
        why.append("Yükselen trend (Fiyat > EMA20 > EMA50)")
    elif last > ema20:
        pts += 5

    # 5) Güçlü kapanış / gün yükseğine yakınlık (0-10)
    if res.change_pct > 0:
        if close_pos >= 0.8:
            pts += 10
            why.append("Fiyat gün yükseğine yakın (satıcı zayıf)")
        elif close_pos >= 0.6:
            pts += 5

    # 6) RSI momentum bölgesi (0-5)
    if 55 <= res.rsi14 <= 85:
        pts += 5
    elif res.rsi14 > 85:
        why.append(f"RSI {res.rsi14:.0f}: aşırı alım, dikkat")

    res.technical_score = pts
    res.reasons = why
    return res.finalize()


def apply_news(res: ScanResult, news_items: list[dict]) -> ScanResult:
    """Haber puanını (-15..+15) sonuca ekler."""
    if not news_items:
        return res.finalize()
    total = sum(item.get("weight", 0) for item in news_items)
    res.news_score = float(np.clip(total * 3, -15, 15))
    res.news = news_items
    best = max(news_items, key=lambda n: abs(n.get("weight", 0)))
    if best.get("weight", 0) > 0:
        res.reasons.append(f"Olumlu haber: {best['title'][:90]}")
    elif best.get("weight", 0) < 0:
        res.reasons.append(f"Olumsuz haber: {best['title'][:90]}")
    return res.finalize()
