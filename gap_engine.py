# ============================================================
# QQQ PRO
# gap_engine.py
# REAL GAP ANALYSIS ENGINE
# FINAL VERSION
# ============================================================

import math
from datetime import datetime


# ============================================================
# ENGINE CONFIG
# ============================================================

ENGINE_NAME = "GAP ENGINE"
ENGINE_VERSION = "2.0"

GAP_THRESHOLD_PERCENT = 0.20
GAP_FILL_TOLERANCE_PERCENT = 0.05


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=None):

    try:

        if value is None:
            return default

        if hasattr(value, "iloc"):

            if len(value) == 0:
                return default

            value = value.iloc[-1]

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except Exception:
        return default


def safe_string(value, default=""):

    try:

        if value is None:
            return default

        return str(value).strip()

    except Exception:
        return default


# ============================================================
# VALIDATE GAP DATA
# ============================================================

def validate_gap_data(data):

    if not isinstance(data, dict):
        return False

    required = (
        "current_price",
        "previous_close",
        "gap",
        "gap_percent",
        "gap_direction",
    )

    for key in required:

        if key not in data:
            return False

    return True


# ============================================================
# DATAFRAME
# ============================================================

def _get_dataframes(market):

    if not isinstance(market, dict):
        return []

    dataframes = []

    for key in (
        "df_1m",
        "df_5m",
        "df_15m",
    ):

        df = market.get(key)

        if df is not None and not getattr(df, "empty", True):

            dataframes.append(df)

    return dataframes


def _get_dataframe(market):

    dataframes = _get_dataframes(market)

    if not dataframes:
        return None

    return dataframes[0]


# ============================================================
# PREVIOUS CLOSE
# ============================================================

def _get_previous_close(market, df=None):

    if isinstance(market, dict):

        for key in (
            "previous_close",
            "prev_close",
            "previousClose",
            "previous_day_close",
            "prior_close",
        ):

            value = safe_float(
                market.get(key)
            )

            if value is not None:
                return value

    if df is not None and not getattr(df, "empty", True):

        try:

            if len(df) >= 2:

                value = safe_float(
                    df["Close"].iloc[-2]
                )

                if value is not None:
                    return value

        except Exception:
            pass

    return None


# ============================================================
# CURRENT PRICE
# ============================================================

def _get_current_price(market, df=None):

    if isinstance(market, dict):

        price = safe_float(
            market.get("price")
        )

        if price is not None:
            return price

    if df is not None and not getattr(df, "empty", True):

        try:

            return safe_float(
                df["Close"].iloc[-1]
            )

        except Exception:
            pass

    return None


# ============================================================
# SESSION OPEN
# ============================================================

def _get_open_price(market, df=None):

    if isinstance(market, dict):

        for key in (
            "session_open",
            "today_open",
            "market_open_price",
            "open",
        ):

            value = safe_float(
                market.get(key)
            )

            if value is not None:
                return value

    if df is not None and not getattr(df, "empty", True):

        try:

            return safe_float(
                df["Open"].iloc[0]
            )

        except Exception:
            pass

    return None


# ============================================================
# GAP CALCULATION
# ============================================================

def _calculate_gap(
    session_open,
    previous_close
):

    if (
        session_open is None
        or previous_close is None
    ):

        return 0.0, 0.0

    gap = (
        session_open
        - previous_close
    )

    if previous_close == 0:

        return gap, 0.0

    gap_percent = (
        gap
        / previous_close
    ) * 100.0

    return gap, gap_percent


# ============================================================
# GAP DIRECTION
# ============================================================

def _gap_direction(gap_percent):

    if gap_percent is None:
        return "UNKNOWN"

    if gap_percent >= GAP_THRESHOLD_PERCENT:
        return "GAP_UP"

    if gap_percent <= -GAP_THRESHOLD_PERCENT:
        return "GAP_DOWN"

    return "NO_GAP"


# ============================================================
# GAP STRENGTH
# ============================================================

def _gap_strength(gap_percent):

    if gap_percent is None:
        return 0

    value = abs(
        safe_float(
            gap_percent,
            0.0
        )
    )

    if value >= 2.00:
        return 100

    if value >= 1.50:
        return 95

    if value >= 1.00:
        return 90

    if value >= 0.75:
        return 80

    if value >= 0.50:
        return 70

    if value >= 0.30:
        return 60

    if value >= 0.20:
        return 50

    if value >= 0.10:
        return 30

    return 20


# ============================================================
# GAP FILL CALCULATION
# ============================================================

def _calculate_gap_fill(
    current_price,
    previous_close,
    session_open
):

    result = {
        "gap_fill": False,
        "gap_fill_percent": 0.0,
        "gap_remaining": None,
        "gap_remaining_percent": 100.0,
        "gap_filling": False,
        "fill_status": "NOT_AVAILABLE",
    }

    if (
        current_price is None
        or previous_close is None
        or session_open is None
    ):

        return result

    opening_gap = (
        session_open
        - previous_close
    )

    opening_gap_abs = abs(opening_gap)

    if opening_gap_abs <= 0:

        result["gap_fill"] = True
        result["gap_fill_percent"] = 100.0
        result["gap_remaining"] = 0.0
        result["gap_remaining_percent"] = 0.0
        result["fill_status"] = "NO_GAP"

        return result

    # Fiyat önceki kapanış çizgisini geçtiyse gap tamamen dolmuştur.
    # Mutlak mesafe kullanmak, çizginin ötesine geçen fiyatı yanlışlıkla
    # yeniden "dolmamış" gösterebilir.
    crossed_previous_close = bool(
        (opening_gap > 0 and current_price <= previous_close)
        or (opening_gap < 0 and current_price >= previous_close)
    )

    current_distance = (
        0.0
        if crossed_previous_close
        else abs(current_price - previous_close)
    )

    fill_percent = (
        1.0
        - (
            current_distance
            / opening_gap_abs
        )
    ) * 100.0

    fill_percent = max(
        0.0,
        min(
            100.0,
            fill_percent
        )
    )

    remaining = current_distance

    remaining_percent = (
        remaining
        / opening_gap_abs
    ) * 100.0

    remaining_percent = max(
        0.0,
        min(
            100.0,
            remaining_percent
        )
    )

    tolerance = (
        previous_close
        * GAP_FILL_TOLERANCE_PERCENT
        / 100.0
    )

    fully_filled = bool(
        crossed_previous_close
        or current_distance <= tolerance
    )

    moving_toward_fill = False

    if opening_gap > 0:

        moving_toward_fill = (
            current_price
            < session_open
        )

    elif opening_gap < 0:

        moving_toward_fill = (
            current_price
            > session_open
        )

    if fully_filled:

        fill_status = "FILLED"

    elif fill_percent >= 75:

        fill_status = "NEAR_FILL"

    elif fill_percent >= 50:

        fill_status = "FILLING"

    elif moving_toward_fill:

        fill_status = "PARTIAL_FILL"

    else:

        fill_status = "OPEN"

    result = {
        "gap_fill": fully_filled,
        "gap_fill_percent": round(
            fill_percent,
            2
        ),
        "gap_remaining": round(
            remaining,
            4
        ),
        "gap_remaining_percent": round(
            remaining_percent,
            2
        ),
        "gap_filling": (
            moving_toward_fill
            and not fully_filled
        ),
        "fill_status": fill_status,
    }

    return result


# ============================================================
# GAP BIAS
# ============================================================

def _calculate_gap_bias(
    gap_direction,
    gap_fill_percent,
    gap_filling
):

    if gap_direction == "GAP_UP":

        if gap_fill_percent >= 90:
            return "CALL_BIAS_WEAK"

        if gap_filling:
            return "PUT_REVERSAL_RISK"

        return "CALL_BIAS"

    if gap_direction == "GAP_DOWN":

        if gap_fill_percent >= 90:
            return "PUT_BIAS_WEAK"

        if gap_filling:
            return "CALL_REVERSAL_RISK"

        return "PUT_BIAS"

    return "NEUTRAL"


# ============================================================
# MAIN GAP ANALYSIS
# ============================================================

def analyze_gap(market):

    if not isinstance(market, dict):

        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "status": "FAIL",
            "valid": False,
            "reason": "MARKET DATA DICT DEĞİL",
            "gap_direction": "UNKNOWN",
            "direction": "UNKNOWN",
            "gap": 0.0,
            "gap_percent": 0.0,
            "score": 50.0,
            "final_score": 50.0,
            "confidence": 0,
            "signal": "NEUTRAL",
            "final_signal": "NEUTRAL",
            "data_ok": False,
        }

    df = _get_dataframe(market)

    current_price = _get_current_price(
        market,
        df
    )

    previous_close = _get_previous_close(
        market,
        df
    )

    session_open = _get_open_price(
        market,
        df
    )

    # --------------------------------------------------------
    # GAP ALWAYS USES SESSION OPEN VS PREVIOUS CLOSE
    # --------------------------------------------------------

    gap = 0.0
    gap_percent = 0.0

    if (
        session_open is not None
        and previous_close is not None
    ):

        gap, gap_percent = _calculate_gap(
            session_open,
            previous_close
        )

    elif (
        current_price is not None
        and previous_close is not None
    ):

        gap, gap_percent = _calculate_gap(
            current_price,
            previous_close
        )

    direction = _gap_direction(
        gap_percent
    )

    strength = _gap_strength(
        gap_percent
    )

    gap_up = (
        direction == "GAP_UP"
    )

    gap_down = (
        direction == "GAP_DOWN"
    )

    no_gap = (
        direction == "NO_GAP"
    )

    # --------------------------------------------------------
    # GAP FILL
    # --------------------------------------------------------

    fill_data = _calculate_gap_fill(
        current_price,
        previous_close,
        session_open
    )

    gap_fill = fill_data.get(
        "gap_fill",
        False
    )

    gap_fill_percent = fill_data.get(
        "gap_fill_percent",
        0.0
    )

    gap_remaining = fill_data.get(
        "gap_remaining"
    )

    gap_remaining_percent = fill_data.get(
        "gap_remaining_percent",
        100.0
    )

    gap_filling = fill_data.get(
        "gap_filling",
        False
    )

    fill_status = fill_data.get(
        "fill_status",
        "NOT_AVAILABLE"
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = 50.0

    if gap_up:

        score = 50.0 + (
            strength * 0.50
        )

    elif gap_down:

        score = 50.0 - (
            strength * 0.50
        )

    # Gap almost completely filled reduces directional edge.

    if (
        gap_fill_percent >= 90
        and not gap_fill
    ):

        if gap_up:
            score -= 10

        elif gap_down:
            score += 10

    if gap_fill:

        score = 50.0

    score = max(
        0.0,
        min(
            100.0,
            round(
                score,
                2
            )
        )
    )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = strength

    if no_gap:

        confidence = max(
            20,
            strength
        )

    if gap_fill:

        confidence = min(
            confidence,
            35
        )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    if gap_up:

        signal = "CALL_BIAS"

    elif gap_down:

        signal = "PUT_BIAS"

    else:

        signal = "NEUTRAL"

    # --------------------------------------------------------
    # GAP BIAS
    # --------------------------------------------------------

    gap_bias = _calculate_gap_bias(
        direction,
        gap_fill_percent,
        gap_filling
    )

    # --------------------------------------------------------
    # REASON
    # --------------------------------------------------------

    if gap_fill:

        reason = "GAP TAMAMEN DOLDU"

    elif gap_fill_percent >= 90:

        reason = "GAP %90'DAN FAZLA DOLDU"

    elif gap_filling:

        if gap_up:
            reason = "YUKARI GAP DOLUYOR"

        elif gap_down:
            reason = "AŞAĞI GAP DOLUYOR"

        else:
            reason = "GAP DOLMA SÜRECİNDE"

    elif gap_up:

        reason = "YUKARI GAP"

    elif gap_down:

        reason = "AŞAĞI GAP"

    else:

        reason = "ANLAMLI GAP YOK"

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    result = {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "status":
            "PASS",

        "valid":
            True,

        "symbol":
            market.get(
                "symbol",
                "QQQ"
            ),

        "timestamp":
            datetime.now().isoformat(),

        "current_price":
            current_price,

        "previous_close":
            previous_close,

        "session_open":
            session_open,

        "gap":
            round(
                gap,
                4
            ),

        "gap_percent":
            round(
                gap_percent,
                4
            ),

        "gap_direction":
            direction,

        "direction":
            direction,

        "gap_up":
            gap_up,

        "gap_down":
            gap_down,

        "no_gap":
            no_gap,

        "gap_threshold_percent":
            GAP_THRESHOLD_PERCENT,

        "gap_strength":
            strength,

        "score":
            score,

        "final_score":
            score,

        "confidence":
            confidence,

        "signal":
            signal,

        "final_signal":
            signal,

        "gap_bias":
            gap_bias,

        "gap_fill":
            gap_fill,

        "gap_fill_percent":
            gap_fill_percent,

        "gap_remaining":
            gap_remaining,

        "gap_remaining_percent":
            gap_remaining_percent,

        "gap_filling":
            gap_filling,

        "fill_status":
            fill_status,

        "gap_fill_tolerance_percent":
            GAP_FILL_TOLERANCE_PERCENT,

        "reason":
            reason,

        "data_source":
            market.get(
                "source"
            ),

        "market_open":
            market.get(
                "market_open"
            ),

        "session":
            market.get(
                "session"
            ),

        "data_ok":
            True,
    }

    return result


# ============================================================
# ALIASES
# ============================================================

def gap_engine(market):

    return analyze_gap(
        market
    )


def get_gap_data(market):

    return analyze_gap(
        market
    )


def calculate_gap(market):

    return analyze_gap(
        market
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "analyze_gap",
    "gap_engine",
    "get_gap_data",
    "calculate_gap",
    "validate_gap_data",
]
