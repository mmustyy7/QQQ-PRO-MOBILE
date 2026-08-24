from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict

import numpy as np
import pandas as pd


ENGINE_NAME = "QQQ PRO Opportunity Candidate Engine"
ENGINE_VERSION = "1.0-shadow"

OPENING_CONFIRM_MINUTES = 5
NORMAL_CONFIRM_MINUTES = 10
CANDIDATE_MIN_SCORE = 3
CONFIRM_MIN_GROUPS = 5
CONFIRM_CONSECUTIVE_BARS = 1
COOLDOWN_MINUTES = 45
CANDIDATE_REARM_MINUTES = 10

RANGE_MIN_VOLUME_RATIO = 1.35
RANGE_MIN_EMA_GAP_PCT = 0.025
RANGE_MIN_VWAP_DISTANCE_PCT = 0.18
RANGE_MIN_MOMENTUM_DOLLARS = 0.55
RANGE_MIN_ACCELERATION_DOLLARS = 0.30
RANGE_BLOCK_WEAK_COUNT = 3


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return default if not np.isfinite(out) else out
    except (TypeError, ValueError):
        return default


def _text(value: Any, default: str = "NONE") -> str:
    text = str(value or "").strip().upper()
    return text or default


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [str(c).strip().title() for c in out.columns]
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(out.columns):
        return pd.DataFrame()
    for col in required:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["Open", "High", "Low", "Close"]).sort_index()


def _minutes_between(now: pd.Timestamp, then: Any) -> int:
    then_ts = pd.to_datetime(then, errors="coerce")
    if pd.isna(then_ts):
        return 0
    if now.tzinfo is not None and then_ts.tzinfo is None:
        then_ts = then_ts.tz_localize(now.tzinfo)
    if now.tzinfo is None and then_ts.tzinfo is not None:
        then_ts = then_ts.tz_localize(None)
    return max(0, int((now - then_ts).total_seconds() // 60))


def calculate_features(df_1m: pd.DataFrame) -> Dict[str, Any]:
    """Önceki seans ısınmasıyla açılışın ilk dakikalarını da değerlendirir."""
    df = _normalize_df(df_1m)
    if len(df) < 22:
        return {
            "valid": False,
            "reason": "MINIMUM_22_TOTAL_BARS_REQUIRED",
            "available_bars": len(df),
        }

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"].fillna(0.0)
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    # EMA önceki seans barlarıyla ısınır; VWAP her seansta sıfırlanır.
    latest_date = df.index[-1].date()
    session_mask = np.asarray(df.index.date == latest_date)
    session_df = df.loc[session_mask]
    session_typical = (
        session_df["High"]
        + session_df["Low"]
        + session_df["Close"]
    ) / 3.0
    session_volume = session_df["Volume"].fillna(0.0)
    cumulative_volume = session_volume.cumsum().replace(0, np.nan)
    session_vwap = (
        (session_typical * session_volume).cumsum()
        / cumulative_volume
    )

    price = _safe_float(close.iloc[-1])
    previous = _safe_float(close.iloc[-2])
    ema9_now = _safe_float(ema9.iloc[-1])
    ema21_now = _safe_float(ema21.iloc[-1])
    ema9_slope = ema9_now - _safe_float(ema9.iloc[-3])
    momentum_3 = price - _safe_float(close.iloc[-4])
    momentum_acceleration = momentum_3 - (
        _safe_float(close.iloc[-4]) - _safe_float(close.iloc[-7])
    )
    vwap_now = _safe_float(session_vwap.iloc[-1], price)
    avg_volume = _safe_float(volume.iloc[-21:-1].mean(), 0.0)
    volume_ratio = _safe_float(volume.iloc[-1]) / avg_volume if avg_volume > 0 else 0.0

    prior_high = _safe_float(high.iloc[-11:-1].max())
    prior_low = _safe_float(low.iloc[-11:-1].min())
    breakout_up = price > prior_high and previous <= prior_high
    breakout_down = price < prior_low and previous >= prior_low
    support_rejection = low.iloc[-1] <= prior_low and price > prior_low
    resistance_rejection = high.iloc[-1] >= prior_high and price < prior_high


    return {
        "valid": True,
        "history_bars": len(df),
        "session_bars": len(session_df),
        "timestamp": df.index[-1],
        "price": price,
        "ema9": ema9_now,
        "ema21": ema21_now,
        "ema9_slope": ema9_slope,
        "vwap": vwap_now,
        "momentum_3": momentum_3,
        "momentum_acceleration": momentum_acceleration,
        "volume_ratio": volume_ratio,
        "breakout_up": bool(breakout_up),
        "breakout_down": bool(breakout_down),
        "support_rejection": bool(support_rejection),
        "resistance_rejection": bool(resistance_rejection),
    }


def score_direction(features: Dict[str, Any], side: str) -> Dict[str, bool]:
    side = _text(side)
    price = _safe_float(features.get("price"))
    ema9 = _safe_float(features.get("ema9"))
    ema21 = _safe_float(features.get("ema21"))
    slope = _safe_float(features.get("ema9_slope"))
    vwap = _safe_float(features.get("vwap"))
    momentum = _safe_float(features.get("momentum_3"))
    acceleration = _safe_float(features.get("momentum_acceleration"))
    volume_ratio = _safe_float(features.get("volume_ratio"))

    if side == "CALL":
        return {
            "direction": ema9 > ema21 and slope > 0,
            "location": price > vwap,
            "momentum": momentum > 0 and acceleration >= -0.10,
            "volume": volume_ratio >= 1.15,
            "structure": bool(features.get("breakout_up") or features.get("support_rejection")),
        }
    return {
        "direction": ema9 < ema21 and slope < 0,
        "location": price < vwap,
        "momentum": momentum < 0 and acceleration <= 0.10,
        "volume": volume_ratio >= 1.15,
        "structure": bool(features.get("breakout_down") or features.get("resistance_rejection")),
    }


def _candidate_score(groups: Dict[str, bool]) -> int:
    return sum(bool(v) for v in groups.values())


def evaluate_range_gate(features: Dict[str, Any], side: str) -> Dict[str, Any]:
    """Clear sideways/chop conditions block alerts, never create orders."""
    direction = 1.0 if _text(side) == "CALL" else -1.0
    price = _safe_float(features.get("price"))
    ema_gap_pct = (
        abs(_safe_float(features.get("ema9")) - _safe_float(features.get("ema21")))
        / price * 100.0
        if price > 0 else 0.0
    )
    vwap_distance_pct = (
        (_safe_float(features.get("price")) - _safe_float(features.get("vwap")))
        / price * 100.0 * direction
        if price > 0 else 0.0
    )
    momentum = _safe_float(features.get("momentum_3")) * direction
    acceleration = _safe_float(features.get("momentum_acceleration")) * direction
    volume_ratio = _safe_float(features.get("volume_ratio"))
    weak = {
        "volume": volume_ratio < RANGE_MIN_VOLUME_RATIO,
        "ema_separation": ema_gap_pct < RANGE_MIN_EMA_GAP_PCT,
        "vwap_distance": vwap_distance_pct < RANGE_MIN_VWAP_DISTANCE_PCT,
        "momentum": momentum < RANGE_MIN_MOMENTUM_DOLLARS,
        "acceleration": acceleration < RANGE_MIN_ACCELERATION_DOLLARS,
    }
    weak_count = sum(bool(v) for v in weak.values())
    return {
        "blocked": weak_count >= RANGE_BLOCK_WEAK_COUNT,
        "regime": "SIDEWAYS" if weak_count >= RANGE_BLOCK_WEAK_COUNT else "DIRECTIONAL",
        "weak_count": weak_count,
        "weak": weak,
        "ema_gap_pct": round(ema_gap_pct, 6),
        "vwap_distance_pct": round(vwap_distance_pct, 6),
        "directional_momentum": round(momentum, 6),
        "directional_acceleration": round(acceleration, 6),
        "volume_ratio": round(volume_ratio, 6),
    }


def _opposite_conflict(features: Dict[str, Any], side: str) -> bool:
    if side == "CALL":
        return bool(features.get("breakout_down")) or (
            _safe_float(features.get("price")) < _safe_float(features.get("ema21"))
            and _safe_float(features.get("momentum_3")) < 0
        )
    return bool(features.get("breakout_up")) or (
        _safe_float(features.get("price")) > _safe_float(features.get("ema21"))
        and _safe_float(features.get("momentum_3")) > 0
    )


def opportunity_candidate_engine(
    df_1m: pd.DataFrame,
    state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    state = dict(state or {})
    features = calculate_features(df_1m)
    base = {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "status": "NO_CANDIDATE",
        "action": "BEKLE",
        "side": "NONE",
        "candidate_score": 0,
        "confirmation_groups": 0,
        "features": features,
        "state": state,
    }
    if not features.get("valid"):
        base["status"] = "INSUFFICIENT_DATA"
        return base

    now = pd.Timestamp(features["timestamp"])
    active = dict(state.get("active_candidate") or {})
    last_confirmed = dict(state.get("last_confirmed") or {})

    if active:
        side = _text(active.get("side"))
        age = _minutes_between(now, active.get("created_at"))
        expiry = OPENING_CONFIRM_MINUTES if now.hour == 9 or (now.hour == 10 and now.minute <= 30) else NORMAL_CONFIRM_MINUTES
        groups = score_direction(features, side)
        score = _candidate_score(groups)
        range_gate = evaluate_range_gate(features, side)

        range_block_streak = int(active.get("range_block_streak", 0))
        range_block_streak = range_block_streak + 1 if range_gate["blocked"] else 0
        active["range_block_streak"] = range_block_streak
        state["active_candidate"] = active

        if range_block_streak >= 2:
            state["active_candidate"] = {}
            state["last_candidate_end"] = str(now)
            base.update({"status": "RANGE_BLOCKED", "action": "YATAY — İŞLEM YOK", "side": side, "candidate_score": score, "groups": groups, "range_gate": range_gate, "state": state})
            return base

        if age > expiry or _opposite_conflict(features, side):
            state["active_candidate"] = {}
            state["last_candidate_end"] = str(now)
            base.update({"status": "CANDIDATE_CANCELLED", "action": "ADAY İPTAL", "side": side, "candidate_score": score, "groups": groups, "state": state})
            return base

        independent_confirmations = sum(groups[name] for name in ("direction", "location", "structure", "volume", "momentum"))
        structure_or_volume = groups["structure"] or groups["volume"]
        confirmation_ready = (
            age >= 1
            and independent_confirmations >= CONFIRM_MIN_GROUPS
            and structure_or_volume
        )
        confirmation_streak = int(active.get("confirmation_streak", 0))
        confirmation_streak = confirmation_streak + 1 if confirmation_ready else 0
        active["confirmation_streak"] = confirmation_streak
        state["active_candidate"] = active

        if confirmation_streak >= CONFIRM_CONSECUTIVE_BARS:
            state["active_candidate"] = {}
            state["last_confirmed"] = {"side": side, "timestamp": str(now), "price": features["price"]}
            base.update({"status": "CONFIRMED", "action": f"{side} ONAYLI ADAY", "side": side, "candidate_score": score, "confirmation_groups": independent_confirmations, "groups": groups, "requires_final_approval": True, "state": state})
            return base

        base.update({"status": "WAITING_CONFIRMATION", "action": "ONAY BEKLE", "side": side, "candidate_score": score, "confirmation_groups": independent_confirmations, "groups": groups, "state": state})
        return base

    call_groups = score_direction(features, "CALL")
    put_groups = score_direction(features, "PUT")
    call_score = _candidate_score(call_groups)
    put_score = _candidate_score(put_groups)
    side = "CALL" if call_score > put_score else "PUT"
    groups = call_groups if side == "CALL" else put_groups
    score = max(call_score, put_score)
    range_gate = evaluate_range_gate(features, side)

    cooldown_active = (
        last_confirmed
        and _text(last_confirmed.get("side")) == side
        and _minutes_between(now, last_confirmed.get("timestamp")) < COOLDOWN_MINUTES
    )
    rearm_active = (
        state.get("last_candidate_end")
        and _minutes_between(now, state.get("last_candidate_end")) < CANDIDATE_REARM_MINUTES
    )
    base.update({"side": side if score >= CANDIDATE_MIN_SCORE else "NONE", "candidate_score": score, "groups": groups, "range_gate": range_gate})

    if rearm_active:
        base.update({"status": "REARM_COOLDOWN", "action": "BEKLE", "side": side, "state": state})
    elif range_gate["blocked"]:
        base.update({"status": "RANGE_BLOCKED", "action": "YATAY — İŞLEM YOK", "side": side, "state": state})
    elif score >= CANDIDATE_MIN_SCORE and groups["direction"] and groups["location"] and not cooldown_active:
        state["active_candidate"] = {"side": side, "created_at": str(now), "trigger_price": features["price"], "initial_score": score, "confirmation_streak": 0, "range_block_streak": 0}
        base.update({"status": "CANDIDATE_CREATED", "action": f"{side} ADAYI", "side": side, "state": state})
    elif cooldown_active:
        base.update({"status": "COOLDOWN", "action": "BEKLE", "side": side, "state": state})
    return base


def engine_health() -> Dict[str, Any]:
    return {"status": "PASS", "engine": ENGINE_NAME, "version": ENGINE_VERSION}
