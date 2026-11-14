# ============================================================
# BIST Tavan Radarı — Tarama orkestrasyonu
# fiyat verisi -> teknik skor -> (en iyi N hisse için) haber skoru
# ============================================================

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import pandas as pd

from .scoring import ScanResult, analyze, apply_news


def scan(
    codes: list[str],
    price_fetcher: Callable[[list[str]], dict[str, pd.DataFrame]],
    news_fetcher: Callable[[str], list[dict]] | None = None,
    news_top_n: int = 15,
) -> list[ScanResult]:
    data = price_fetcher(codes)
    results = [analyze(code, data.get(code)) for code in codes]

    if news_fetcher and news_top_n > 0:
        ranked = sorted(
            (r for r in results if not r.error),
            key=lambda r: r.technical_score,
            reverse=True,
        )[:news_top_n]

        def _safe(code: str) -> list[dict]:
            try:
                return news_fetcher(code)
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=6) as pool:
            news_lists = list(pool.map(_safe, [r.code for r in ranked]))
        for r, items in zip(ranked, news_lists):
            apply_news(r, items)

    results.sort(key=lambda r: (r.error == "", r.at_ceiling, r.score), reverse=True)
    return results


def to_frame(results: list[ScanResult]) -> pd.DataFrame:
    rows = [r.as_row() for r in results if not r.error]
    return pd.DataFrame(rows)
