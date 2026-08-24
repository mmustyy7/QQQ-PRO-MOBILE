from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ============================================================
# QQQ PRO
# reversal_confirmation_engine.py
#
# REVERSAL CONFIRMATION ENGINE v1.3.2
#
# v1.1:
#   1) Mevcut bearish reversal mantığı korunur.
#   2) Yeni OPENING_PUT_CONTINUATION modu eklenir.
#   3) Açılıştan başlayan sert aşağı yön hareketi için
#      "önce güçlü yükseliş olsun" şartı aranmaz.
#   4) SUPPORT_BOUNCE + bullish yapı CALL koruması korunur.
#   5) Aynı event içinde tekrar PUT AL üretilmez.
#
# v1.2:
#   1) EXTENDED MOVE / LATE PUT PROTECTION eklenir.
#   2) Sert düşüş sonrası session low yakınında,
#      SUPPORT_BREAK + bullish dip yapısı varsa yeni PUT
#      giriş adayı bloke edilir.
#   3) Reversal skoru korunur; yalnız entry gate bloklanır.
#   4) Mevcut açık PUT pozisyonunu otomatik kapatmaz.
#   5) Decision Engine / Trade Manager mevcut lifecycle
#      yönetimini sürdürür.
#
# v1.3.3:
#   1) FAST BULLISH INVALIDATION eklendi.
#   2) Aktif bearish PUT event, Signal=CALL + fiyat recovery
#      oluşursa 45 dakika beklemeden resetlenebilir.
#   3) Yeni CALL AL üretmez; yalnız eski bearish event'i temizler.
#
# Bu motor tek başına broker emri göndermez.
# ============================================================


ENGINE_NAME = "QQQ PRO Reversal Confirmation Engine"
ENGINE_VERSION = "1.3.3"


# ============================================================
# LEVEL / EVENT CONSTANTS
# ============================================================


REVERSAL_NONE = "NONE"
REVERSAL_WATCH = "WATCH"
REVERSAL_CONFIRMED = "CONFIRMED"
REVERSAL_STRONG = "STRONG"
REVERSAL_VERY_STRONG = "VERY_STRONG"

MODE_NONE = "NONE"
MODE_REVERSAL = "BEARISH_REVERSAL"
MODE_OPENING_PUT = "OPENING_PUT_CONTINUATION"

EVENT_NONE = "NO_EVENT"
EVENT_FIRST_SIGNAL = "FIRST_SIGNAL"
EVENT_CONFIRMATION = "SAME_EVENT_CONFIRMATION"


# ============================================================
# ORIGINAL REVERSAL SCORE SETTINGS
# ============================================================


W_CRITICAL_WARNING = 30
W_HIGH_WARNING = 15

W_PEAK_VERY_CLOSE = 15
W_PEAK_CLOSE = 10

W_VOL15_STRONG_DRY = 10
W_VOL15_DRY = 5

W_VOL5_STRONG_DRY = 10
W_VOL5_DRY = 5

W_PRIOR_UP_STRONG = 15
W_PRIOR_UP_OK = 10

W_DOUBLE_TOP = 30
W_BEARISH_REJECTION = 25
W_BEARISH_PATTERN_BIAS = 15

W_SUPPORT_BREAK = 40
W_RESISTANCE_REJECTION = 30

W_PUT_SIGNAL = 10
W_BEARISH_TREND = 5

P_SUPPORT_BOUNCE = 50
P_DOUBLE_BOTTOM_NORMAL = 35
P_BULLISH_BIAS_NORMAL = 20
P_DOUBLE_BOTTOM_AFTER_BREAK = 10
P_BULLISH_BIAS_AFTER_BREAK = 5
P_BULLISH_REJECTION = 30
P_CALL_SIGNAL = 5
P_BULLISH_TREND = 5

W_SUPPORT_BREAK_CRITICAL = 20
W_SUPPORT_BREAK_PRIOR_UP = 10
W_SUPPORT_BREAK_PEAK = 10


# ============================================================
# SCORE THRESHOLDS
# ============================================================


PUT_CANDIDATE_MIN_SCORE = 60
STRONG_PUT_MIN_SCORE = 80

# ============================================================
# FIRST SIGNAL WARNING QUALITY GATE v1.3.2
# ============================================================
#
# Sorun:
# Toplam reversal skoru pattern/hacim/önceki hareket puanlarıyla
# 100'e doyabilir; ancak Big Move Warning yalnız MEDIUM olabilir.
#
# Kural:
# Yeni STRONG PUT adayı için en az HIGH warning kalitesi gerekir.
# Fakat gerçek yapısal kırılım/red varsa warning kalitesi düşük olsa
# bile entry adayı korunur.
#
FIRST_SIGNAL_WARNING_MIN_SCORE = 95.0
FIRST_SIGNAL_WARNING_STRONG_LEVELS = {
    "HIGH",
    "CRITICAL",
}
FIRST_SIGNAL_STRUCTURAL_OVERRIDES = {
    "SUPPORT_BREAK",
    "RESISTANCE_REJECTION",
    "RESISTANCE_REJECT",
}


# ============================================================
# OPENING PUT CONTINUATION SETTINGS
#
# Amaç:
# 09:30 sonrası güçlü aşağı yön devamını, klasik
# "önce yükseliş sonra reversal" filtresine sokmadan yakalamak.
#
# Bu mod yalnız sıkı koşullarla aktif olur:
# - erken seans,
# - ciddi open->current düşüş,
# - fiyat seans dibine yakın,
# - Signal Engine PUT,
# - Big Move warning >= 80,
# - bullish SUPPORT_BOUNCE yok.
# ============================================================


OPENING_START_HOUR = 9
OPENING_START_MINUTE = 35

OPENING_END_HOUR = 10
OPENING_END_MINUTE = 15

OPENING_MIN_DROP_PCT = 0.75
OPENING_NEAR_LOW_MAX_PCT = 0.25
OPENING_WARNING_MIN_SCORE = 80
OPENING_MIN_BARS = 6

OPENING_BASE_SCORE = 55
OPENING_PUT_SIGNAL_BONUS = 15
OPENING_WARNING_BONUS = 10
OPENING_DEEP_DROP_BONUS = 10
OPENING_NEAR_LOW_BONUS = 10
OPENING_BEARISH_PATTERN_BONUS = 10
OPENING_SUPPORT_BREAK_BONUS = 15

OPENING_DOUBLE_BOTTOM_PENALTY = 5
OPENING_BULLISH_BIAS_PENALTY = 5


# ============================================================
# EXTENDED MOVE / LATE PUT PROTECTION SETTINGS
# ============================================================
#
# Amaç:
# Hareket zaten aşağı yönde uzamışken, session low yakınında
# SUPPORT_BREAK görüp dipten yeni PUT kovalamayı engellemek.
#
# Bu katman skoru değiştirmez.
# Yalnız yeni PUT ENTRY adayını bloke eder.
#
# ------------------------------------------------------------

LATE_PUT_MIN_DROP_PCT = 0.70
LATE_PUT_NEAR_LOW_MAX_PCT = 0.20
LATE_PUT_DEEP_DROP_PCT = 1.00

# v1.3:
# Opening sırasında session open yerine session high'dan
# fiyatın ne kadar geri çekildiğini de ölç.
#
# 19 Ağustos 10:21 ve 20 Ağustos 10:19 gibi:
#   - fiyat session low'a yakın,
#   - SUPPORT_BREAK var,
#   - session high'dan sert düşüş oluşmuş,
# durumlarında yeni PUT kovalamayı engeller.
LATE_PUT_PEAK_DRAWDOWN_MIN_PCT = 0.45
LATE_PUT_WINDOW_END_HOUR = 10
LATE_PUT_WINDOW_END_MINUTE = 30

LATE_PUT_REQUIRE_SUPPORT_BREAK = True

LATE_PUT_BULLISH_PATTERNS = (
    "DOUBLE_BOTTOM",
    "BULLISH_REJECTION",
)

LATE_PUT_BULLISH_BIAS_VALUES = (
    "BULLISH",
)


# ============================================================
# EVENT SETTINGS
# ============================================================


MIN_EVENT_RESET_MINUTES = 45
SOFT_RESET_AFTER_MINUTES = 120
EVENT_INVALIDATION_UP_PCT = 0.35

# v1.3.3 FAST BULLISH INVALIDATION
# Amaç:
# Aktif bearish PUT event, piyasa belirgin şekilde CALL yönüne
# döndüğünde 45 dakika beklemeden geçersiz kılınabilsin.
#
# Bu kural yeni CALL AL üretmez.
# Yalnız mevcut bearish reversal event state'ini resetler.
FAST_BULLISH_RESET_MINUTES = 10
FAST_BULLISH_SIGNAL_VALUES = ("CALL",)
FAST_BULLISH_BLOCKED_SR_EVENTS = (
    "SUPPORT_BREAK",
    "BREAKDOWN",
    "BREAKOUT_DOWN",
)
FAST_BULLISH_MIN_PRICE_RECOVERY_PCT = 0.12
FAST_BULLISH_MIN_REVERSAL_SCORE = 0.0


# ============================================================
# HELPERS
# ============================================================


def safe_float(value: Any, default: float = 0.0) -> float:

    try:

        if value is None:
            return default

        result = float(value)

        if np.isnan(result):
            return default

        return result

    except Exception:
        return default


def safe_bool(value: Any, default: bool = False) -> bool:

    if isinstance(value, bool):
        return value

    if value is None:
        return default

    text = str(value).strip().upper()

    if text in ("TRUE", "1", "YES", "EVET"):
        return True

    if text in ("FALSE", "0", "NO", "HAYIR", "", "NONE", "NAN"):
        return False

    return default


def normalize_text(
    value: Any,
    default: str = "UNKNOWN",
) -> str:

    if value is None:
        return default

    try:

        if pd.isna(value):
            return default

    except Exception:
        pass

    text = str(value).strip().upper()

    return text if text else default


def parse_timestamp(
    value: Any,
) -> Optional[pd.Timestamp]:

    try:

        if value is None:
            return None

        ts = pd.Timestamp(value)

        if pd.isna(ts):
            return None

        return ts

    except Exception:
        return None


def normalize_dataframe(
    df: Any,
) -> pd.DataFrame:

    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    result = df.copy()

    for col in ("Open", "High", "Low", "Close", "Volume"):

        if col in result.columns:

            result[col] = pd.to_numeric(
                result[col],
                errors="coerce",
            )

    return result


# ============================================================
# DEFAULT STATE / RESPONSE
# ============================================================


def default_event_state() -> Dict[str, Any]:

    return {
        "active": False,
        "event_id": 0,
        "start_time": None,
        "start_price": 0.0,
        "side": "PUT",
        "confirmation_count": 0,
        "last_confirmation_time": None,
        "signal_mode": MODE_NONE,
    }


def normalize_event_state(
    event_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    state = default_event_state()

    if not isinstance(event_state, dict):
        return state

    state.update(event_state)

    state["active"] = safe_bool(
        state.get("active", False)
    )

    state["event_id"] = int(
        safe_float(
            state.get("event_id", 0),
            0.0,
        )
    )

    state["start_price"] = safe_float(
        state.get("start_price", 0.0)
    )

    state["confirmation_count"] = int(
        safe_float(
            state.get("confirmation_count", 0),
            0.0,
        )
    )

    state["signal_mode"] = normalize_text(
        state.get("signal_mode", MODE_NONE),
        MODE_NONE,
    )

    return state


def default_reversal_response(
    reason: str = "",
    event_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    state = normalize_event_state(
        event_state
    )

    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "valid": False,

        "signal_mode": MODE_NONE,

        "reversal_warning": False,
        "reversal_score": 0.0,
        "reversal_level": REVERSAL_NONE,

        "put_candidate": False,
        "strong_put_candidate": False,
        "put_entry_candidate": False,
        "put_hold_confirmation": False,

        "call_entry_risk": False,
        "hard_call_protection": False,

        "warning_quality_blocked": False,
        "warning_quality_reason": "",
        "warning_quality_score": 0.0,
        "warning_quality_risk": "LOW",
        "warning_quality_structural_override": False,

        "opening_put_continuation": False,
        "opening_drop_pct": 0.0,
        "opening_distance_from_low_pct": 999.0,
        "opening_session_open": 0.0,
        "opening_session_low": 0.0,

        "late_put_blocked": False,
        "late_put_reason": "",
        "late_put_drop_pct": 0.0,
        "late_put_peak_drawdown_pct": 0.0,
        "late_put_distance_from_low_pct": 999.0,

        "event_role": EVENT_NONE,
        "event_id": state.get("event_id", 0),
        "event_active": state.get("active", False),
        "event_reset": False,
        "event_reset_reason": "",
        "minutes_from_event_start": 0.0,

        "positive_reasons": "",
        "negative_reasons": "",

        "event_state": state,

        "status": "NO_REVERSAL",
        "reason": reason,
    }


# ============================================================
# MARKET EXTRACTION
# ============================================================


def extract_timestamp(
    market: Optional[Dict[str, Any]],
) -> pd.Timestamp:
    """
    Analiz için tek zaman kaynağı üretir.

    Öncelik gerçek 1m bar timestamp'idir. Bunun nedeni canlı
    market["timestamp"] değerinin sistem saatinden timezone'suz
    gelebilmesi, Yahoo DataFrame index'inin ise America/New_York
    timezone'lu olmasıdır.

    Böylece canlı ve replay aynı borsa zaman standardını kullanır.
    """

    if isinstance(market, dict):

        df_1m = normalize_dataframe(
            market.get("df_1m")
        )

        if not df_1m.empty:

            try:
                ts = pd.Timestamp(
                    df_1m.index[-1]
                )

                if not pd.isna(ts):
                    return ts

            except Exception:
                pass

        for key in (
            "timestamp",
            "last_update",
            "datetime",
            "time",
        ):

            ts = parse_timestamp(
                market.get(key)
            )

            if ts is not None:
                return ts

    return pd.Timestamp.now()


def extract_price(
    market: Optional[Dict[str, Any]],
) -> float:

    if isinstance(market, dict):

        for key in (
            "price",
            "live_price",
            "last_price",
            "close",
        ):

            price = safe_float(
                market.get(key)
            )

            if price > 0:
                return price

        df_1m = normalize_dataframe(
            market.get("df_1m")
        )

        if (
            not df_1m.empty
            and "Close" in df_1m.columns
        ):

            price = safe_float(
                df_1m["Close"].iloc[-1]
            )

            if price > 0:
                return price

    return 0.0


def extract_session_metrics(
    market: Optional[Dict[str, Any]],
    timestamp: pd.Timestamp,
    price: float,
) -> Dict[str, Any]:

    result = {
        "session_open": 0.0,
        "session_low": 0.0,
        "session_high": 0.0,
        "drop_pct": 0.0,
        "distance_from_low_pct": 999.0,
        "bars": 0,
    }

    if not isinstance(market, dict):
        return result

    df = normalize_dataframe(
        market.get("df_1m")
    )

    if df.empty:
        return result

    try:

        index_ts = pd.DatetimeIndex(
            pd.to_datetime(df.index)
        )

        ts = pd.Timestamp(timestamp)

        # DataFrame timezone'una hizala. Naive timestamp yalnız
        # fallback senaryosunda kalır; mümkünse borsa bar zamanı
        # extract_timestamp() tarafından zaten seçilmiştir.
        if index_ts.tz is not None:

            if ts.tzinfo is None:
                ts = ts.tz_localize(
                    index_ts.tz
                )
            else:
                ts = ts.tz_convert(
                    index_ts.tz
                )

        elif ts.tzinfo is not None:
            ts = ts.tz_localize(None)

        day_mask = (
            index_ts.date
            == ts.date()
        )

        same_day = df.loc[
            day_mask
        ].copy()

        if same_day.empty:
            return result

        # Pandas datetime64[s, tz] / Timestamp resolution
        # karşılaştırma sorununu önlemek için iki tarafı da
        # int64 nanosecond epoch değerine çevir.
        same_index = pd.DatetimeIndex(
            pd.to_datetime(same_day.index)
        )

        if same_index.tz is not None:
            cutoff_ns = ts.tz_convert(
                "UTC"
            ).value
            index_ns = same_index.tz_convert(
                "UTC"
            ).asi8
        else:
            cutoff_ns = ts.value
            index_ns = same_index.asi8

        same_day = same_day.iloc[
            index_ns <= cutoff_ns
        ].copy()

    except Exception:
        return result

    if same_day.empty:
        return result

    session_open = safe_float(
        same_day["Open"].iloc[0]
        if "Open" in same_day.columns
        else same_day["Close"].iloc[0]
    )

    session_low = safe_float(
        same_day["Low"].min()
        if "Low" in same_day.columns
        else same_day["Close"].min()
    )

    session_high = safe_float(
        same_day["High"].max()
        if "High" in same_day.columns
        else same_day["Close"].max()
    )

    if session_open > 0 and price > 0:

        drop_pct = (
            (
                price
                - session_open
            )
            / session_open
            * 100.0
        )

    else:
        drop_pct = 0.0

    if session_low > 0 and price > 0:

        distance_from_low_pct = (
            (
                price
                - session_low
            )
            / session_low
            * 100.0
        )

    else:
        distance_from_low_pct = 999.0

    result.update(
        {
            "session_open": session_open,
            "session_low": session_low,
            "session_high": session_high,
            "drop_pct": drop_pct,
            "distance_from_low_pct": distance_from_low_pct,
            "bars": len(same_day),
        }
    )

    return result


def is_opening_window(
    timestamp: pd.Timestamp,
) -> bool:

    minutes = (
        timestamp.hour * 60
        + timestamp.minute
    )

    start = (
        OPENING_START_HOUR * 60
        + OPENING_START_MINUTE
    )

    end = (
        OPENING_END_HOUR * 60
        + OPENING_END_MINUTE
    )

    return start <= minutes <= end


# ============================================================
# TECHNICAL NORMALIZATION
# ============================================================


def extract_technical_context(
    trend_data: Optional[Dict[str, Any]],
    signal_data: Optional[Dict[str, Any]],
    sr_data: Optional[Dict[str, Any]],
    pattern_data: Optional[Dict[str, Any]],
) -> Dict[str, str]:

    trend_data = (
        trend_data
        if isinstance(trend_data, dict)
        else {}
    )

    signal_data = (
        signal_data
        if isinstance(signal_data, dict)
        else {}
    )

    sr_data = (
        sr_data
        if isinstance(sr_data, dict)
        else {}
    )

    pattern_data = (
        pattern_data
        if isinstance(pattern_data, dict)
        else {}
    )

    trend = normalize_text(
        trend_data.get(
            "trend",
            trend_data.get(
                "trend_bias",
                "NEUTRAL",
            ),
        ),
        "NEUTRAL",
    )

    signal = normalize_text(
        signal_data.get(
            "signal",
            signal_data.get(
                "final_signal",
                "NEUTRAL",
            ),
        ),
        "NEUTRAL",
    )

    sr_event = normalize_text(
        sr_data.get(
            "event",
            sr_data.get(
                "sr_event",
                "NONE",
            ),
        ),
        "NONE",
    )

    pattern = normalize_text(
        pattern_data.get(
            "pattern",
            pattern_data.get(
                "signal",
                "NONE",
            ),
        ),
        "NONE",
    )

    pattern_bias = normalize_text(
        pattern_data.get(
            "pattern_bias",
            pattern_data.get(
                "bias",
                "NEUTRAL",
            ),
        ),
        "NEUTRAL",
    )

    return {
        "trend": trend,
        "signal": signal,
        "sr_event": sr_event,
        "pattern": pattern,
        "pattern_bias": pattern_bias,
    }


# ============================================================
# HARD CALL PROTECTION
# ============================================================


def calculate_hard_call_protection(
    sr_event: str,
    pattern: str,
    pattern_bias: str,
) -> bool:

    return bool(
        sr_event == "SUPPORT_BOUNCE"
        and (
            pattern in (
                "DOUBLE_BOTTOM",
                "BULLISH_REJECTION",
            )
            or pattern_bias == "BULLISH"
        )
    )


# ============================================================
# CLASSIC BEARISH REVERSAL SCORE
# ============================================================


def calculate_classic_reversal_score(
    big_move_warning: Dict[str, Any],
    context: Dict[str, str],
) -> Dict[str, Any]:

    score = 0

    positive: List[str] = []
    negative: List[str] = []

    filtered_warning = safe_bool(
        big_move_warning.get(
            "filtered_warning",
            False,
        )
    )

    warning_score = safe_float(
        big_move_warning.get(
            "warning_score",
            0,
        )
    )

    warning_risk = normalize_text(
        big_move_warning.get(
            "risk_level",
            "LOW",
        ),
        "LOW",
    )

    peak_distance = safe_float(
        big_move_warning.get(
            "distance_from_peak_%",
            999,
        ),
        999,
    )

    vol15_ratio = safe_float(
        big_move_warning.get(
            "vol15_ratio",
            999,
        ),
        999,
    )

    vol5_ratio = safe_float(
        big_move_warning.get(
            "vol5_ratio",
            999,
        ),
        999,
    )

    prior_up = safe_float(
        big_move_warning.get(
            "prior_up_move_$",
            0,
        )
    )

    trend = context["trend"]
    signal = context["signal"]
    sr_event = context["sr_event"]
    pattern = context["pattern"]
    pattern_bias = context["pattern_bias"]

    hard_call_protection = (
        calculate_hard_call_protection(
            sr_event,
            pattern,
            pattern_bias,
        )
    )

    if not filtered_warning:

        return {
            "score": 0.0,
            "eligible": False,
            "hard_call_protection": hard_call_protection,
            "positive_reasons": "",
            "negative_reasons": "",
        }

    critical_warning = bool(
        warning_score >= 100
        or warning_risk == "CRITICAL"
    )

    high_warning = bool(
        warning_score >= 95
        or warning_risk == "HIGH"
    )

    support_break = (
        sr_event == "SUPPORT_BREAK"
    )

    if critical_warning:

        score += W_CRITICAL_WARNING
        positive.append("critical warning")

    elif high_warning:

        score += W_HIGH_WARNING
        positive.append("high warning")

    if peak_distance <= 0.05:

        score += W_PEAK_VERY_CLOSE
        positive.append("very close to peak")

    elif peak_distance <= 0.20:

        score += W_PEAK_CLOSE
        positive.append("close to peak")

    if vol15_ratio <= 0.70:

        score += W_VOL15_STRONG_DRY
        positive.append("strong 15m volume dry-up")

    elif vol15_ratio <= 0.95:

        score += W_VOL15_DRY
        positive.append("15m volume dry-up")

    if vol5_ratio <= 0.60:

        score += W_VOL5_STRONG_DRY
        positive.append("strong 5m volume dry-up")

    elif vol5_ratio <= 0.90:

        score += W_VOL5_DRY
        positive.append("5m volume dry-up")

    if prior_up >= 3.0:

        score += W_PRIOR_UP_STRONG
        positive.append("strong prior up move")

    elif prior_up >= 2.0:

        score += W_PRIOR_UP_OK
        positive.append("prior up move")

    if pattern == "DOUBLE_TOP":

        score += W_DOUBLE_TOP
        positive.append("double top")

    if pattern == "BEARISH_REJECTION":

        score += W_BEARISH_REJECTION
        positive.append("bearish rejection")

    if pattern_bias == "BEARISH":

        score += W_BEARISH_PATTERN_BIAS
        positive.append("bearish pattern bias")

    if support_break:

        score += W_SUPPORT_BREAK
        positive.append("support break")

        if critical_warning:

            score += W_SUPPORT_BREAK_CRITICAL
            positive.append("support break + critical")

        if prior_up >= 3.0:

            score += W_SUPPORT_BREAK_PRIOR_UP
            positive.append("support break + strong prior up")

        if peak_distance <= 0.20:

            score += W_SUPPORT_BREAK_PEAK
            positive.append("support break + peak proximity")

    if sr_event in (
        "RESISTANCE_REJECTION",
        "RESISTANCE_REJECT",
    ):

        score += W_RESISTANCE_REJECTION
        positive.append("resistance rejection")

    if signal == "PUT":

        score += W_PUT_SIGNAL
        positive.append("PUT signal")

    if trend == "BEARISH":

        score += W_BEARISH_TREND
        positive.append("bearish trend")

    if sr_event == "SUPPORT_BOUNCE":

        score -= P_SUPPORT_BOUNCE
        negative.append("support bounce protection")

    if pattern == "DOUBLE_BOTTOM":

        if support_break:

            score -= P_DOUBLE_BOTTOM_AFTER_BREAK
            negative.append(
                "double bottom weakened after support break"
            )

        else:

            score -= P_DOUBLE_BOTTOM_NORMAL
            negative.append("double bottom protection")

    if pattern_bias == "BULLISH":

        if support_break:

            score -= P_BULLISH_BIAS_AFTER_BREAK
            negative.append(
                "bullish bias weakened after support break"
            )

        else:

            score -= P_BULLISH_BIAS_NORMAL
            negative.append(
                "bullish pattern bias protection"
            )

    if pattern == "BULLISH_REJECTION":

        score -= P_BULLISH_REJECTION
        negative.append("bullish rejection protection")

    if signal == "CALL":

        score -= P_CALL_SIGNAL
        negative.append("CALL signal minor conflict")

    if trend == "BULLISH":

        score -= P_BULLISH_TREND
        negative.append("bullish trend minor conflict")

    if hard_call_protection:

        score = min(score, 20)
        negative.append("hard call protection")

    score = max(
        -100,
        min(
            100,
            score,
        ),
    )

    return {
        "score": float(score),
        "eligible": True,
        "hard_call_protection": hard_call_protection,
        "positive_reasons": " | ".join(positive),
        "negative_reasons": " | ".join(negative),
    }


# ============================================================
# OPENING PUT CONTINUATION
# ============================================================


def calculate_opening_put_continuation(
    market: Optional[Dict[str, Any]],
    big_move_warning: Dict[str, Any],
    context: Dict[str, str],
    timestamp: pd.Timestamp,
    price: float,
) -> Dict[str, Any]:

    metrics = extract_session_metrics(
        market,
        timestamp,
        price,
    )

    score = 0

    positive: List[str] = []
    negative: List[str] = []

    signal = context["signal"]
    sr_event = context["sr_event"]
    pattern = context["pattern"]
    pattern_bias = context["pattern_bias"]

    warning = safe_bool(
        big_move_warning.get(
            "warning",
            False,
        )
    )

    warning_score = safe_float(
        big_move_warning.get(
            "warning_score",
            0.0,
        )
    )

    hard_call_protection = (
        calculate_hard_call_protection(
            sr_event,
            pattern,
            pattern_bias,
        )
    )

    # --------------------------------------------------------
    # HARD REQUIREMENTS
    # --------------------------------------------------------

    opening_window = (
        is_opening_window(timestamp)
    )

    enough_bars = (
        metrics["bars"]
        >= OPENING_MIN_BARS
    )

    deep_drop = (
        metrics["drop_pct"]
        <= -OPENING_MIN_DROP_PCT
    )

    near_low = (
        metrics["distance_from_low_pct"]
        <= OPENING_NEAR_LOW_MAX_PCT
    )

    put_signal = (
        signal == "PUT"
    )

    warning_ok = bool(
        warning
        and warning_score
        >= OPENING_WARNING_MIN_SCORE
    )

    eligible = bool(
        opening_window
        and enough_bars
        and deep_drop
        and near_low
        and put_signal
        and warning_ok
        and not hard_call_protection
    )

    if not eligible:

        reasons = []

        if not opening_window:
            reasons.append("outside opening window")

        if not enough_bars:
            reasons.append("insufficient opening bars")

        if not deep_drop:
            reasons.append("opening drop insufficient")

        if not near_low:
            reasons.append("price not near session low")

        if not put_signal:
            reasons.append("signal not PUT")

        if not warning_ok:
            reasons.append("warning below opening threshold")

        if hard_call_protection:
            reasons.append("hard call protection")

        return {
            "score": 0.0,
            "eligible": False,
            "hard_call_protection": hard_call_protection,
            "metrics": metrics,
            "positive_reasons": "",
            "negative_reasons": " | ".join(reasons),
        }

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score += OPENING_BASE_SCORE
    positive.append("opening downside continuation")

    score += OPENING_PUT_SIGNAL_BONUS
    positive.append("PUT signal")

    score += OPENING_WARNING_BONUS
    positive.append("opening warning confirmed")

    if metrics["drop_pct"] <= -1.00:

        score += OPENING_DEEP_DROP_BONUS
        positive.append("very deep opening drop")

    if (
        metrics["distance_from_low_pct"]
        <= 0.15
    ):

        score += OPENING_NEAR_LOW_BONUS
        positive.append("price near session low")

    if pattern in (
        "DOUBLE_TOP",
        "BEARISH_REJECTION",
    ):

        score += OPENING_BEARISH_PATTERN_BONUS
        positive.append("bearish pattern")

    if pattern_bias == "BEARISH":

        score += OPENING_BEARISH_PATTERN_BONUS
        positive.append("bearish pattern bias")

    if sr_event == "SUPPORT_BREAK":

        score += OPENING_SUPPORT_BREAK_BONUS
        positive.append("support break")

    # DOUBLE_BOTTOM / bullish bias tek başına veto değildir.
    # Açılışta trend devam ederken pattern motoru dip arayabilir.
    # Sadece küçük ceza uygulanır.

    if pattern == "DOUBLE_BOTTOM":

        score -= OPENING_DOUBLE_BOTTOM_PENALTY
        negative.append("double bottom minor conflict")

    if pattern_bias == "BULLISH":

        score -= OPENING_BULLISH_BIAS_PENALTY
        negative.append("bullish bias minor conflict")

    score = max(
        0,
        min(
            100,
            score,
        ),
    )

    return {
        "score": float(score),
        "eligible": True,
        "hard_call_protection": hard_call_protection,
        "metrics": metrics,
        "positive_reasons": " | ".join(positive),
        "negative_reasons": " | ".join(negative),
    }


# ============================================================
# EXTENDED MOVE / LATE PUT PROTECTION
# ============================================================

def evaluate_late_put_protection(
    market: Optional[Dict[str, Any]],
    context: Dict[str, str],
    timestamp: pd.Timestamp,
    price: float,
) -> Dict[str, Any]:
    """
    EXTENDED MOVE / LATE PUT PROTECTION v1.3

    Yeni PUT girişini iki ayrı exhaustion yapısında bloke eder:

    A) OPEN-BASED EXHAUSTION
       - session open'dan güçlü düşüş,
       - session low'a çok yakınlık,
       - SUPPORT_BREAK,
       - bullish dip yapısı/bias.

    B) PEAK-DRAWDOWN EXHAUSTION
       - açılışın ilk 60 dakikasında,
       - session high'dan >= %0.45 geri çekilme,
       - session low'a <= %0.20 yakınlık,
       - SUPPORT_BREAK.

    B kuralı özellikle pattern'in tek bar içinde
    DOUBLE_BOTTOM -> BEARISH_REJECTION / DOUBLE_TOP değişmesi
    nedeniyle geç PUT filtresinin boşa düşmesini engeller.

    Not:
      - Reversal score değiştirilmez.
      - Yalnız yeni PUT ENTRY candidate bloke edilir.
      - Açık PUT pozisyonunu otomatik kapatmaz.
    """

    metrics = extract_session_metrics(
        market,
        timestamp,
        price,
    )

    sr_event = normalize_text(
        context.get("sr_event"),
        "NONE",
    )

    pattern = normalize_text(
        context.get("pattern"),
        "NONE",
    )

    pattern_bias = normalize_text(
        context.get("pattern_bias"),
        "NEUTRAL",
    )

    signal = normalize_text(
        context.get("signal"),
        "NEUTRAL",
    )

    trend = normalize_text(
        context.get("trend"),
        "NEUTRAL",
    )

    drop_pct = safe_float(
        metrics.get("drop_pct"),
        0.0,
    )

    session_high = safe_float(
        metrics.get("session_high"),
        0.0,
    )

    distance_from_low_pct = safe_float(
        metrics.get("distance_from_low_pct"),
        999.0,
    )

    if session_high > 0 and price > 0:
        peak_drawdown_pct = (
            (session_high - price)
            / session_high
            * 100.0
        )
    else:
        peak_drawdown_pct = 0.0

    extended_drop = bool(
        drop_pct <= -LATE_PUT_MIN_DROP_PCT
    )

    very_deep_drop = bool(
        drop_pct <= -LATE_PUT_DEEP_DROP_PCT
    )

    peak_drawdown = bool(
        peak_drawdown_pct
        >= LATE_PUT_PEAK_DRAWDOWN_MIN_PCT
    )

    near_low = bool(
        distance_from_low_pct
        <= LATE_PUT_NEAR_LOW_MAX_PCT
    )

    support_break = bool(
        sr_event == "SUPPORT_BREAK"
    )

    bullish_pattern = bool(
        pattern in LATE_PUT_BULLISH_PATTERNS
    )

    bullish_bias = bool(
        pattern_bias in LATE_PUT_BULLISH_BIAS_VALUES
    )

    bullish_structure = bool(
        bullish_pattern
        or bullish_bias
    )

    minute_of_day = (
        timestamp.hour * 60
        + timestamp.minute
    )

    late_window_end = (
        LATE_PUT_WINDOW_END_HOUR * 60
        + LATE_PUT_WINDOW_END_MINUTE
    )

    # Regular US session başlangıcı.
    opening_window = bool(
        minute_of_day >= (9 * 60 + 30)
        and minute_of_day <= late_window_end
    )

    # --------------------------------------------------------
    # A) OPEN-BASED EXHAUSTION
    # --------------------------------------------------------
    primary_block = bool(
        extended_drop
        and near_low
        and support_break
        and bullish_structure
    )

    # --------------------------------------------------------
    # B) PEAK-DRAWDOWN EXHAUSTION
    # --------------------------------------------------------
    #
    # Pattern'in o tek barda bearish görünmesi bu korumayı
    # iptal etmez. Çünkü amaç dip yakınında, sert session-high
    # drawdown sonrası SUPPORT_BREAK kovalamayı engellemektir.
    #
    # Yalnız açılışın ilk 60 dakikasında aktiftir; böylece
    # 11 Ağustos 13:00 gibi gün ortası başarılı continuation
    # PUT'ları bu gate tarafından engellenmez.
    # --------------------------------------------------------
    peak_exhaustion_block = bool(
        opening_window
        and peak_drawdown
        and near_low
        and support_break
    )

    # Çok derin open düşüşünde bullish dip yapısı varsa
    # SUPPORT_BREAK olmasa bile güvenlik blokajı.
    deep_drop_block = bool(
        very_deep_drop
        and near_low
        and bullish_structure
    )

    blocked = bool(
        primary_block
        or peak_exhaustion_block
        or deep_drop_block
    )

    reasons: List[str] = []

    if opening_window:
        reasons.append("opening late-put window")

    if extended_drop:
        reasons.append(
            f"extended open drop {drop_pct:.3f}%"
        )

    if peak_drawdown:
        reasons.append(
            f"session-high drawdown {peak_drawdown_pct:.3f}%"
        )

    if very_deep_drop:
        reasons.append(
            "very deep opening/session drop"
        )

    if near_low:
        reasons.append(
            f"near session low {distance_from_low_pct:.3f}%"
        )

    if support_break:
        reasons.append(
            "support break"
        )

    if bullish_pattern:
        reasons.append(
            f"bullish pattern {pattern}"
        )

    if bullish_bias:
        reasons.append(
            "bullish pattern bias"
        )

    if peak_exhaustion_block:
        reasons.append(
            "PEAK_DRAWDOWN_EXHAUSTION"
        )

    if signal == "PUT":
        reasons.append("signal PUT")

    if trend == "BEARISH":
        reasons.append("trend BEARISH")

    return {
        "blocked": blocked,
        "reason": " | ".join(reasons),
        "drop_pct": drop_pct,
        "peak_drawdown_pct": peak_drawdown_pct,
        "distance_from_low_pct": distance_from_low_pct,
        "session_open": safe_float(
            metrics.get("session_open"),
            0.0,
        ),
        "session_low": safe_float(
            metrics.get("session_low"),
            0.0,
        ),
        "session_high": session_high,
        "support_break": support_break,
        "bullish_structure": bullish_structure,
        "bullish_pattern": bullish_pattern,
        "bullish_bias": bullish_bias,
        "extended_drop": extended_drop,
        "peak_drawdown": peak_drawdown,
        "opening_window": opening_window,
        "peak_exhaustion_block": peak_exhaustion_block,
        "very_deep_drop": very_deep_drop,
    }


# ============================================================
# FIRST SIGNAL WARNING QUALITY GATE
# ============================================================

def evaluate_first_signal_warning_quality(
    big_move_warning: Optional[Dict[str, Any]],
    context: Optional[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Reversal score'u değiştirmeden yeni güçlü PUT entry kalitesini
    kontrol eder.

    HIGH/CRITICAL warning -> uygun.
    MEDIUM/LOW warning -> yalnız gerçek yapısal S/R teyidi varsa uygun.
    """

    warning_data = (
        big_move_warning
        if isinstance(big_move_warning, dict)
        else {}
    )

    technical = (
        context
        if isinstance(context, dict)
        else {}
    )

    warning_score = safe_float(
        warning_data.get(
            "warning_score",
            0.0,
        )
    )

    warning_risk = normalize_text(
        warning_data.get(
            "risk_level",
            "LOW",
        ),
        "LOW",
    )

    sr_event = normalize_text(
        technical.get(
            "sr_event",
            "NONE",
        ),
        "NONE",
    )

    strong_warning = bool(
        warning_score
        >= FIRST_SIGNAL_WARNING_MIN_SCORE
        or warning_risk
        in FIRST_SIGNAL_WARNING_STRONG_LEVELS
    )

    structural_override = bool(
        sr_event
        in FIRST_SIGNAL_STRUCTURAL_OVERRIDES
    )

    quality_ok = bool(
        strong_warning
        or structural_override
    )

    if strong_warning:
        reason = "STRONG_WARNING"

    elif structural_override:
        reason = "STRUCTURAL_OVERRIDE"

    else:
        reason = "WEAK_WARNING_WITHOUT_STRUCTURE"

    return {
        "quality_ok": quality_ok,
        "blocked": not quality_ok,
        "reason": reason,
        "warning_score": warning_score,
        "warning_risk": warning_risk,
        "sr_event": sr_event,
        "strong_warning": strong_warning,
        "structural_override": structural_override,
    }


# ============================================================
# COMBINED SCORE SELECTOR
# ============================================================


def calculate_reversal_score(
    market: Optional[Dict[str, Any]],
    big_move_warning: Dict[str, Any],
    trend_data: Optional[Dict[str, Any]] = None,
    signal_data: Optional[Dict[str, Any]] = None,
    sr_data: Optional[Dict[str, Any]] = None,
    pattern_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    context = extract_technical_context(
        trend_data,
        signal_data,
        sr_data,
        pattern_data,
    )

    timestamp = extract_timestamp(
        market
    )

    price = extract_price(
        market
    )

    classic = calculate_classic_reversal_score(
        big_move_warning,
        context,
    )

    opening = calculate_opening_put_continuation(
        market=market,
        big_move_warning=big_move_warning,
        context=context,
        timestamp=timestamp,
        price=price,
    )

    late_put = evaluate_late_put_protection(
        market=market,
        context=context,
        timestamp=timestamp,
        price=price,
    )

    hard_call_protection = bool(
        classic.get(
            "hard_call_protection",
            False,
        )
        or opening.get(
            "hard_call_protection",
            False,
        )
    )

    # En yüksek geçerli bearish setup seçilir.
    # Opening continuation klasik reversal mantığını değiştirmez.

    classic_score = safe_float(
        classic.get(
            "score",
            0.0,
        )
    )

    opening_score = safe_float(
        opening.get(
            "score",
            0.0,
        )
    )

    if (
        opening.get("eligible", False)
        and opening_score > classic_score
    ):

        selected_mode = MODE_OPENING_PUT
        selected = opening

    elif classic.get("eligible", False):

        selected_mode = MODE_REVERSAL
        selected = classic

    else:

        selected_mode = MODE_NONE
        selected = {
            "score": 0.0,
            "positive_reasons": "",
            "negative_reasons": (
                opening.get(
                    "negative_reasons",
                    "",
                )
            ),
        }

    score = safe_float(
        selected.get(
            "score",
            0.0,
        )
    )

    if hard_call_protection:

        score = min(
            score,
            20.0,
        )

    if score >= 80:

        level = REVERSAL_VERY_STRONG

    elif score >= 70:

        level = REVERSAL_STRONG

    elif score >= 60:

        level = REVERSAL_CONFIRMED

    elif score >= 40:

        level = REVERSAL_WATCH

    else:

        level = REVERSAL_NONE

    late_put_blocked = safe_bool(
        late_put.get(
            "blocked",
            False,
        )
    )

    warning_quality = (
        evaluate_first_signal_warning_quality(
            big_move_warning=big_move_warning,
            context=context,
        )
    )

    warning_quality_blocked = bool(
        warning_quality.get(
            "blocked",
            False,
        )
    )

    put_candidate = bool(
        score >= PUT_CANDIDATE_MIN_SCORE
        and not hard_call_protection
        and not late_put_blocked
    )

    strong_put_candidate = bool(
        score >= STRONG_PUT_MIN_SCORE
        and not hard_call_protection
        and not late_put_blocked
        and not warning_quality_blocked
    )

    opening_metrics = opening.get(
        "metrics",
        {},
    )

    return {
        "score": score,
        "level": level,
        "signal_mode": selected_mode,

        "put_candidate": put_candidate,
        "strong_put_candidate": strong_put_candidate,

        "hard_call_protection": hard_call_protection,

        "warning_quality_blocked":
            warning_quality_blocked,

        "warning_quality_reason":
            warning_quality.get(
                "reason",
                "",
            ),

        "warning_quality_score":
            warning_quality.get(
                "warning_score",
                0.0,
            ),

        "warning_quality_risk":
            warning_quality.get(
                "warning_risk",
                "LOW",
            ),

        "warning_quality_structural_override":
            warning_quality.get(
                "structural_override",
                False,
            ),

        "late_put_blocked": late_put_blocked,

        "late_put_reason": late_put.get(
            "reason",
            "",
        ),

        "late_put_drop_pct": safe_float(
            late_put.get(
                "drop_pct",
                0.0,
            )
        ),

        "late_put_peak_drawdown_pct": safe_float(
            late_put.get(
                "peak_drawdown_pct",
                0.0,
            )
        ),

        "late_put_distance_from_low_pct": safe_float(
            late_put.get(
                "distance_from_low_pct",
                999.0,
            ),
            999.0,
        ),

        "opening_put_continuation": bool(
            selected_mode == MODE_OPENING_PUT
            and strong_put_candidate
        ),

        "opening_drop_pct": safe_float(
            opening_metrics.get(
                "drop_pct",
                0.0,
            )
        ),

        "opening_distance_from_low_pct": safe_float(
            opening_metrics.get(
                "distance_from_low_pct",
                999.0,
            ),
            999.0,
        ),

        "opening_session_open": safe_float(
            opening_metrics.get(
                "session_open",
                0.0,
            )
        ),

        "opening_session_low": safe_float(
            opening_metrics.get(
                "session_low",
                0.0,
            )
        ),

        "positive_reasons": selected.get(
            "positive_reasons",
            "",
        ),

        "negative_reasons": selected.get(
            "negative_reasons",
            "",
        ),

        "sr_event": context["sr_event"],
        "pattern": context["pattern"],
        "pattern_bias": context["pattern_bias"],
        "trend": context["trend"],
        "signal": context["signal"],
    }


# ============================================================
# EVENT RESET
# ============================================================


def should_reset_event(
    timestamp: pd.Timestamp,
    price: float,
    score_result: Dict[str, Any],
    event_state: Dict[str, Any],
) -> Dict[str, Any]:

    if not safe_bool(
        event_state.get(
            "active",
            False,
        )
    ):

        return {
            "reset": False,
            "reason": "",
        }

    event_start = parse_timestamp(
        event_state.get(
            "start_time"
        )
    )

    if event_start is None:

        return {
            "reset": True,
            "reason": "INVALID_EVENT_TIME",
        }

    if timestamp.date() != event_start.date():

        return {
            "reset": True,
            "reason": "NEW_TRADING_DAY",
        }

    minutes_from_start = (
        timestamp
        - event_start
    ).total_seconds() / 60.0

    start_price = safe_float(
        event_state.get(
            "start_price",
            0.0,
        )
    )

    hard_call_protection = safe_bool(
        score_result.get(
            "hard_call_protection",
            False,
        )
    )

    sr_event = normalize_text(
        score_result.get(
            "sr_event",
            "NONE",
        )
    )

    pattern = normalize_text(
        score_result.get(
            "pattern",
            "NONE",
        )
    )

    pattern_bias = normalize_text(
        score_result.get(
            "pattern_bias",
            "NEUTRAL",
        )
    )

    trend = normalize_text(
        score_result.get(
            "trend",
            "NEUTRAL",
        )
    )

    signal = normalize_text(
        score_result.get(
            "signal",
            "NEUTRAL",
        )
    )

    reasons: List[str] = []

    if (
        start_price > 0
        and price > 0
    ):

        price_up_pct = (
            (
                price
                - start_price
            )
            / start_price
            * 100.0
        )

    else:
        price_up_pct = 0.0

    # --------------------------------------------------------
    # v1.3.3 FAST BULLISH INVALIDATION
    # --------------------------------------------------------
    #
    # Aktif PUT event kısa sürede fiyat tarafından geçersiz
    # kılınırsa 45 dakika beklemeyiz.
    #
    # Güvenlik:
    # - en az 10 dakika event yaşı,
    # - Signal Engine CALL,
    # - aktif bearish breakdown/support-break olmamalı,
    # - fiyat event başlangıç seviyesinin en az %0.12 üstüne çıkmalı.
    #
    # Pattern'in hâlâ DOUBLE_TOP/BEARISH görünmesi tek başına
    # reset'i engellemez; çünkü bu kural fiyat+signal invalidation'dır.
    # --------------------------------------------------------

    fast_bullish_signal = (
        signal in FAST_BULLISH_SIGNAL_VALUES
    )

    fast_bullish_sr_clear = (
        sr_event not in FAST_BULLISH_BLOCKED_SR_EVENTS
    )

    fast_bullish_price_recovery = (
        price_up_pct >= FAST_BULLISH_MIN_PRICE_RECOVERY_PCT
    )

    fast_bullish_invalidation = bool(
        minutes_from_start >= FAST_BULLISH_RESET_MINUTES
        and fast_bullish_signal
        and fast_bullish_sr_clear
        and fast_bullish_price_recovery
    )

    if fast_bullish_invalidation:
        reasons.append(
            "FAST_BULLISH_INVALIDATION"
        )

    if (
        minutes_from_start
        >= MIN_EVENT_RESET_MINUTES
        and price_up_pct
        >= EVENT_INVALIDATION_UP_PCT
    ):

        reasons.append(
            "PRICE_INVALIDATION"
        )

    if (
        minutes_from_start
        >= MIN_EVENT_RESET_MINUTES
        and hard_call_protection
    ):

        reasons.append(
            "HARD_CALL_PROTECTION"
        )

    bullish_structure = bool(
        sr_event == "SUPPORT_BOUNCE"
        and (
            pattern in (
                "DOUBLE_BOTTOM",
                "BULLISH_REJECTION",
            )
            or pattern_bias == "BULLISH"
        )
    )

    if (
        minutes_from_start
        >= MIN_EVENT_RESET_MINUTES
        and bullish_structure
    ):

        reasons.append(
            "BULLISH_SUPPORT_BOUNCE"
        )

    soft_bullish = bool(
        (
            trend == "BULLISH"
            or signal == "CALL"
        )
        and pattern_bias == "BULLISH"
        and sr_event != "SUPPORT_BREAK"
    )

    if (
        minutes_from_start
        >= SOFT_RESET_AFTER_MINUTES
        and soft_bullish
    ):

        reasons.append(
            "SOFT_BULLISH_RESET"
        )

    return {
        "reset": bool(reasons),
        "reason": " | ".join(reasons),
    }


# ============================================================
# EVENT MANAGER
# ============================================================


def manage_reversal_event(
    timestamp: pd.Timestamp,
    price: float,
    score_result: Dict[str, Any],
    event_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    state = normalize_event_state(
        event_state
    )

    event_reset = False
    event_reset_reason = ""

    if state.get("active", False):

        reset_result = should_reset_event(
            timestamp=timestamp,
            price=price,
            score_result=score_result,
            event_state=state,
        )

        if reset_result["reset"]:

            event_reset = True
            event_reset_reason = (
                reset_result["reason"]
            )

            old_event_id = int(
                state.get("event_id", 0)
            )

            state = default_event_state()
            state["event_id"] = old_event_id

    strong_candidate = safe_bool(
        score_result.get(
            "strong_put_candidate",
            False,
        )
    )

    if not strong_candidate:

        return {
            "event_state": state,
            "event_role": EVENT_NONE,
            "event_id": state.get(
                "event_id",
                0,
            ),
            "event_active": state.get(
                "active",
                False,
            ),
            "event_reset": event_reset,
            "event_reset_reason": event_reset_reason,
            "minutes_from_event_start": 0.0,
        }

    if not state.get("active", False):

        new_event_id = (
            int(
                state.get(
                    "event_id",
                    0,
                )
            )
            + 1
        )

        state.update(
            {
                "active": True,
                "event_id": new_event_id,
                "start_time": timestamp,
                "start_price": price,
                "side": "PUT",
                "confirmation_count": 1,
                "last_confirmation_time": timestamp,
                "signal_mode": score_result.get(
                    "signal_mode",
                    MODE_NONE,
                ),
            }
        )

        return {
            "event_state": state,
            "event_role": EVENT_FIRST_SIGNAL,
            "event_id": new_event_id,
            "event_active": True,
            "event_reset": event_reset,
            "event_reset_reason": event_reset_reason,
            "minutes_from_event_start": 0.0,
        }

    event_start = parse_timestamp(
        state.get(
            "start_time"
        )
    )

    if event_start is not None:

        minutes_from_start = (
            timestamp
            - event_start
        ).total_seconds() / 60.0

    else:
        minutes_from_start = 0.0

    state["confirmation_count"] = (
        int(
            state.get(
                "confirmation_count",
                0,
            )
        )
        + 1
    )

    state["last_confirmation_time"] = (
        timestamp
    )

    return {
        "event_state": state,
        "event_role": EVENT_CONFIRMATION,
        "event_id": state.get(
            "event_id",
            0,
        ),
        "event_active": True,
        "event_reset": event_reset,
        "event_reset_reason": event_reset_reason,
        "minutes_from_event_start": round(
            minutes_from_start,
            2,
        ),
    }


# ============================================================
# MAIN ANALYZER
# ============================================================


def analyze_reversal_confirmation(
    market: Optional[Dict[str, Any]] = None,
    big_move_warning: Optional[Dict[str, Any]] = None,
    trend_data: Optional[Dict[str, Any]] = None,
    signal_data: Optional[Dict[str, Any]] = None,
    sr_data: Optional[Dict[str, Any]] = None,
    pattern_data: Optional[Dict[str, Any]] = None,
    event_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    try:

        if not isinstance(
            big_move_warning,
            dict,
        ):
            big_move_warning = {}

        timestamp = extract_timestamp(
            market
        )

        price = extract_price(
            market
        )

        state = normalize_event_state(
            event_state
        )

        score_result = calculate_reversal_score(
            market=market,
            big_move_warning=big_move_warning,
            trend_data=trend_data,
            signal_data=signal_data,
            sr_data=sr_data,
            pattern_data=pattern_data,
        )

        event_result = manage_reversal_event(
            timestamp=timestamp,
            price=price,
            score_result=score_result,
            event_state=state,
        )

        score = safe_float(
            score_result.get(
                "score",
                0.0,
            )
        )

        level = normalize_text(
            score_result.get(
                "level",
                REVERSAL_NONE,
            ),
            REVERSAL_NONE,
        )

        put_candidate = safe_bool(
            score_result.get(
                "put_candidate",
                False,
            )
        )

        strong_put_candidate = safe_bool(
            score_result.get(
                "strong_put_candidate",
                False,
            )
        )

        hard_call_protection = safe_bool(
            score_result.get(
                "hard_call_protection",
                False,
            )
        )

        late_put_blocked = safe_bool(
            score_result.get(
                "late_put_blocked",
                False,
            )
        )

        warning_quality_blocked = safe_bool(
            score_result.get(
                "warning_quality_blocked",
                False,
            )
        )

        event_role = normalize_text(
            event_result.get(
                "event_role",
                EVENT_NONE,
            ),
            EVENT_NONE,
        )

        put_entry_candidate = bool(
            strong_put_candidate
            and event_role
            == EVENT_FIRST_SIGNAL
            and not hard_call_protection
        )

        put_hold_confirmation = bool(
            strong_put_candidate
            and event_role
            == EVENT_CONFIRMATION
            and not hard_call_protection
        )

        call_entry_risk = bool(
            put_entry_candidate
            and not hard_call_protection
        )

        if hard_call_protection:

            status = "CALL_PROTECTED"

        elif late_put_blocked:

            status = "LATE_PUT_BLOCKED"

        elif warning_quality_blocked and score >= STRONG_PUT_MIN_SCORE:

            status = "WARNING_QUALITY_BLOCKED"

        elif put_entry_candidate:

            status = (
                "OPENING_PUT_ENTRY_CANDIDATE"
                if score_result.get(
                    "signal_mode"
                )
                == MODE_OPENING_PUT
                else "PUT_ENTRY_CANDIDATE"
            )

        elif put_hold_confirmation:

            status = "PUT_EVENT_CONFIRMATION"

        elif put_candidate:

            status = "PUT_REVERSAL_WATCH"

        else:

            status = "NO_CONFIRMED_REVERSAL"

        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "valid": True,

            "timestamp": timestamp,
            "price": round(
                price,
                4,
            ),

            "signal_mode": score_result.get(
                "signal_mode",
                MODE_NONE,
            ),

            "reversal_warning": bool(
                score > 0
            ),

            "reversal_score": round(
                score,
                2,
            ),

            "reversal_level": level,

            "put_candidate": put_candidate,
            "strong_put_candidate": strong_put_candidate,
            "put_entry_candidate": put_entry_candidate,
            "put_hold_confirmation": put_hold_confirmation,

            "call_entry_risk": call_entry_risk,
            "hard_call_protection": hard_call_protection,

            "warning_quality_blocked":
                warning_quality_blocked,

            "warning_quality_reason":
                score_result.get(
                    "warning_quality_reason",
                    "",
                ),

            "warning_quality_score": round(
                safe_float(
                    score_result.get(
                        "warning_quality_score",
                        0.0,
                    )
                ),
                2,
            ),

            "warning_quality_risk":
                score_result.get(
                    "warning_quality_risk",
                    "LOW",
                ),

            "warning_quality_structural_override":
                safe_bool(
                    score_result.get(
                        "warning_quality_structural_override",
                        False,
                    )
                ),

            "late_put_blocked": late_put_blocked,

            "late_put_reason": score_result.get(
                "late_put_reason",
                "",
            ),

            "late_put_drop_pct": round(
                safe_float(
                    score_result.get(
                        "late_put_drop_pct",
                        0.0,
                    )
                ),
                4,
            ),

            "late_put_peak_drawdown_pct": round(
                safe_float(
                    score_result.get(
                        "late_put_peak_drawdown_pct",
                        0.0,
                    )
                ),
                4,
            ),

            "late_put_distance_from_low_pct": round(
                safe_float(
                    score_result.get(
                        "late_put_distance_from_low_pct",
                        999.0,
                    ),
                    999.0,
                ),
                4,
            ),

            "opening_put_continuation": safe_bool(
                score_result.get(
                    "opening_put_continuation",
                    False,
                )
            ),

            "opening_drop_pct": round(
                safe_float(
                    score_result.get(
                        "opening_drop_pct",
                        0.0,
                    )
                ),
                4,
            ),

            "opening_distance_from_low_pct": round(
                safe_float(
                    score_result.get(
                        "opening_distance_from_low_pct",
                        999.0,
                    ),
                    999.0,
                ),
                4,
            ),

            "opening_session_open": round(
                safe_float(
                    score_result.get(
                        "opening_session_open",
                        0.0,
                    )
                ),
                4,
            ),

            "opening_session_low": round(
                safe_float(
                    score_result.get(
                        "opening_session_low",
                        0.0,
                    )
                ),
                4,
            ),

            "event_role": event_role,
            "event_id": event_result.get(
                "event_id",
                0,
            ),
            "event_active": safe_bool(
                event_result.get(
                    "event_active",
                    False,
                )
            ),
            "event_reset": safe_bool(
                event_result.get(
                    "event_reset",
                    False,
                )
            ),
            "event_reset_reason": event_result.get(
                "event_reset_reason",
                "",
            ),
            "minutes_from_event_start": safe_float(
                event_result.get(
                    "minutes_from_event_start",
                    0.0,
                )
            ),

            "sr_event": score_result.get(
                "sr_event",
                "NONE",
            ),
            "pattern": score_result.get(
                "pattern",
                "NONE",
            ),
            "pattern_bias": score_result.get(
                "pattern_bias",
                "NEUTRAL",
            ),
            "trend": score_result.get(
                "trend",
                "NEUTRAL",
            ),
            "signal": score_result.get(
                "signal",
                "NEUTRAL",
            ),

            "positive_reasons": score_result.get(
                "positive_reasons",
                "",
            ),
            "negative_reasons": score_result.get(
                "negative_reasons",
                "",
            ),

            "event_state": event_result.get(
                "event_state",
                state,
            ),

            "status": status,
        }

    except Exception as exc:

        return default_reversal_response(
            reason=(
                "Reversal Confirmation "
                f"Engine hatası: {exc}"
            ),
            event_state=event_state,
        )


# ============================================================
# ALIAS
# ============================================================


def reversal_confirmation_engine(
    market: Optional[Dict[str, Any]] = None,
    big_move_warning: Optional[Dict[str, Any]] = None,
    trend_data: Optional[Dict[str, Any]] = None,
    signal_data: Optional[Dict[str, Any]] = None,
    sr_data: Optional[Dict[str, Any]] = None,
    pattern_data: Optional[Dict[str, Any]] = None,
    event_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return analyze_reversal_confirmation(
        market=market,
        big_move_warning=big_move_warning,
        trend_data=trend_data,
        signal_data=signal_data,
        sr_data=sr_data,
        pattern_data=pattern_data,
        event_state=event_state,
    )


# ============================================================
# HEALTH
# ============================================================


def engine_health() -> Dict[str, Any]:

    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "status": "OK",
        "mode": "REVERSAL_CONFIRMATION_PLUS_OPENING_CONTINUATION_PLUS_LATE_PUT_EXHAUSTION",

        "thresholds": {
            "put_candidate_min_score":
                PUT_CANDIDATE_MIN_SCORE,

            "strong_put_min_score":
                STRONG_PUT_MIN_SCORE,

            "first_signal_warning_min_score":
                FIRST_SIGNAL_WARNING_MIN_SCORE,

            "fast_bullish_reset_minutes":
                FAST_BULLISH_RESET_MINUTES,

            "fast_bullish_min_price_recovery_pct":
                FAST_BULLISH_MIN_PRICE_RECOVERY_PCT,

            "opening_min_drop_pct":
                OPENING_MIN_DROP_PCT,

            "opening_near_low_max_pct":
                OPENING_NEAR_LOW_MAX_PCT,

            "opening_warning_min_score":
                OPENING_WARNING_MIN_SCORE,

            "late_put_min_drop_pct":
                LATE_PUT_MIN_DROP_PCT,

            "late_put_near_low_max_pct":
                LATE_PUT_NEAR_LOW_MAX_PCT,

            "late_put_deep_drop_pct":
                LATE_PUT_DEEP_DROP_PCT,

            "late_put_peak_drawdown_min_pct":
                LATE_PUT_PEAK_DRAWDOWN_MIN_PCT,

            "late_put_window_end":
                (
                    f"{LATE_PUT_WINDOW_END_HOUR:02d}:"
                    f"{LATE_PUT_WINDOW_END_MINUTE:02d}"
                ),

            "opening_window":
                (
                    f"{OPENING_START_HOUR:02d}:"
                    f"{OPENING_START_MINUTE:02d}-"
                    f"{OPENING_END_HOUR:02d}:"
                    f"{OPENING_END_MINUTE:02d}"
                ),

            "min_event_reset_minutes":
                MIN_EVENT_RESET_MINUTES,

            "soft_reset_minutes":
                SOFT_RESET_AFTER_MINUTES,

            "price_invalidation_pct":
                EVENT_INVALIDATION_UP_PCT,
        },

        "capabilities": [
            "BEARISH_REVERSAL_CONFIRMATION",
            "OPENING_PUT_CONTINUATION",
            "FIRST_SIGNAL",
            "SAME_EVENT_CONFIRMATION",
            "PUT_ENTRY_CANDIDATE",
            "PUT_HOLD_CONFIRMATION",
            "HARD_CALL_PROTECTION",
            "LATE_PUT_PROTECTION",
            "EXTENDED_MOVE_FILTER",
            "PEAK_DRAWDOWN_EXHAUSTION_FILTER",
            "TIMEZONE_SAFE_SESSION_METRICS",
            "FIRST_SIGNAL_WARNING_QUALITY_GATE",
            "EVENT_RESET",
        ],

        "limitations": [
            "NO_DIRECT_ORDER",
            "NO_BROKER_EXECUTION",
            "NO_HISTORICAL_OPTIONS_CHAIN",
        ],
    }


if __name__ == "__main__":

    print("=" * 90)
    print("QQQ PRO - REVERSAL CONFIRMATION ENGINE")
    print("=" * 90)
    print(engine_health())
    print("=" * 90)