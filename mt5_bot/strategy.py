# ============================================================
# MT5 Endeks Botu — Strateji (trend + kırılım)
#
# ALIŞ : Kapanış > son N barın en yükseği  VE  EMA50 > EMA200  VE  Kapanış > EMA50
# SATIŞ: Kapanış < son N barın en düşüğü   VE  EMA50 < EMA200  VE  Kapanış < EMA50
# Zarar kes / kâr al ATR'ye göre (piyasanın o anki oynaklığına göre) belirlenir.
#
# Girdi DataFrame yalnızca KAPANMIŞ barları içermelidir:
#   index = bar zamanı, sütunlar = open, high, low, close
# ============================================================

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import BotConfig


@dataclass
class Signal:
    direction: str      # "BUY" / "SELL"
    ref_price: float    # sinyal barının kapanışı
    sl_distance: float  # fiyat birimi
    tp_distance: float
    atr: float
    reason: str


def add_indicators(df: pd.DataFrame, cfg: BotConfig) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = out["close"].ewm(span=cfg.ema_fast, adjust=False).mean()
    out["ema_slow"] = out["close"].ewm(span=cfg.ema_slow, adjust=False).mean()
    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / cfg.atr_period, adjust=False).mean()
    # Bu bar HARİÇ önceki N bar
    out["brk_high"] = out["high"].shift(1).rolling(cfg.breakout_bars).max()
    out["brk_low"] = out["low"].shift(1).rolling(cfg.breakout_bars).min()
    return out


def min_bars(cfg: BotConfig) -> int:
    return max(cfg.ema_slow, cfg.breakout_bars + 1, cfg.atr_period) + 5


def signal_from_row(row: pd.Series, cfg: BotConfig) -> Signal | None:
    vals = row[["close", "ema_fast", "ema_slow", "atr", "brk_high", "brk_low"]]
    if vals.isna().any() or row["atr"] <= 0:
        return None
    c, ef, es, atr = row["close"], row["ema_fast"], row["ema_slow"], row["atr"]
    sl, tp = cfg.sl_atr * atr, cfg.tp_atr * atr

    if c > row["brk_high"] and ef > es and c > ef:
        return Signal("BUY", c, sl, tp, atr,
                      f"{cfg.breakout_bars} bar zirvesi ({row['brk_high']:.2f}) kırıldı, trend yukarı")
    if cfg.allow_short and c < row["brk_low"] and ef < es and c < ef:
        return Signal("SELL", c, sl, tp, atr,
                      f"{cfg.breakout_bars} bar dibi ({row['brk_low']:.2f}) kırıldı, trend aşağı")
    return None


def latest_signal(closed_bars: pd.DataFrame, cfg: BotConfig) -> Signal | None:
    if closed_bars is None or len(closed_bars) < min_bars(cfg):
        return None
    ind = add_indicators(closed_bars, cfg)
    return signal_from_row(ind.iloc[-1], cfg)
