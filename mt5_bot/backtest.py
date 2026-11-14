# ============================================================
# MT5 Endeks Botu — Geriye dönük test (backtest)
#
# Sonuçlar "R" cinsindendir: 1R = işlem başına riske edilen tutar.
# Örn. toplam +12R ve işlem başı risk %0.5 => yaklaşık +%6.
# Basit bir simülasyondur: kayma (slippage), swap ve fiyat boşlukları
# tam modellenmez; aynı barda hem SL hem TP görülürse SL varsayılır.
# ============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta

import numpy as np
import pandas as pd

from .config import BotConfig
from .strategy import add_indicators, min_bars, signal_from_row


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


@dataclass
class Trade:
    direction: str
    entry_time: pd.Timestamp
    entry: float
    sl: float
    tp: float
    exit_time: pd.Timestamp | None = None
    exit: float | None = None
    result_r: float = 0.0
    exit_reason: str = ""


def run_backtest(bars: pd.DataFrame, cfg: BotConfig) -> tuple[list[Trade], dict]:
    df = add_indicators(bars, cfg)
    ny_times = df.index - timedelta(hours=cfg.server_minus_ny_hours)
    start, end, eod = _t(cfg.entry_start_ny), _t(cfg.entry_end_ny), _t(cfg.close_eod_ny)
    spread = cfg.backtest_spread_points

    trades: list[Trade] = []
    pos: Trade | None = None
    risk = 0.0
    day_trades: dict = {}

    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    for i in range(min_bars(cfg), len(df) - 1):
        t_ny = ny_times[i]

        # --- açık pozisyon yönetimi (bar i içinde)
        if pos is not None:
            long = pos.direction == "BUY"
            hit_sl = l[i] <= pos.sl if long else h[i] >= pos.sl
            hit_tp = h[i] >= pos.tp if long else l[i] <= pos.tp
            exit_px, why = None, ""
            if hit_sl:
                exit_px, why = pos.sl, "SL"
            elif hit_tp:
                exit_px, why = pos.tp, "TP"
            elif cfg.close_eod and t_ny.time() >= eod:
                exit_px, why = c[i], "gün sonu"
            if exit_px is not None:
                pnl = (exit_px - pos.entry) if long else (pos.entry - exit_px)
                pos.exit, pos.exit_time, pos.exit_reason = exit_px, df.index[i], why
                pos.result_r = pnl / risk
                trades.append(pos)
                pos = None
            continue

        # --- yeni sinyal (bar i kapandı -> bar i+1 açılışında giriş)
        if t_ny.weekday() >= 5 or not (start <= t_ny.time() <= end):
            continue
        d = t_ny.date()
        if day_trades.get(d, 0) >= cfg.max_trades_per_day:
            continue
        sig = signal_from_row(df.iloc[i], cfg)
        if sig is None:
            continue
        if sig.direction == "BUY":
            entry = o[i + 1] + spread
            pos = Trade("BUY", df.index[i + 1], entry, entry - sig.sl_distance, entry + sig.tp_distance)
        else:
            entry = o[i + 1] - spread
            pos = Trade("SELL", df.index[i + 1], entry, entry + sig.sl_distance, entry - sig.tp_distance)
        risk = sig.sl_distance
        day_trades[d] = day_trades.get(d, 0) + 1

    return trades, summarize(trades, cfg)


def summarize(trades: list[Trade], cfg: BotConfig) -> dict:
    if not trades:
        return {"işlem": 0}
    r = np.array([t.result_r for t in trades])
    equity = np.cumsum(r)
    peak = np.maximum.accumulate(np.concatenate([[0.0], equity]))[1:]
    wins, losses = r[r > 0], r[r <= 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
    return {
        "işlem": len(r),
        "kazanma oranı %": round(len(wins) / len(r) * 100, 1),
        "ortalama R": round(r.mean(), 3),
        "toplam R": round(r.sum(), 2),
        "kâr faktörü": round(pf, 2),
        "en büyük düşüş R": round((peak - equity).max(), 2),
        "yaklaşık getiri %": round(r.sum() * cfg.risk_per_trade_pct, 2),
        "yaklaşık en büyük düşüş %": round((peak - equity).max() * cfg.risk_per_trade_pct, 2),
    }
