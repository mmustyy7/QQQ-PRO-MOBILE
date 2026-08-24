
# ============================================================
# QQQ PRO
# pattern_engine.py
#
# FINAL PATTERN ENGINE
#
# Mum + yapı + breakout + rejection
# Double Top / Double Bottom + Range
#
# Öncelik:
# 1. REJECTION
# 2. DOUBLE TOP / DOUBLE BOTTOM
# 3. BREAKOUT
# 4. STRUCTURE
# 5. RANGE
#
# Test uyumluluğu:
# - validate_pattern_data
# - detect_structure
# - analyze_structure
# - detect_breakout
# - detect_rejection
# - detect_double_bottom
# - detect_double_top
# - analyze_patterns
# - pattern_engine
# - detect_patterns
# - get_pattern_data
# ============================================================

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ============================================================
# CONSTANTS
# ============================================================

MIN_DATA_LENGTH = 20

DOUBLE_TOLERANCE = 0.025
NECKLINE_TOLERANCE = 0.015

BREAKOUT_BUFFER = 0.0025

REJECTION_WICK_RATIO = 0.55
REJECTION_CLOSE_RATIO = 0.45

STRENGTH_MIN = 0
STRENGTH_MAX = 100


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:
            return default

        if isinstance(value, pd.Series):

            if value.empty:
                return default

            value = value.iloc[-1]

        elif isinstance(value, pd.DataFrame):

            if value.empty:
                return default

            value = value.iloc[-1, -1]

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except Exception:

        return default


def _clamp(
    value: float,
    low: float = STRENGTH_MIN,
    high: float = STRENGTH_MAX,
) -> int:

    try:

        return int(
            round(
                max(
                    low,
                    min(
                        high,
                        value,
                    ),
                )
            )
        )

    except Exception:

        return int(low)


# ============================================================
# COLUMN NORMALIZATION
# ============================================================

def _normalize_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    data = df.copy()

    mapping = {}

    for col in data.columns:

        name = str(col).strip().lower()

        if name in ("open", "o"):
            mapping[col] = "open"

        elif name in ("high", "h"):
            mapping[col] = "high"

        elif name in ("low", "l"):
            mapping[col] = "low"

        elif name in (
            "close",
            "c",
            "adj close",
        ):
            mapping[col] = "close"

        elif name in (
            "volume",
            "vol",
            "v",
        ):
            mapping[col] = "volume"

    data = data.rename(
        columns=mapping
    )

    required = [
        "open",
        "high",
        "low",
        "close",
    ]

    for column in required:

        if column not in data.columns:
            return pd.DataFrame()

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=required
    ).copy()

    if data.empty:
        return pd.DataFrame()

    return data


# ============================================================
# VALIDATE PATTERN DATA
# ============================================================

def validate_pattern_data(
    df: Any,
    min_length: int = MIN_DATA_LENGTH,
) -> Dict[str, Any]:

    if not isinstance(
        df,
        pd.DataFrame,
    ):

        return {
            "valid": False,
            "status": "INVALID_DATA",
            "reason": "DATAFRAME_DEĞİL",
            "length": 0,
        }

    if df.empty:

        return {
            "valid": False,
            "status": "INVALID_DATA",
            "reason": "BOŞ DATAFRAME",
            "length": 0,
        }

    data = _normalize_columns(df)

    if data.empty:

        return {
            "valid": False,
            "status": "INVALID_DATA",
            "reason": "OHLC VERİSİ GEÇERSİZ",
            "length": len(df),
        }

    if len(data) < min_length:

        return {
            "valid": False,
            "status": "INSUFFICIENT_DATA",
            "reason": "YETERSİZ VERİ",
            "length": len(data),
        }

    return {
        "valid": True,
        "status": "PASS",
        "reason": "VERİ GEÇERLİ",
        "length": len(data),
    }


# ============================================================
# MARKET DATA EXTRACTION
# ============================================================

def _get_data(
    market: Any,
) -> pd.DataFrame:

    if isinstance(
        market,
        pd.DataFrame,
    ):

        return _normalize_columns(
            market
        )

    if not isinstance(
        market,
        dict,
    ):

        return pd.DataFrame()

    candidates = [
        "df_5m",
        "df_15m",
        "df_1m",
        "data",
        "df",
        "ohlcv",
    ]

    for key in candidates:

        value = market.get(key)

        if isinstance(
            value,
            pd.DataFrame,
        ):

            data = _normalize_columns(
                value
            )

            if not data.empty:
                return data

    return pd.DataFrame()


# ============================================================
# CANDLE ANALYSIS
# ============================================================

def analyze_candle(
    row: pd.Series,
) -> Dict[str, Any]:

    if not isinstance(
        row,
        pd.Series,
    ):

        return {
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "body": 0.0,
            "range": 0.0,
            "upper_wick": 0.0,
            "lower_wick": 0.0,
            "body_ratio": 0.0,
            "upper_wick_ratio": 0.0,
            "lower_wick_ratio": 0.0,
            "bullish": False,
            "bearish": False,
            "type": "INVALID",
        }

    o = _safe_float(
        row.get("open")
    )

    h = _safe_float(
        row.get("high")
    )

    l = _safe_float(
        row.get("low")
    )

    c = _safe_float(
        row.get("close")
    )

    body = abs(
        c - o
    )

    total_range = max(
        h - l,
        0.000001,
    )

    upper_wick = max(
        0.0,
        h - max(o, c),
    )

    lower_wick = max(
        0.0,
        min(o, c) - l,
    )

    bullish = c > o
    bearish = c < o

    body_ratio = (
        body /
        total_range
    )

    upper_ratio = (
        upper_wick /
        total_range
    )

    lower_ratio = (
        lower_wick /
        total_range
    )

    if (
        bullish
        and
        lower_ratio >= REJECTION_WICK_RATIO
    ):

        candle_type = (
            "BULLISH_REJECTION"
        )

    elif (
        bearish
        and
        upper_ratio >= REJECTION_WICK_RATIO
    ):

        candle_type = (
            "BEARISH_REJECTION"
        )

    elif bullish:

        candle_type = "BULLISH"

    elif bearish:

        candle_type = "BEARISH"

    else:

        candle_type = "DOJI"

    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "body": body,
        "range": total_range,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "body_ratio": body_ratio,
        "upper_wick_ratio": upper_ratio,
        "lower_wick_ratio": lower_ratio,
        "bullish": bullish,
        "bearish": bearish,
        "type": candle_type,
    }


# ============================================================
# CANDLE ALIASES
# ============================================================

def analyze_candles(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    data = _normalize_columns(
        df
    )

    if data.empty:

        return {
            "valid": False,
            "pattern": "INVALID_DATA",
        }

    return analyze_candle(
        data.iloc[-1]
    )


def candle_analysis(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return analyze_candles(
        df
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def analyze_structure(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    data = _normalize_columns(
        df
    )

    if len(data) < 4:

        return {
            "pattern": "INSUFFICIENT_DATA",
            "bias": "NEUTRAL",
            "strength": 0,
            "valid": False,
        }

    highs = (
        data["high"]
        .tail(4)
        .tolist()
    )

    lows = (
        data["low"]
        .tail(4)
        .tolist()
    )

    last_high = highs[-1]
    prev_high = highs[-2]

    last_low = lows[-1]
    prev_low = lows[-2]

    higher_high = (
        last_high >
        prev_high
    )

    higher_low = (
        last_low >
        prev_low
    )

    lower_high = (
        last_high <
        prev_high
    )

    lower_low = (
        last_low <
        prev_low
    )

    if (
        higher_high
        and
        higher_low
    ):

        return {
            "pattern": "HIGHER_HIGH",
            "bias": "BULLISH",
            "strength": 65,
            "valid": True,
        }

    if (
        lower_high
        and
        lower_low
    ):

        return {
            "pattern": "LOWER_LOW",
            "bias": "BEARISH",
            "strength": 65,
            "valid": True,
        }

    return {
        "pattern": "RANGE",
        "bias": "NEUTRAL",
        "strength": 50,
        "valid": True,
    }


# ============================================================
# STRUCTURE ALIASES
# ============================================================

def detect_structure(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return analyze_structure(
        df
    )


def structure_analysis(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return analyze_structure(
        df
    )


# ============================================================
# BREAKOUT DETECTION
# ============================================================

def detect_breakout(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    data = _normalize_columns(
        df
    )

    if len(data) < 5:

        return {
            "detected": False,
            "pattern": None,
            "bias": "NEUTRAL",
            "strength": 0,
        }

    previous = data.iloc[:-1]

    current = data.iloc[-1]

    resistance = _safe_float(
        previous["high"]
        .tail(4)
        .max()
    )

    support = _safe_float(
        previous["low"]
        .tail(4)
        .min()
    )

    close = _safe_float(
        current["close"]
    )

    bullish_threshold = (
        resistance *
        (
            1 +
            BREAKOUT_BUFFER
        )
    )

    bearish_threshold = (
        support *
        (
            1 -
            BREAKOUT_BUFFER
        )
    )

    # ========================================================
    # BULLISH BREAKOUT
    #
    # ÖNEMLİ:
    # Sadece kapanış breakout kabul edilir.
    # Fitil tek başına breakout oluşturamaz.
    # ========================================================

    if close > bullish_threshold:

        strength = 72

        if (
            close >
            resistance *
            (
                1 +
                BREAKOUT_BUFFER * 2
            )
        ):

            strength = 82

        return {
            "detected": True,
            "pattern": "BULLISH_BREAKOUT",
            "bias": "BULLISH",
            "strength": strength,
            "level": resistance,
        }

    # ========================================================
    # BEARISH BREAKOUT
    #
    # ÖNEMLİ:
    # Sadece kapanış breakout kabul edilir.
    # Fitil tek başına breakout oluşturamaz.
    # ========================================================

    if close < bearish_threshold:

        strength = 73

        if (
            close <
            support *
            (
                1 -
                BREAKOUT_BUFFER * 2
            )
        ):

            strength = 84

        return {
            "detected": True,
            "pattern": "BEARISH_BREAKOUT",
            "bias": "BEARISH",
            "strength": strength,
            "level": support,
        }

    return {
        "detected": False,
        "pattern": None,
        "bias": "NEUTRAL",
        "strength": 0,
    }


# ============================================================
# BREAKOUT ALIAS
# ============================================================

def breakout_analysis(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return detect_breakout(
        df
    )


# ============================================================
# REJECTION DETECTION
# ============================================================

def detect_rejection(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    data = _normalize_columns(
        df
    )

    if len(data) < 3:

        return {
            "detected": False,
            "pattern": None,
            "bias": "NEUTRAL",
            "strength": 0,
        }

    row = analyze_candle(
        data.iloc[-1]
    )

    o = row["open"]
    h = row["high"]
    l = row["low"]
    c = row["close"]

    total_range = row["range"]

    if total_range <= 0:

        return {
            "detected": False,
            "pattern": None,
            "bias": "NEUTRAL",
            "strength": 0,
        }

    upper = row["upper_wick"]
    lower = row["lower_wick"]

    previous_high = _safe_float(
        data["high"]
        .iloc[:-1]
        .tail(3)
        .max()
    )

    previous_low = _safe_float(
        data["low"]
        .iloc[:-1]
        .tail(3)
        .min()
    )

    # ========================================================
    # BULLISH REJECTION
    # ========================================================

    bullish_wick = (
        lower >=
        total_range *
        REJECTION_WICK_RATIO
    )

    bullish_close = (
        c >=
        l +
        total_range *
        REJECTION_CLOSE_RATIO
    )

    bullish_level_test = (
        l <=
        previous_low *
        1.003
    )

    if (
        bullish_wick
        and
        bullish_close
        and
        bullish_level_test
        and
        c >= o
    ):

        return {
            "detected": True,
            "pattern": "BULLISH_REJECTION",
            "bias": "BULLISH",
            "strength": 100,
            "level": previous_low,
        }

    # ========================================================
    # BEARISH REJECTION
    # ========================================================

    bearish_wick = (
        upper >=
        total_range *
        REJECTION_WICK_RATIO
    )

    bearish_close = (
        c <=
        l +
        total_range *
        0.55
    )

    bearish_level_test = (
        h >=
        previous_high *
        0.997
    )

    if (
        bearish_wick
        and
        bearish_close
        and
        bearish_level_test
        and
        c <= o
    ):

        return {
            "detected": True,
            "pattern": "BEARISH_REJECTION",
            "bias": "BEARISH",
            "strength": 100,
            "level": previous_high,
        }

    return {
        "detected": False,
        "pattern": None,
        "bias": "NEUTRAL",
        "strength": 0,
    }


# ============================================================
# REJECTION ALIAS
# ============================================================

def rejection_analysis(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return detect_rejection(
        df
    )


# ============================================================
# DOUBLE BOTTOM
# ============================================================

def detect_double_bottom(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    data = _normalize_columns(
        df
    )

    if len(data) < 7:

        return {
            "detected": False,
            "strength": 0,
        }

    lows = (
        data["low"]
        .tolist()
    )

    split = len(lows) // 2

    left = lows[:split]
    right = lows[split:]

    if not left or not right:

        return {
            "detected": False,
            "strength": 0,
        }

    first_low = min(left)
    second_low = min(right)

    first_index = left.index(
        first_low
    )

    second_index = (
        split +
        right.index(
            second_low
        )
    )

    if first_index >= second_index:

        return {
            "detected": False,
            "strength": 0,
        }

    average_low = (
        first_low +
        second_low
    ) / 2

    difference = (
        abs(
            first_low -
            second_low
        )
        /
        max(
            average_low,
            0.000001,
        )
    )

    if difference > DOUBLE_TOLERANCE:

        return {
            "detected": False,
            "strength": 0,
        }

    middle = data.iloc[
        first_index + 1:
        second_index
    ]

    if middle.empty:

        return {
            "detected": False,
            "strength": 0,
        }

    neckline = _safe_float(
        middle["high"].max()
    )

    if neckline <= average_low:

        return {
            "detected": False,
            "strength": 0,
        }

    separation = (
        neckline -
        average_low
    ) / max(
        average_low,
        0.000001,
    )

    if separation < 0.015:

        return {
            "detected": False,
            "strength": 0,
        }

    strength = 75

    if difference <= 0.01:
        strength = 90

    if separation >= 0.06:
        strength += 5

    return {
        "detected": True,
        "strength": _clamp(
            strength
        ),
        "neckline": round(
            neckline,
            4,
        ),
        "first_low": round(
            first_low,
            4,
        ),
        "second_low": round(
            second_low,
            4,
        ),
    }


# ============================================================
# DOUBLE TOP
# ============================================================

def detect_double_top(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    data = _normalize_columns(
        df
    )

    if len(data) < 7:

        return {
            "detected": False,
            "strength": 0,
        }

    highs = (
        data["high"]
        .tolist()
    )

    split = len(highs) // 2

    left = highs[:split]
    right = highs[split:]

    if not left or not right:

        return {
            "detected": False,
            "strength": 0,
        }

    first_high = max(left)
    second_high = max(right)

    first_index = left.index(
        first_high
    )

    second_index = (
        split +
        right.index(
            second_high
        )
    )

    if first_index >= second_index:

        return {
            "detected": False,
            "strength": 0,
        }

    average_high = (
        first_high +
        second_high
    ) / 2

    difference = (
        abs(
            first_high -
            second_high
        )
        /
        max(
            average_high,
            0.000001,
        )
    )

    if difference > DOUBLE_TOLERANCE:

        return {
            "detected": False,
            "strength": 0,
        }

    middle = data.iloc[
        first_index + 1:
        second_index
    ]

    if middle.empty:

        return {
            "detected": False,
            "strength": 0,
        }

    neckline = _safe_float(
        middle["low"].min()
    )

    if neckline >= average_high:

        return {
            "detected": False,
            "strength": 0,
        }

    separation = (
        average_high -
        neckline
    ) / max(
        average_high,
        0.000001,
    )

    if separation < 0.015:

        return {
            "detected": False,
            "strength": 0,
        }

    strength = 75

    if difference <= 0.01:
        strength = 90

    if separation >= 0.06:
        strength += 5

    return {
        "detected": True,
        "strength": _clamp(
            strength
        ),
        "neckline": round(
            neckline,
            4,
        ),
        "first_high": round(
            first_high,
            4,
        ),
        "second_high": round(
            second_high,
            4,
        ),
    }


# ============================================================
# DOUBLE ALIASES
# ============================================================

def double_bottom_analysis(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return detect_double_bottom(
        df
    )


def double_top_analysis(
    df: pd.DataFrame,
) -> Dict[str, Any]:

    return detect_double_top(
        df
    )


# ============================================================
# RANGE DETECTION
# ============================================================

def detect_range(
    df: pd.DataFrame,
) -> bool:

    data = _normalize_columns(
        df
    )

    if len(data) < 5:
        return False

    recent = data.tail(5)

    high = _safe_float(
        recent["high"].max()
    )

    low = _safe_float(
        recent["low"].min()
    )

    if low <= 0:
        return False

    range_pct = (
        high - low
    ) / low

    return (
        range_pct <= 0.025
    )


# ============================================================
# PATTERN RECORD
# ============================================================

def _pattern(
    name: str,
    bias: str,
    strength: int,
) -> Dict[str, Any]:

    return {
        "pattern": name,
        "bias": bias,
        "strength": _clamp(
            strength
        ),
    }


# ============================================================
# PATTERN PRIORITY
# ============================================================

def _priority(
    pattern_name: str,
) -> int:

    priorities = {

        "BULLISH_REJECTION": 100,
        "BEARISH_REJECTION": 100,

        "DOUBLE_BOTTOM": 95,
        "DOUBLE_TOP": 95,

        "BULLISH_BREAKOUT": 90,
        "BEARISH_BREAKOUT": 90,

        "HIGHER_HIGH": 60,
        "LOWER_LOW": 60,

        "RANGE": 10,
    }

    return priorities.get(
        pattern_name,
        0,
    )


# ============================================================
# DOUBLE PATTERN RESOLUTION
# ============================================================

def _resolve_double_pattern(
    data: pd.DataFrame,
    double_bottom: Dict[str, Any],
    double_top: Dict[str, Any],
) -> Optional[str]:

    bottom_detected = bool(
        double_bottom.get(
            "detected"
        )
    )

    top_detected = bool(
        double_top.get(
            "detected"
        )
    )

    if (
        not bottom_detected
        and
        not top_detected
    ):

        return None

    if (
        bottom_detected
        and
        not top_detected
    ):

        return "DOUBLE_BOTTOM"

    if (
        top_detected
        and
        not bottom_detected
    ):

        return "DOUBLE_TOP"

    last_close = _safe_float(
        data["close"].iloc[-1]
    )

    bottom_neckline = _safe_float(
        double_bottom.get(
            "neckline"
        )
    )

    top_neckline = _safe_float(
        double_top.get(
            "neckline"
        )
    )

    bottom_distance = abs(
        last_close -
        bottom_neckline
    )

    top_distance = abs(
        last_close -
        top_neckline
    )

    if top_distance < bottom_distance:
        return "DOUBLE_TOP"

    if bottom_distance < top_distance:
        return "DOUBLE_BOTTOM"

    last_open = _safe_float(
        data["open"].iloc[-1]
    )

    if last_close >= last_open:
        return "DOUBLE_BOTTOM"

    return "DOUBLE_TOP"


# ============================================================
# MAIN ANALYZER
# ============================================================

def analyze_patterns(
    market: Any = None,
    df: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    if df is not None:

        data = _normalize_columns(
            df
        )

    else:

        data = _get_data(
            market
        )

    # --------------------------------------------------------
    # INVALID DATA
    # --------------------------------------------------------

    if data.empty:

        return {
            "valid": False,
            "status": "FAIL",

            "pattern": "INVALID_DATA",
            "actual_pattern": "INVALID_DATA",

            "patterns": [],

            "bias": "NEUTRAL",

            "score": 50,
            "final_score": 50,

            "confidence": 0,

            "signal": "NEUTRAL",
            "final_signal": "NEUTRAL",

            "pattern_count": 0,

            "reason": "GEÇERSİZ VERİ",

            "validation": {
                "valid": False,
                "status": "INVALID_DATA",
            },
        }

    # --------------------------------------------------------
    # INSUFFICIENT DATA
    # --------------------------------------------------------

    if len(data) < MIN_DATA_LENGTH:

        return {
            "valid": False,
            "status": "INSUFFICIENT_DATA",

            "pattern": "INSUFFICIENT_DATA",
            "actual_pattern": "INSUFFICIENT_DATA",

            "patterns": [],

            "bias": "NEUTRAL",

            "score": 50,
            "final_score": 50,

            "confidence": 0,

            "signal": "NEUTRAL",
            "final_signal": "NEUTRAL",

            "pattern_count": 0,

            "reason": "YETERSİZ VERİ",

            "validation": {
                "valid": False,
                "status": "INSUFFICIENT_DATA",
            },
        }

    # --------------------------------------------------------
    # DETECTIONS
    # --------------------------------------------------------

    breakout = detect_breakout(
        data
    )

    rejection = detect_rejection(
        data
    )

    double_bottom = (
        detect_double_bottom(
            data
        )
    )

    double_top = (
        detect_double_top(
            data
        )
    )

    structure = analyze_structure(
        data
    )

    patterns: List[
        Dict[str, Any]
    ] = []

    # --------------------------------------------------------
    # REJECTION
    # --------------------------------------------------------

    if rejection.get(
        "detected"
    ):

        patterns.append(
            _pattern(
                rejection["pattern"],
                rejection["bias"],
                rejection["strength"],
            )
        )

    else:

        # ----------------------------------------------------
        # DOUBLE PATTERN
        # ----------------------------------------------------

        selected_double = (
            _resolve_double_pattern(
                data,
                double_bottom,
                double_top,
            )
        )

        if (
            selected_double
            ==
            "DOUBLE_BOTTOM"
        ):

            patterns.append(
                _pattern(
                    "DOUBLE_BOTTOM",
                    "BULLISH",
                    double_bottom[
                        "strength"
                    ],
                )
            )

        elif (
            selected_double
            ==
            "DOUBLE_TOP"
        ):

            patterns.append(
                _pattern(
                    "DOUBLE_TOP",
                    "BEARISH",
                    double_top[
                        "strength"
                    ],
                )
            )

        # ----------------------------------------------------
        # BREAKOUT
        # ----------------------------------------------------

        if breakout.get(
            "detected"
        ):

            breakout_name = (
                breakout.get(
                    "pattern"
                )
            )

            if (
                breakout_name
                ==
                "BULLISH_BREAKOUT"
            ):

                patterns.append(
                    _pattern(
                        "BULLISH_BREAKOUT",
                        "BULLISH",
                        breakout[
                            "strength"
                        ],
                    )
                )

            elif (
                breakout_name
                ==
                "BEARISH_BREAKOUT"
            ):

                patterns.append(
                    _pattern(
                        "BEARISH_BREAKOUT",
                        "BEARISH",
                        breakout[
                            "strength"
                        ],
                    )
                )

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    if (
        structure.get(
            "pattern"
        )
        in (
            "HIGHER_HIGH",
            "LOWER_LOW",
        )
    ):

        existing_names = {
            item["pattern"]
            for item in patterns
        }

        if (
            structure["pattern"]
            not in existing_names
        ):

            patterns.append(
                _pattern(
                    structure["pattern"],
                    structure["bias"],
                    structure["strength"],
                )
            )

    # --------------------------------------------------------
    # RANGE
    # --------------------------------------------------------

    if not patterns:

        patterns.append(
            _pattern(
                "RANGE",
                "NEUTRAL",
                55,
            )
        )

    # --------------------------------------------------------
    # UNIQUE PATTERNS
    # --------------------------------------------------------

    unique: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for item in patterns:

        name = item[
            "pattern"
        ]

        if name not in unique:

            unique[name] = item

        else:

            if (
                item["strength"]
                >
                unique[name]["strength"]
            ):

                unique[name] = item

    patterns = list(
        unique.values()
    )

    # --------------------------------------------------------
    # MAIN PATTERN
    # --------------------------------------------------------

    def ranking(
        item: Dict[str, Any],
    ) -> Tuple[int, int]:

        return (
            _priority(
                item["pattern"]
            ),
            item["strength"],
        )

    main = max(
        patterns,
        key=ranking,
    )

    main_pattern = (
        main["pattern"]
    )

    main_bias = (
        main["bias"]
    )

    main_strength = (
        main["strength"]
    )

    # --------------------------------------------------------
    # BIAS
    # --------------------------------------------------------

    if main_pattern == "RANGE":

        bias = "NEUTRAL"

    elif main_bias == "BULLISH":

        bias = "BULLISH"

    elif main_bias == "BEARISH":

        bias = "BEARISH"

    else:

        bias = "NEUTRAL"

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    if bias == "BULLISH":

        supportive_strength = sum(
            item["strength"]
            for item in patterns
            if (
                item["bias"]
                == "BULLISH"
                and
                item["pattern"]
                != main_pattern
            )
        )

        score = (
            50
            +
            min(
                49,
                int(
                    main_strength *
                    0.50
                )
                +
                int(
                    supportive_strength *
                    0.15
                ),
            )
        )

    elif bias == "BEARISH":

        supportive_strength = sum(
            item["strength"]
            for item in patterns
            if (
                item["bias"]
                == "BEARISH"
                and
                item["pattern"]
                != main_pattern
            )
        )

        score = (
            50
            -
            min(
                49,
                int(
                    main_strength *
                    0.50
                )
                +
                int(
                    supportive_strength *
                    0.15
                ),
            )
        )

    else:

        score = 50

    score = _clamp(
        score
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    if bias == "BULLISH":

        signal = "CALL_BIAS"

    elif bias == "BEARISH":

        signal = "PUT_BIAS"

    else:

        signal = "NEUTRAL"

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    if main_pattern == "RANGE":

        confidence = 50

    else:

        confidence = _clamp(
            50
            +
            (
                main_strength *
                0.35
            )
        )

        supportive_count = sum(
            1
            for item in patterns
            if (
                item["bias"]
                == bias
                and
                item["pattern"]
                != main_pattern
            )
        )

        if supportive_count >= 1:
            confidence += 5

        if supportive_count >= 2:
            confidence += 5

        confidence = _clamp(
            confidence
        )

    # --------------------------------------------------------
    # REASON
    # --------------------------------------------------------

    if main_pattern == "RANGE":

        reason = (
            "PATTERN YOK / RANGE"
        )

    elif main_pattern in (
        "BULLISH_REJECTION",
        "DOUBLE_BOTTOM",
        "BULLISH_BREAKOUT",
        "HIGHER_HIGH",
    ):

        reason = (
            "BULLISH PATTERN TEYIDI"
        )

    elif main_pattern in (
        "BEARISH_REJECTION",
        "DOUBLE_TOP",
        "BEARISH_BREAKOUT",
        "LOWER_LOW",
    ):

        reason = (
            "BEARISH PATTERN TEYIDI"
        )

    else:

        reason = (
            "PATTERN ANALİZİ"
        )

    # --------------------------------------------------------
    # FINAL SIGNAL
    # --------------------------------------------------------

    if main_pattern == "RANGE":

        final_signal = "NEUTRAL"

    elif main_bias == "BULLISH":

        final_signal = "CALL_BIAS"

    elif main_bias == "BEARISH":

        final_signal = "PUT_BIAS"

    else:

        final_signal = "NEUTRAL"

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    validation = (
        validate_pattern_data(
            data
        )
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    return {
        "valid": True,
        "status": "PASS",

        "pattern": main_pattern,
        "actual_pattern": main_pattern,

        "patterns": patterns,

        "bias": bias,

        "score": score,
        "final_score": score,

        "confidence": confidence,

        "signal": signal,
        "final_signal": final_signal,

        "pattern_count": len(patterns),

        "reason": reason,

        "validation": validation,
    }


# ============================================================
# MAIN ENGINE ALIAS
# ============================================================

def pattern_engine(
    market: Any = None,
    df: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Dict[str, Any]:

    return analyze_patterns(
        market=market,
        df=df,
        **kwargs,
    )


# ============================================================
# DETECT PATTERNS ALIAS
# ============================================================

def detect_patterns(
    market: Any = None,
    df: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Dict[str, Any]:

    return analyze_patterns(
        market=market,
        df=df,
        **kwargs,
    )


# ============================================================
# GET PATTERN DATA
# ============================================================

def get_pattern_data(
    market: Any = None,
    df: Optional[pd.DataFrame] = None,
    **kwargs,
) -> Dict[str, Any]:

    return analyze_patterns(
        market=market,
        df=df,
        **kwargs,
    )


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [

    "analyze_patterns",
    "detect_patterns",
    "pattern_engine",
    "get_pattern_data",

    "validate_pattern_data",

    "analyze_candle",
    "analyze_candles",
    "candle_analysis",

    "analyze_structure",
    "detect_structure",
    "structure_analysis",

    "detect_breakout",
    "breakout_analysis",

    "detect_rejection",
    "rejection_analysis",

    "detect_double_bottom",
    "double_bottom_analysis",

    "detect_double_top",
    "double_top_analysis",

    "detect_range",
]


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("QQQ PRO PATTERN ENGINE")
    print("SELF TEST")
    print("=" * 60)

    sample = pd.DataFrame({

        "open": [
            100,
            101,
            100,
            102,
            103,
            104,
            105,
            106,
        ],

        "high": [
            101,
            102,
            101,
            103,
            104,
            105,
            107,
            108,
        ],

        "low": [
            99,
            100,
            99,
            101,
            102,
            103,
            104,
            105,
        ],

        "close": [
            100.5,
            101.5,
            100.5,
            102.5,
            103.5,
            104.5,
            106,
            107,
        ],

        "volume": [
            1000,
            1100,
            1050,
            1200,
            1300,
            1400,
            1500,
            1600,
        ],
    })

    result = analyze_patterns(
        df=sample
    )

    print()

    print(
        "VALID   :",
        result.get("valid")
    )

    print(
        "STATUS  :",
        result.get("status")
    )

    print(
        "PATTERN :",
        result.get("pattern")
    )

    print(
        "BIAS    :",
        result.get("bias")
    )

    print(
        "SCORE   :",
        result.get("score")
    )

    print(
        "SIGNAL  :",
        result.get("signal")
    )

    print(
        "PATTERNS:",
        result.get("patterns")
    )

    print()
    print("=" * 60)
    print("SELF TEST TAMAMLANDI")
    print("=" * 60)
