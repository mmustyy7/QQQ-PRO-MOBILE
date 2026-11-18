# ============================================================
# MOMENTUM TARAYICI — ABD hisseleri
#
# Amaç: Günlük açılışından +%10 / +%15 / +%20 prim yapma
# potansiyeli taşıyan ABD hisselerini taramak, puanlamak ve
# gerekçeleriyle birlikte sıralamak.
#
# AKIŞ
#   1. EVREN     : Yahoo tarama listeleri (günün yükselenleri,
#                  küçük şirket yükselenleri, en aktifler, en çok
#                  açığa satılanlar, yüksek beta ...) + izleme listesi
#   2. ÖN ELEME  : Fiyat, likidite, hacim ve ilk momentum
#   3. FİYAT     : Günlük (1 yıl) + 5 dakikalık (pre/post dahil) barlar
#   4. ÖZELLİK   : Açılıştan değişim, gap, RVOL, VWAP, açılış aralığı,
#                  20 gün / 52 hafta zirvesi, sıkışma, ATR, geçmiş
#                  %10+ gün sayısı ...
#   5. DERİN     : En iyi adaylar için haber, float / açığa satış,
#                  bilanço tarihi ve olağandışı CALL opsiyon hacmi
#   6. PUAN      : 100 puanlık şeffaf puan + sinyal / risk listesi
#
# NOT: Broker'a emir göndermez. Bir hissenin %10+ yükseleceğini
# garanti eden bir yöntem yoktur; bu araç olasılığı yüksek adayları
# öne çıkarır, karar kullanıcıya aittir.
# ============================================================

from __future__ import annotations

import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")

PRE_START = 4 * 60          # 04:00
REG_START = 9 * 60 + 30     # 09:30
REG_END = 16 * 60           # 16:00
POST_END = 20 * 60          # 20:00
REG_MINUTES = REG_END - REG_START

PHASE_LABELS = {
    "premarket": "Pre-market (açılış öncesi)",
    "regular": "Seans açık",
    "postmarket": "After-hours (kapanış sonrası)",
    "closed": "Piyasa kapalı (son seans verisi)",
}

# Yüksek oynaklıkla bilinen, her taramada kontrol edilen semboller.
DEFAULT_WATCHLIST = [
    "TSLA", "NVDA", "AMD", "PLTR", "SMCI", "MSTR", "COIN", "HOOD",
    "SOFI", "MARA", "RIOT", "CLSK", "IONQ", "RGTI", "QBTS", "SOUN",
    "RKLB", "ASTS", "OKLO", "SMR", "HIMS", "UPST", "AFRM", "CVNA",
    "RIVN", "LCID", "NIO", "APP", "CRWV", "TEM", "ACHR", "JOBY",
]

SCREEN_LABELS = {
    "day_gainers": "Günün yükselenleri",
    "small_cap_gainers": "Küçük şirket yükselenleri",
    "most_actives": "En aktifler",
    "aggressive_small_caps": "Agresif küçük şirketler",
    "most_shorted_stocks": "En çok açığa satılanlar",
    "custom_movers": "Hareketliler (+%4 üstü)",
    "custom_high_beta": "Yüksek beta",
    "watchlist": "İzleme listesi",
}


# ============================================================
# AYARLAR / SONUÇ
# ============================================================

@dataclass
class ScanSettings:
    min_price: float = 1.0
    max_price: float = 1000.0
    min_dollar_volume: float = 3_000_000.0   # bugünkü işlem hacmi ($)
    min_avg_volume: float = 300_000.0        # 20 günlük ort. adet
    max_universe: int = 150                  # fiyat verisi çekilecek sembol
    deep_count: int = 30                     # haber / opsiyon bakılacak
    include_news: bool = True
    include_options: bool = True
    include_screens: bool = True
    watchlist: List[str] = field(default_factory=lambda: list(DEFAULT_WATCHLIST))


@dataclass
class ScanResult:
    table: pd.DataFrame
    details: Dict[str, Dict[str, Any]]
    phase: str
    analysis_date: Optional[str]
    universe_size: int
    analysed: int
    errors: List[str]
    started_at: datetime
    duration_sec: float


# ============================================================
# YARDIMCILAR
# ============================================================

def _f(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return default
        return out
    except Exception:
        return default


def _ramp(x: Optional[float], x0: float, x1: float, points: float) -> float:
    """x0'da 0, x1'de `points` veren ve sınırlanan doğrusal ölçek."""
    if x is None:
        return 0.0
    if x1 == x0:
        return points if x >= x1 else 0.0
    frac = (x - x0) / (x1 - x0)
    return float(max(0.0, min(1.0, frac)) * points)


def _minute_of_day(ts: pd.Timestamp) -> int:
    return ts.hour * 60 + ts.minute


def market_phase(now_ny: datetime) -> str:
    if now_ny.weekday() >= 5:
        return "closed"
    m = now_ny.hour * 60 + now_ny.minute
    if PRE_START <= m < REG_START:
        return "premarket"
    if REG_START <= m < REG_END:
        return "regular"
    if REG_END <= m < POST_END:
        return "postmarket"
    return "closed"


def expected_volume_share(elapsed_min: float) -> float:
    """Normal seansta geçen süreye göre beklenen kümülatif hacim payı.

    Hacim açılışta yoğundur; doğrusal yerine konkav bir eğri kullanılır
    (ilk 30 dakika ≈ %15, ilk saat ≈ %25, yarı gün ≈ %59).
    """
    frac = max(1.0, elapsed_min) / REG_MINUTES
    return float(min(1.0, frac ** 0.75))


def _fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "-"
    if x >= 1e9:
        return f"${x / 1e9:.1f}B"
    if x >= 1e6:
        return f"${x / 1e6:.0f}M"
    return f"${x:,.0f}"


# ============================================================
# VERİ KAYNAĞI (Yahoo Finance)
# ============================================================

class YahooFetcher:
    """yfinance erişimi. Testlerde sahte bir sınıf ile değiştirilebilir."""

    def __init__(self) -> None:
        import yfinance as yf  # geç import: testler yfinance'sız da çalışsın
        self.yf = yf

    # ---- evren ----
    def screen(self, name: str, count: int = 100) -> List[Dict[str, Any]]:
        yf = self.yf
        if name == "custom_movers":
            q = yf.EquityQuery("and", [
                yf.EquityQuery("eq", ["region", "us"]),
                yf.EquityQuery("gt", ["percentchange", 4]),
                yf.EquityQuery("gte", ["intradayprice", 1]),
                yf.EquityQuery("gt", ["dayvolume", 200_000]),
            ])
            res = yf.screen(q, size=min(count * 2, 250), sortField="percentchange", sortAsc=False)
        elif name == "custom_high_beta":
            q = yf.EquityQuery("and", [
                yf.EquityQuery("eq", ["region", "us"]),
                yf.EquityQuery("gt", ["beta", 1.8]),
                yf.EquityQuery("gt", ["avgdailyvol3m", 1_000_000]),
                yf.EquityQuery("gte", ["intradayprice", 2]),
            ])
            res = yf.screen(q, size=min(count, 250), sortField="percentchange", sortAsc=False)
        else:
            res = yf.screen(name, count=min(count, 250))
        return list((res or {}).get("quotes", []) or [])

    # ---- fiyat ----
    def download(self, symbols: List[str], period: str, interval: str,
                 prepost: bool = False) -> Dict[str, pd.DataFrame]:
        out: Dict[str, pd.DataFrame] = {}
        for i in range(0, len(symbols), 60):
            chunk = symbols[i:i + 60]
            try:
                df = self.yf.download(
                    chunk, period=period, interval=interval, prepost=prepost,
                    group_by="ticker", auto_adjust=False, threads=True,
                    progress=False, ignore_tz=False if interval != "1d" else True,
                )
            except Exception:
                continue
            out.update(split_download(df, chunk))
        return out

    # ---- derin analiz ----
    def info(self, symbol: str) -> Dict[str, Any]:
        try:
            return dict(self.yf.Ticker(symbol).info or {})
        except Exception:
            return {}

    def news(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            raw = self.yf.Ticker(symbol).news or []
        except Exception:
            return []
        return normalise_news(raw)

    def options(self, symbol: str) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, str]]:
        try:
            t = self.yf.Ticker(symbol)
            expiries = list(t.options or [])
            if not expiries:
                return None
            chain = t.option_chain(expiries[0])
            return chain.calls, chain.puts, expiries[0]
        except Exception:
            return None


def split_download(df: Optional[pd.DataFrame], symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """yf.download çıktısını sembol → DataFrame sözlüğüne ayırır."""
    out: Dict[str, pd.DataFrame] = {}
    if df is None or df.empty:
        return out
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = set(df.columns.get_level_values(0))
        lvl1 = set(df.columns.get_level_values(1))
        for s in symbols:
            sub = None
            if s in lvl0:
                sub = df[s]
            elif s in lvl1:
                sub = df.xs(s, axis=1, level=1)
            if sub is None:
                continue
            sub = sub.dropna(how="all")
            if not sub.empty:
                out[s] = sub.copy()
    elif len(symbols) == 1:
        sub = df.dropna(how="all")
        if not sub.empty:
            out[symbols[0]] = sub.copy()
    return out


def normalise_news(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """yfinance'ın eski ve yeni haber biçimlerini tek biçime çevirir."""
    items = []
    for n in raw:
        c = n.get("content") if isinstance(n.get("content"), dict) else n
        title = c.get("title") or ""
        if not title:
            continue
        ts = None
        if c.get("pubDate"):
            try:
                ts = datetime.fromisoformat(str(c["pubDate"]).replace("Z", "+00:00"))
            except Exception:
                ts = None
        elif n.get("providerPublishTime"):
            try:
                ts = datetime.fromtimestamp(int(n["providerPublishTime"]), tz=timezone.utc)
            except Exception:
                ts = None
        url = ""
        if isinstance(c.get("canonicalUrl"), dict):
            url = c["canonicalUrl"].get("url", "")
        elif isinstance(c.get("clickThroughUrl"), dict):
            url = c["clickThroughUrl"].get("url", "")
        else:
            url = n.get("link", "")
        provider = ""
        if isinstance(c.get("provider"), dict):
            provider = c["provider"].get("displayName", "")
        else:
            provider = n.get("publisher", "")
        items.append({
            "title": title,
            "summary": c.get("summary") or "",
            "time": ts,
            "url": url,
            "provider": provider,
        })
    return items


# ============================================================
# HABER / KATALİZÖR SINIFLANDIRMA
# ============================================================

# (etiket, puan, regex) — İngilizce başlıklarda aranır
POSITIVE_CATALYSTS = [
    ("FDA / klinik onay", 12, r"\bfda\b.*(approv|clear|grant|accept)|approval|breakthrough (therapy|device)|positive (topline|phase|data|results)|met (its )?primary endpoint"),
    ("Birleşme / satın alma", 12, r"\bto be acquired\b|\bacquire[sd]?\b|acquisition|\bmerger\b|buyout|takeover|tender offer|go(ing)? private"),
    ("Büyük sözleşme / sipariş", 10, r"\bcontract\b|\bawarded\b|\baward\b|purchase order|\border(s)? (from|worth)|\bdeal\b|supply agreement|\bwins?\b.*\b(deal|contract|order)"),
    ("Güçlü bilanço / beklenti artışı", 10, r"\bbeats?\b|\bbeat estimates\b|tops? (estimates|expectations)|record (revenue|quarter|sales)|rais(es|ed|ing) (its )?(guidance|outlook|forecast)|profit(ability)?\b.*\b(surge|jump|first)|swings? to profit"),
    ("Ortaklık / iş birliği", 8, r"partner(ship)?|collaborat|teams? up|strategic (alliance|agreement)|joins forces"),
    ("Analist yükseltmesi", 6, r"upgrade[sd]?|price target (raised|hike|increase)|raises? (price )?target|initiat\w* (coverage )?.*\b(buy|outperform|overweight)"),
    ("Hisse geri alımı", 5, r"buyback|repurchase"),
    ("Sıcak tema (AI / kuantum / kripto / uzay / nükleer)", 4, r"\bai\b|artificial intelligence|quantum|bitcoin|crypto|nuclear|space|robot|data cent"),
    ("Momentum haberi", 3, r"soar|surge|jump|skyrocket|rall(y|ies)|spike|short squeeze|climb|rocket"),
]

NEGATIVE_CATALYSTS = [
    ("Hisse arzı / sulandırma", -15, r"offering|\bpriced\b|dilut|registered direct|at-the-market|\batm program\b|private placement|warrant"),
    ("Ters bölünme / borsa kotundan çıkma riski", -10, r"reverse (stock )?split|delist|nasdaq (deficiency|notice)|minimum bid"),
    ("İflas / süreklilik riski", -12, r"bankrupt|chapter 11|going concern|default"),
    ("Kötü bilanço / beklenti düşürme", -8, r"\bmiss(es|ed)?\b|lowers? (guidance|outlook)|cuts? (guidance|outlook|forecast)|warns?|disappoint"),
    ("Not indirimi", -6, r"downgrade"),
    ("Dava / soruşturma", -6, r"lawsuit|class action|investigation|subpoena|\bsec\b (probe|charges)|fraud|short seller report"),
]


def classify_news(news: List[Dict[str, Any]], now_utc: datetime,
                  max_age_hours: float = 36.0) -> Dict[str, Any]:
    """Son `max_age_hours` saatteki başlıkları katalizör türlerine ayırır."""
    pos: Dict[str, float] = {}
    neg: Dict[str, float] = {}
    recent: List[Dict[str, Any]] = []
    for item in news:
        ts = item.get("time")
        age_h = None
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_h = (now_utc - ts).total_seconds() / 3600.0
            if age_h > max_age_hours or age_h < -1:
                continue
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        tags = []
        # Yeni haber daha değerli: 0-6 saat tam, 36 saatte yarıya iner
        recency = 1.0 if age_h is None or age_h <= 6 else max(0.5, 1 - (age_h - 6) / 60)
        for label, pts, pattern in POSITIVE_CATALYSTS:
            if re.search(pattern, text):
                pos[label] = max(pos.get(label, 0.0), pts * recency)
                tags.append(label)
        for label, pts, pattern in NEGATIVE_CATALYSTS:
            if re.search(pattern, text):
                neg[label] = min(neg.get(label, 0.0), pts * recency)
                tags.append(label)
        recent.append({**item, "age_h": age_h, "tags": tags})
    # En güçlü iki pozitif katalizör sayılır (aynı haberin tekrarını şişirmemek için)
    pos_sorted = sorted(pos.values(), reverse=True)
    pos_score = sum(pos_sorted[:1]) + 0.5 * sum(pos_sorted[1:2])
    neg_score = sum(sorted(neg.values())[:2])
    return {
        "positive": pos,
        "negative": neg,
        "pos_score": pos_score,
        "neg_score": neg_score,
        "recent": recent,
    }


# ============================================================
# OPSİYON AKIŞI (kurumsal / akıllı para göstergesi)
# ============================================================

def analyse_options(chain: Optional[Tuple[pd.DataFrame, pd.DataFrame, str]],
                    price: Optional[float]) -> Dict[str, Any]:
    out = {"available": False, "call_vol": 0, "put_vol": 0, "cp_ratio": None,
           "unusual_strikes": [], "expiry": None}
    if not chain or price is None:
        return out
    calls, puts, expiry = chain
    if calls is None or calls.empty:
        return out
    out["available"] = True
    out["expiry"] = expiry
    cv = pd.to_numeric(calls.get("volume"), errors="coerce").fillna(0)
    co = pd.to_numeric(calls.get("openInterest"), errors="coerce").fillna(0)
    ks = pd.to_numeric(calls.get("strike"), errors="coerce")
    pv = pd.to_numeric(puts.get("volume"), errors="coerce").fillna(0) if puts is not None and not puts.empty else pd.Series(dtype=float)
    out["call_vol"] = int(cv.sum())
    out["put_vol"] = int(pv.sum())
    out["cp_ratio"] = (out["call_vol"] / out["put_vol"]) if out["put_vol"] > 0 else (float(out["call_vol"]) if out["call_vol"] else None)
    # Fiyatın üzerindeki strike'larda hacim > 2 × açık pozisyon ve ≥ 500 kontrat
    mask = (ks >= price) & (cv >= 500) & (cv > 2 * co)
    out["unusual_strikes"] = [
        {"strike": float(k), "volume": int(v), "oi": int(o)}
        for k, v, o in zip(ks[mask], cv[mask], co[mask])
    ][:6]
    return out


# ============================================================
# ÖZELLİK ÇIKARIMI
# ============================================================

def _ensure_ny(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert(NY)
    return df


def _rsi(closes: pd.Series, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] > 0 else np.inf
    return float(100 - 100 / (1 + rs))


def compute_features(symbol: str, quote: Dict[str, Any],
                     daily: Optional[pd.DataFrame],
                     intraday: Optional[pd.DataFrame],
                     now_ny: datetime) -> Optional[Dict[str, Any]]:
    q = quote or {}
    f: Dict[str, Any] = {"symbol": symbol,
                         "name": q.get("shortName") or q.get("longName") or symbol}

    # ---------------- gün içi ----------------
    day = pd.DataFrame()
    analysis_date = now_ny.date()
    if intraday is not None and not intraday.empty:
        intr = _ensure_ny(intraday).dropna(subset=["Close"])
        if not intr.empty:
            analysis_date = intr.index[-1].date()
            day = intr[intr.index.date == analysis_date]
    f["analysis_date"] = analysis_date

    mins = np.array([_minute_of_day(t) for t in day.index]) if not day.empty else np.array([])
    pre = day[(mins >= PRE_START) & (mins < REG_START)] if len(mins) else day
    reg = day[(mins >= REG_START) & (mins < REG_END)] if len(mins) else day
    post = day[mins >= REG_END] if len(mins) else day

    phase = market_phase(now_ny) if analysis_date == now_ny.date() else "closed"
    f["phase"] = phase

    # ---------------- günlük (önceki günler) ----------------
    prior = pd.DataFrame()
    if daily is not None and not daily.empty:
        d = daily.dropna(subset=["Close"]).copy()
        didx = pd.DatetimeIndex(d.index)
        if didx.tz is not None:
            didx = didx.tz_convert(NY).tz_localize(None)
        d.index = didx
        prior = d[d.index.date < analysis_date]

    prev_close = _f(prior["Close"].iloc[-1]) if not prior.empty else _f(q.get("regularMarketPreviousClose"))
    if prev_close is None or prev_close <= 0:
        return None
    f["prev_close"] = prev_close

    # ---------------- fiyat seviyeleri ----------------
    last_any = _f(day["Close"].iloc[-1]) if not day.empty else None
    open_px = _f(reg["Open"].iloc[0]) if not reg.empty else None
    reg_last = _f(reg["Close"].iloc[-1]) if not reg.empty else None

    if open_px is None and phase in ("regular", "postmarket", "closed"):
        open_px = _f(q.get("regularMarketOpen"))
    if reg_last is None and phase in ("regular", "postmarket", "closed"):
        reg_last = _f(q.get("regularMarketPrice"))

    if phase == "premarket":
        price = last_any if last_any is not None else _f(q.get("preMarketPrice"), _f(q.get("regularMarketPrice")))
    else:
        price = reg_last if reg_last is not None else last_any
    if price is None or price <= 0:
        return None
    f["price"] = price
    f["open"] = open_px
    f["last_any"] = last_any if last_any is not None else price

    f["gap_pct"] = (open_px / prev_close - 1) if open_px else None
    f["change_from_open"] = (reg_last / open_px - 1) if (open_px and reg_last) else None
    f["change_from_prev"] = price / prev_close - 1
    if not pre.empty:
        f["pm_change"] = _f(pre["Close"].iloc[-1]) / prev_close - 1
    else:
        pm_q = _f(q.get("preMarketChangePercent"))
        f["pm_change"] = pm_q / 100.0 if pm_q is not None else None
    f["post_change"] = (_f(post["Close"].iloc[-1]) / reg_last - 1) if (not post.empty and reg_last) else None

    # Referans fiyat: açılış (yoksa pre-market'te önceki kapanış)
    ref = open_px if open_px else prev_close
    f["target_ref"] = ref
    f["target_ref_label"] = "Açılış" if open_px else "Önceki kapanış"
    for p in (10, 15, 20):
        f[f"t{p}"] = ref * (1 + p / 100)
    hod_src = reg if not reg.empty else pre
    f["hod"] = _f(hod_src["High"].max()) if not hod_src.empty else _f(q.get("regularMarketDayHigh"), price)
    f["max_from_open"] = (f["hod"] / open_px - 1) if (open_px and f["hod"]) else None

    # ---------------- hacim ----------------
    avg_vol = _f(prior["Volume"].iloc[-20:].mean()) if len(prior) >= 5 else None
    if not avg_vol:
        avg_vol = _f(q.get("averageDailyVolume10Day")) or _f(q.get("averageDailyVolume3Month"))
    f["avg_vol"] = avg_vol
    reg_vol = _f(reg["Volume"].sum(), 0.0) if not reg.empty else _f(q.get("regularMarketVolume"), 0.0)
    pre_vol = _f(pre["Volume"].sum(), 0.0) if not pre.empty else 0.0
    f["reg_vol"] = reg_vol
    f["pre_vol"] = pre_vol

    rvol = None
    if avg_vol and avg_vol > 0:
        if phase == "premarket":
            # pre-market hacmi normalde günlük hacmin ~%3'ü
            rvol = (pre_vol / avg_vol) / 0.03 if pre_vol else 0.0
        else:
            if phase == "regular":
                elapsed = _minute_of_day(now_ny) - REG_START
            else:
                elapsed = REG_MINUTES
            expected = avg_vol * expected_volume_share(elapsed)
            rvol = reg_vol / expected if expected > 0 else None
    f["rvol"] = rvol
    vol_for_dollars = pre_vol if phase == "premarket" else reg_vol
    f["dollar_volume"] = (vol_for_dollars or 0) * price

    # ---------------- gün içi teknik ----------------
    f["vwap"] = None
    f["orh"] = f["orl"] = None
    f["mom30"] = None
    f["vol_accel"] = None
    if not reg.empty:
        tp = (reg["High"] + reg["Low"] + reg["Close"]) / 3
        v = reg["Volume"].fillna(0)
        if v.sum() > 0:
            f["vwap"] = float((tp * v).sum() / v.sum())
        first = reg.iloc[:3]
        f["orh"] = _f(first["High"].max())
        f["orl"] = _f(first["Low"].min())
    seg = reg if not reg.empty else pre
    if len(seg) >= 7:
        f["mom30"] = float(seg["Close"].iloc[-1] / seg["Close"].iloc[-7] - 1)
    if len(seg) >= 9:
        recent = seg["Volume"].iloc[-3:].mean()
        base = seg["Volume"].iloc[:-3].mean()
        f["vol_accel"] = float(recent / base) if base and base > 0 else None
    f["pm_high"] = _f(pre["High"].max()) if not pre.empty else None

    # ---------------- günlük teknik ----------------
    f.update({"atr_pct": None, "high20": None, "high52": None, "prev_high": None,
              "big_days": 0, "rsi": None, "ema_stack": False, "squeeze": False,
              "bb_pct": None, "history_days": len(prior)})
    if len(prior) >= 15:
        h, l, c = prior["High"], prior["Low"], prior["Close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        f["atr_pct"] = float(tr.iloc[-14:].mean() / prev_close)
        f["high20"] = float(h.iloc[-20:].max())
        f["high52"] = float(h.iloc[-252:].max())
        f["prev_high"] = float(h.iloc[-1])
        o = prior["Open"].replace(0, np.nan)
        f["big_days"] = int(((h / o - 1) >= 0.10).iloc[-120:].sum())
        closes = pd.concat([c, pd.Series([price])], ignore_index=True)
        f["rsi"] = _rsi(closes)
        if len(closes) >= 50:
            e9 = closes.ewm(span=9, adjust=False).mean().iloc[-1]
            e20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
            e50 = closes.ewm(span=50, adjust=False).mean().iloc[-1]
            f["ema_stack"] = bool(price > e9 > e20 > e50)
        if len(c) >= 60:
            mid = c.rolling(20).mean()
            width = (c.rolling(20).std() * 4 / mid).dropna()
            hist = width.iloc[-120:]
            if len(hist) >= 30:
                # Dünkü bant genişliği son 120 günün en dar %20'sinde mi?
                pct = float((hist < hist.iloc[-1]).mean())
                f["bb_pct"] = pct
                f["squeeze"] = pct <= 0.20

    # ---------------- temel / quote ----------------
    f["market_cap"] = _f(q.get("marketCap"))
    f["float_shares"] = None
    f["short_float"] = None
    f["inst_pct"] = None
    f["earnings_ts"] = None
    for key in ("earningsTimestamp", "earningsTimestampStart"):
        ts = _f(q.get(key))
        if ts:
            f["earnings_ts"] = datetime.fromtimestamp(ts, tz=timezone.utc)
            break
    f["sources"] = list(q.get("_sources", []))
    return f


def apply_info(f: Dict[str, Any], info: Dict[str, Any]) -> None:
    if not info:
        return
    if not f.get("market_cap"):
        f["market_cap"] = _f(info.get("marketCap"))
    f["float_shares"] = _f(info.get("floatShares"))
    sf = _f(info.get("shortPercentOfFloat"))
    f["short_float"] = sf
    f["inst_pct"] = _f(info.get("heldPercentInstitutions"))
    f["sector"] = info.get("sector") or ""
    f["industry"] = info.get("industry") or ""
    if not f.get("earnings_ts"):
        ts = _f(info.get("earningsTimestamp")) or _f(info.get("earningsTimestampStart"))
        if ts:
            f["earnings_ts"] = datetime.fromtimestamp(ts, tz=timezone.utc)
    if f["name"] == f["symbol"]:
        f["name"] = info.get("shortName") or info.get("longName") or f["name"]


# ============================================================
# PUANLAMA (100 puan)
#   Momentum 20 · Hacim 20 · Teknik 20 · Patlama potansiyeli 15
#   Katalizör 15 · Akıllı para / squeeze 10 · Cezalar (-)
# ============================================================

def score_candidate(f: Dict[str, Any], now_utc: datetime) -> Dict[str, Any]:
    signals: List[str] = []
    risks: List[str] = []
    b: Dict[str, float] = {}
    phase = f["phase"]
    price = f["price"]
    pre = phase == "premarket"

    # ---------- 1. Momentum (20) ----------
    if pre:
        pm = f.get("pm_change") or 0.0
        m = _ramp(pm, 0.02, 0.15, 16)
        if pm >= 0.04:
            signals.append(f"Pre-market %{pm * 100:+.1f}")
    else:
        cfo = f.get("change_from_open")
        gap = f.get("gap_pct")
        m = _ramp(cfo, 0.0, 0.10, 14)
        if gap is not None and gap > 0.02 and (cfo or 0) > 0:
            m += _ramp(gap, 0.02, 0.12, 4)
            signals.append(f"Gap-up %{gap * 100:.1f} ve açılışın üzerinde tutunuyor")
        if cfo is not None and cfo >= 0.03:
            signals.append(f"Açılıştan %{cfo * 100:+.1f}")
    mom30 = f.get("mom30")
    if mom30 is not None and mom30 > 0.01:
        m += _ramp(mom30, 0.01, 0.04, 2)
        signals.append(f"Son 30 dk ivmesi %{mom30 * 100:+.1f}")
    b["Momentum"] = min(20.0, m)

    # ---------- 2. Hacim / RVOL (20) ----------
    rvol = f.get("rvol")
    v = 0.0
    if rvol and rvol > 1:
        v = 17.0 * min(1.0, math.log(rvol) / math.log(10))
    accel = f.get("vol_accel")
    if accel and accel > 1.5:
        v += _ramp(accel, 1.5, 3.0, 3)
        signals.append(f"Hacim hızlanıyor (son 15 dk {accel:.1f}x)")
    if rvol and rvol >= 2:
        label = "Pre-market hacim" if pre else "Göreceli hacim (RVOL)"
        signals.append(f"{label} normalin {rvol:.1f} katı")
    b["Hacim"] = min(20.0, v)

    # ---------- 3. Teknik yapı (20) ----------
    t = 0.0
    vwap = f.get("vwap")
    if not pre:
        if vwap and price > vwap:
            t += 4
            signals.append(f"VWAP (${vwap:.2f}) üzerinde")
        elif vwap:
            risks.append(f"VWAP (${vwap:.2f}) altında — alıcılar zayıf")
        if f.get("orh") and price > f["orh"]:
            t += 3
            signals.append("Açılış aralığı (ilk 15 dk) kırıldı")
    else:
        if f.get("prev_high") and price > f["prev_high"]:
            t += 4
            signals.append("Önceki gün zirvesinin üzerinde")
        if f.get("pm_high") and price >= f["pm_high"] * 0.98:
            t += 3
    hod = f.get("hod")
    if hod and price >= hod * 0.98:
        t += 3
        signals.append("Gün zirvesine yakın (≤%2)")
    if f.get("high20") and price > f["high20"]:
        t += 4
        signals.append("20 günlük zirve kırıldı")
        if f.get("high52") and price > f["high52"]:
            t += 2
            signals.append("52 haftalık zirve kırıldı (üstte direnç yok)")
    if f.get("ema_stack"):
        t += 2
    rsi = f.get("rsi")
    if rsi is not None:
        if 60 <= rsi <= 85:
            t += 2
            signals.append(f"RSI {rsi:.0f} — güçlü alım baskısı")
        elif rsi > 90:
            risks.append(f"RSI {rsi:.0f} — aşırı ısınma, sert geri çekilme riski")
    b["Teknik"] = min(20.0, t)

    # ---------- 4. Patlama potansiyeli (15) ----------
    p = 0.0
    bd = f.get("big_days") or 0
    p += _ramp(bd, 0, 6, 7)
    if bd >= 2:
        signals.append(f"Son 6 ayda {bd} kez gün içinde açılıştan %10+ yükselmiş")
    atr = f.get("atr_pct")
    p += _ramp(atr, 0.02, 0.10, 4)
    mc = f.get("market_cap")
    if mc:
        p += 2 if mc < 300e6 else 1.5 if mc < 2e9 else 0.5 if mc < 10e9 else 0
    fl = f.get("float_shares")
    if fl:
        p += 2 if fl < 20e6 else 1 if fl < 100e6 else 0
        if fl < 20e6:
            signals.append(f"Düşük float ({fl / 1e6:.1f}M hisse) — hızlı hareket edebilir")
    b["Potansiyel"] = min(15.0, p)

    # ---------- 5. Katalizör (15) ----------
    c = 0.0
    news = f.get("news_info")
    if news:
        c += min(12.0, news["pos_score"])
        for label in sorted(news["positive"], key=news["positive"].get, reverse=True)[:2]:
            signals.append(f"Haber: {label}")
    ets = f.get("earnings_ts")
    if ets is not None:
        hrs = (now_utc - ets).total_seconds() / 3600.0
        if -24 <= hrs <= 40:
            c += 5
            signals.append("Bilanço açıklaması (dün / bugün / yarın)")
    b["Katalizör"] = min(15.0, c)

    # ---------- 6. Akıllı para / squeeze (10) ----------
    s = 0.0
    opt = f.get("options_info")
    if opt and opt.get("available"):
        n_unusual = len(opt["unusual_strikes"])
        if n_unusual:
            s += 4 if n_unusual < 3 else 6
            top = opt["unusual_strikes"][0]
            signals.append(
                f"Olağandışı CALL alımı: {n_unusual} strike "
                f"(ör. ${top['strike']:.2f} → {top['volume']:,} kontrat / {top['oi']:,} açık poz.)"
            )
        cp = opt.get("cp_ratio")
        if cp and cp >= 3 and opt["call_vol"] >= 2000:
            s += 2
            signals.append(f"Call/Put hacim oranı {cp:.1f}")
    sf = f.get("short_float")
    if sf:
        if sf >= 0.20:
            s += 3
            signals.append(f"Açığa satış %{sf * 100:.0f} (float) — short squeeze potansiyeli")
        elif sf >= 0.10:
            s += 1.5
    breaking_out = (f.get("high20") and price > f["high20"]) or (f.get("change_from_open") or f.get("pm_change") or 0) >= 0.05
    if f.get("squeeze") and breaking_out:
        s += 2
        signals.append("Bollinger sıkışması sonrası kırılım")
    if rvol and rvol >= 3 and vwap and price > vwap and (f.get("dollar_volume") or 0) >= 50e6:
        s += 2
        signals.append(f"Yüksek dolar hacmi ({_fmt_money(f['dollar_volume'])}) VWAP üstünde — büyük alıcı izi")
    b["Akıllı para"] = min(10.0, s)

    # ---------- Cezalar ----------
    pen = 0.0
    if news and news["neg_score"] < 0:
        pen += news["neg_score"]
        for label in news["negative"]:
            risks.append(f"Haber: {label}")
    cfo = f.get("change_from_open")
    if cfo is not None:
        if cfo >= 0.50:
            pen -= 10
            risks.append(f"Açılıştan %{cfo * 100:.0f} — çok uzamış, geç kalınmış olabilir")
        elif cfo >= 0.30:
            pen -= 5
            risks.append(f"Açılıştan %{cfo * 100:.0f} — uzamış, kâr satışı riski")
    if hod and price < hod * 0.92 and not pre:
        pen -= 6
        risks.append(f"Gün zirvesinden %{(1 - price / hod) * 100:.0f} geri çekilmiş — momentum sönüyor")
    if cfo is not None and cfo < -0.02:
        pen -= 5
        risks.append("Açılışın altında işlem görüyor")
    if price < 2:
        pen -= 3
        risks.append("Fiyat $2 altında — penny stock riski, geniş alış-satış farkı")
    if f.get("history_days", 0) < 30:
        risks.append("Kısa işlem geçmişi (yeni halka arz olabilir)")
    if (f.get("atr_pct") or 0) > 0.15:
        risks.append(f"Çok yüksek oynaklık (ATR %{f['atr_pct'] * 100:.0f}) — sert düşüşler de olası")
    b["Ceza"] = pen

    total = sum(v for k, v in b.items())
    total = float(max(0.0, min(100.0, total)))

    if total >= 70:
        grade = "A"
    elif total >= 55:
        grade = "B"
    elif total >= 40:
        grade = "C"
    else:
        grade = "D"

    # Hangi hedefler gerçekleşti?
    hit = []
    mfo = f.get("max_from_open")
    if mfo is not None:
        for p_ in (10, 15, 20):
            if mfo >= p_ / 100:
                hit.append(f"+%{p_}")

    # İzleme seviyeleri (tavsiye değildir)
    stop_candidates = [x for x in (vwap, f.get("orl")) if x and x < price]
    stop = max(stop_candidates) if stop_candidates else price * (1 - max(0.04, min(0.10, (atr or 0.05))))
    return {
        "score": round(total, 1),
        "grade": grade,
        "breakdown": {k: round(v, 1) for k, v in b.items()},
        "signals": signals,
        "risks": risks,
        "targets_hit": hit,
        "stop_level": stop,
        "stop_pct": stop / price - 1,
    }


def _prescore(f: Dict[str, Any]) -> float:
    """Derin analiz öncesi kaba sıralama (haber/opsiyon olmadan)."""
    tmp = score_candidate(f, datetime.now(timezone.utc))
    return tmp["score"]


# ============================================================
# ANA TARAMA
# ============================================================

def _quote_prerank(q: Dict[str, Any]) -> float:
    chg = _f(q.get("regularMarketChangePercent"), 0.0) or 0.0
    pm = _f(q.get("preMarketChangePercent"), 0.0) or 0.0
    vol = _f(q.get("regularMarketVolume"), 0.0) or 0.0
    avg = _f(q.get("averageDailyVolume10Day")) or _f(q.get("averageDailyVolume3Month")) or 0.0
    rv = vol / avg if avg else 0.0
    return max(chg, pm) + 5 * math.log1p(rv)


def run_scan(settings: Optional[ScanSettings] = None,
             fetcher: Any = None,
             progress: Optional[Callable[[float, str], None]] = None,
             now: Optional[datetime] = None) -> ScanResult:
    settings = settings or ScanSettings()
    t0 = time.time()
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_ny = now_utc.astimezone(NY)
    errors: List[str] = []

    def report(frac: float, msg: str) -> None:
        if progress:
            try:
                progress(frac, msg)
            except Exception:
                pass

    if fetcher is None:
        fetcher = YahooFetcher()

    # ---------------- 1. Evren ----------------
    quotes: Dict[str, Dict[str, Any]] = {}
    if settings.include_screens:
        names = ["day_gainers", "small_cap_gainers", "most_actives",
                 "aggressive_small_caps", "most_shorted_stocks",
                 "custom_movers", "custom_high_beta"]
        for i, name in enumerate(names):
            report(0.02 + 0.13 * i / len(names), f"Evren taranıyor: {SCREEN_LABELS[name]}")
            try:
                rows = fetcher.screen(name, count=100)
            except Exception as exc:
                errors.append(f"{SCREEN_LABELS[name]}: {exc}")
                continue
            for r in rows:
                sym = r.get("symbol")
                if not sym or r.get("quoteType", "EQUITY") != "EQUITY":
                    continue
                if any(ch in sym for ch in ("^", "=")):
                    continue
                entry = quotes.setdefault(sym, dict(r))
                entry.setdefault("_sources", [])
                if SCREEN_LABELS[name] not in entry["_sources"]:
                    entry["_sources"].append(SCREEN_LABELS[name])

    watch = [s.strip().upper() for s in settings.watchlist if s and s.strip()]

    # Kaba eleme: fiyat ve ortalama hacim (quote verisinden)
    def quote_ok(q: Dict[str, Any]) -> bool:
        px = _f(q.get("regularMarketPrice"))
        if px is not None and not (settings.min_price <= px <= settings.max_price):
            return False
        avg = _f(q.get("averageDailyVolume3Month")) or _f(q.get("averageDailyVolume10Day"))
        if avg is not None and avg < settings.min_avg_volume * 0.5:
            return False
        return True

    ranked = sorted((s for s, q in quotes.items() if quote_ok(q)),
                    key=lambda s: _quote_prerank(quotes[s]), reverse=True)
    universe = ranked[: settings.max_universe]
    for s in watch:
        if s not in universe:
            universe.append(s)
        q = quotes.setdefault(s, {"symbol": s})
        q.setdefault("_sources", [])
        if SCREEN_LABELS["watchlist"] not in q["_sources"]:
            q["_sources"].append(SCREEN_LABELS["watchlist"])
    universe_size = len(quotes)

    if not universe:
        return ScanResult(pd.DataFrame(), {}, market_phase(now_ny), None, 0, 0,
                          errors or ["Evren boş — veri kaynağına ulaşılamadı."],
                          now_utc, time.time() - t0)

    # ---------------- 2. Fiyat verisi ----------------
    report(0.18, f"{len(universe)} hisse için günlük veriler indiriliyor")
    try:
        daily = fetcher.download(universe, period="1y", interval="1d")
    except Exception as exc:
        daily = {}
        errors.append(f"Günlük veri: {exc}")
    report(0.40, f"{len(universe)} hisse için 5 dakikalık veriler indiriliyor")
    try:
        intraday = fetcher.download(universe, period="5d", interval="5m", prepost=True)
    except Exception as exc:
        intraday = {}
        errors.append(f"Gün içi veri: {exc}")

    # ---------------- 3. Özellikler + filtre ----------------
    report(0.62, "Teknik göstergeler hesaplanıyor")
    feats: Dict[str, Dict[str, Any]] = {}
    for s in universe:
        try:
            f = compute_features(s, quotes.get(s, {}), daily.get(s), intraday.get(s), now_ny)
        except Exception as exc:
            errors.append(f"{s}: {exc}")
            continue
        if not f:
            continue
        is_watch = s in watch
        if not (settings.min_price <= f["price"] <= settings.max_price):
            continue
        if not is_watch:
            if (f.get("avg_vol") or 0) < settings.min_avg_volume:
                continue
            min_dv = settings.min_dollar_volume * (0.1 if f["phase"] == "premarket" else 1.0)
            if (f.get("dollar_volume") or 0) < min_dv:
                continue
        feats[s] = f

    # ---------------- 4. Derin analiz ----------------
    pre_scores = {s: _prescore(f) for s, f in feats.items()}
    deep = sorted(pre_scores, key=pre_scores.get, reverse=True)[: settings.deep_count]
    report(0.70, f"En iyi {len(deep)} aday için haber / opsiyon / float verisi")

    def deep_one(sym: str) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]], Any]:
        info = fetcher.info(sym)
        news = fetcher.news(sym) if settings.include_news else []
        opt = fetcher.options(sym) if settings.include_options else None
        return sym, info, news, opt

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for sym, info, news, opt in pool.map(deep_one, deep):
            f = feats[sym]
            try:
                apply_info(f, info)
                if settings.include_news:
                    f["news_info"] = classify_news(news, now_utc)
                if settings.include_options:
                    f["options_info"] = analyse_options(opt, f["price"])
            except Exception as exc:
                errors.append(f"{sym} derin analiz: {exc}")
            done += 1
            report(0.70 + 0.27 * done / max(1, len(deep)), f"Derin analiz: {sym}")

    # ---------------- 5. Puanlama ----------------
    rows = []
    details: Dict[str, Dict[str, Any]] = {}
    for s, f in feats.items():
        sc = score_candidate(f, now_utc)
        f["deep"] = s in deep
        details[s] = {"features": f, "score": sc}
        rows.append({
            "Sembol": s,
            "Şirket": f["name"],
            "Puan": sc["score"],
            "Sınıf": sc["grade"],
            "Fiyat": round(f["price"], 2),
            "Açılıştan %": None if f.get("change_from_open") is None else round(f["change_from_open"] * 100, 1),
            "Gap %": None if f.get("gap_pct") is None else round(f["gap_pct"] * 100, 1),
            "Pre-mkt %": None if f.get("pm_change") is None else round(f["pm_change"] * 100, 1),
            "Önceki kapanıştan %": round(f["change_from_prev"] * 100, 1),
            "RVOL": None if f.get("rvol") is None else round(f["rvol"], 1),
            "Dolar hacmi": f.get("dollar_volume"),
            "Piyasa değeri": f.get("market_cap"),
            "Hedef +%10": round(f["t10"], 2),
            "Hedef +%15": round(f["t15"], 2),
            "Hedef +%20": round(f["t20"], 2),
            "Ulaşılan": " ".join(sc["targets_hit"]) or "-",
            "Öne çıkan": " · ".join(sc["signals"][:3]),
            "Risk": " · ".join(sc["risks"][:2]),
            "Kaynak": ", ".join(f.get("sources", [])),
        })
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values("Puan", ascending=False).reset_index(drop=True)
        table.index = table.index + 1

    phase = market_phase(now_ny)
    a_date = None
    if feats:
        a_date = str(max(f["analysis_date"] for f in feats.values()))
    report(1.0, "Tamamlandı")
    return ScanResult(table, details, phase, a_date, universe_size, len(feats),
                      errors, now_utc, time.time() - t0)
