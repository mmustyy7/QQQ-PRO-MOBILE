# ============================================================
# BIST Tavan Radarı — Fiyat verisi (Yahoo Finance / yfinance)
#
# Ücretsiz kaynak: BIST verisi ~15 dk GECİKMELİDİR.
# Gerçek zamanlı veri / AKD (aracı kurum dağılımı) için lisanslı
# bir sağlayıcı (Matriks, Foreks, İdeal, vb.) adaptörü yazılmalıdır.
# Bu modül tek bir fonksiyon döndürür: {kod: DataFrame}
# ============================================================

from __future__ import annotations

import pandas as pd

from .symbols import to_yahoo

FIELDS = ["Open", "High", "Low", "Close", "Volume"]


def _split_download(raw: pd.DataFrame, codes: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return out
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(raw.columns.get_level_values(0))
        for code in codes:
            yt = to_yahoo(code)
            if yt in level0:
                sub = raw[yt]
            elif code in level0:
                sub = raw[code]
            else:
                continue
            sub = sub[[c for c in FIELDS if c in sub.columns]].dropna(how="all")
            if not sub.empty:
                out[code] = sub
    elif len(codes) == 1:
        sub = raw[[c for c in FIELDS if c in raw.columns]].dropna(how="all")
        if not sub.empty:
            out[codes[0]] = sub
    return out


def fetch_daily(codes: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Tüm hisseler için günlük OHLCV verisini tek seferde indirir."""
    import yfinance as yf

    if not codes:
        return {}
    raw = yf.download(
        tickers=[to_yahoo(c) for c in codes],
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )
    return _split_download(raw, codes)
