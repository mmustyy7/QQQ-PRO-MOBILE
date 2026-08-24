# ============================================================
# QQQ PRO v5.6
# support_resistance.py
# DYNAMIC SUPPORT / RESISTANCE ENGINE
# ============================================================

import pandas as pd
import numpy as np


# ============================================================
# ENGINE INFO
# ============================================================

ENGINE_NAME = "QQQ PRO Support Resistance Engine"
ENGINE_VERSION = "5.6"


# ============================================================
# SETTINGS
# ============================================================

LOOKBACK_BARS = 50
SWING_WINDOW = 5

ZONE_PERCENT = 0.20
BREAKOUT_BUFFER_PERCENT = 0.10
LEVEL_TOLERANCE_PERCENT = 0.15

MIN_BREAKOUT_VOLUME_RATIO = 1.20
VOLUME_LOOKBACK = 10

TOUCH_WEIGHT = 4
REJECTION_WEIGHT = 6
BREAKOUT_WEIGHT = 5

EVENT_BREAKOUT_WEIGHT = 0.40
EVENT_LEVEL_WEIGHT = 0.40
EVENT_VOLUME_WEIGHT = 0.20


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, pd.Series):

            if value.empty:
                return default

            value = value.iloc[-1]

        if isinstance(value, pd.DataFrame):

            if value.empty:
                return default

            value = value.iloc[-1, -1]

        if isinstance(value, (list, tuple, np.ndarray)):

            if len(value) == 0:
                return default

            value = value[-1]

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


# ============================================================
# SAFE STRING
# ============================================================

def safe_string(value, default=""):

    try:

        if value is None:
            return default

        return str(value).strip().upper()

    except Exception:

        return default


# ============================================================
# VALIDATE DATAFRAME
# ============================================================

def validate_dataframe(df):

    if not isinstance(df, pd.DataFrame):
        return False

    if df.empty:
        return False

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    return all(
        column in df.columns
        for column in required
    )


# ============================================================
# CLEAN DATAFRAME
# ============================================================

def clean_dataframe(df):

    if not validate_dataframe(df):

        return pd.DataFrame(
            columns=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume"
            ]
        )

    data = df.copy()

    for column in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close"
        ]
    )

    return data


# ============================================================
# DAILY PIVOT
# ============================================================

def calculate_daily_pivot(df):

    result = {
        "pivot": 0.0,
        "r1": 0.0,
        "r2": 0.0,
        "s1": 0.0,
        "s2": 0.0
    }

    if not validate_dataframe(df):
        return result

    data = clean_dataframe(df)

    if data.empty:
        return result

    high = 0.0
    low = 0.0
    close = 0.0

    try:

        if isinstance(data.index, pd.DatetimeIndex):

            dates = data.index.normalize()

            unique_dates = pd.Series(
                dates
            ).drop_duplicates()

            if len(unique_dates) >= 2:

                previous_date = unique_dates.iloc[-2]

                previous_session = data[
                    dates == previous_date
                ]

                if not previous_session.empty:

                    high = safe_float(
                        previous_session["High"].max()
                    )

                    low = safe_float(
                        previous_session["Low"].min()
                    )

                    close = safe_float(
                        previous_session["Close"].iloc[-1]
                    )

            if (
                high <= 0
                or low <= 0
                or close <= 0
            ):

                recent = data.tail(
                    LOOKBACK_BARS
                )

                high = safe_float(
                    recent["High"].max()
                )

                low = safe_float(
                    recent["Low"].min()
                )

                close = safe_float(
                    recent["Close"].iloc[-1]
                )

        else:

            recent = data.tail(
                LOOKBACK_BARS
            )

            high = safe_float(
                recent["High"].max()
            )

            low = safe_float(
                recent["Low"].min()
            )

            close = safe_float(
                recent["Close"].iloc[-1]
            )

    except Exception:

        recent = data.tail(
            LOOKBACK_BARS
        )

        high = safe_float(
            recent["High"].max()
        )

        low = safe_float(
            recent["Low"].min()
        )

        close = safe_float(
            recent["Close"].iloc[-1]
        )

    if (
        high <= 0
        or low <= 0
        or close <= 0
    ):

        return result

    pivot = (
        high +
        low +
        close
    ) / 3.0

    r1 = (
        2 * pivot
    ) - low

    s1 = (
        2 * pivot
    ) - high

    r2 = (
        pivot +
        (high - low)
    )

    s2 = (
        pivot -
        (high - low)
    )

    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2)
    }


# ============================================================
# RECENT LEVELS
# ============================================================

def calculate_recent_levels(df):

    result = {
        "recent_high": 0.0,
        "recent_low": 0.0
    }

    if not validate_dataframe(df):
        return result

    data = clean_dataframe(df)

    if data.empty:
        return result

    recent = data.tail(
        LOOKBACK_BARS
    )

    result["recent_high"] = round(
        safe_float(
            recent["High"].max()
        ),
        2
    )

    result["recent_low"] = round(
        safe_float(
            recent["Low"].min()
        ),
        2
    )

    return result


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_support_resistance(df):

    result = {
        "pivot": 0.0,
        "support_1": 0.0,
        "support_2": 0.0,
        "resistance_1": 0.0,
        "resistance_2": 0.0,
        "recent_high": 0.0,
        "recent_low": 0.0
    }

    if not validate_dataframe(df):
        return result

    pivot = calculate_daily_pivot(df)
    recent = calculate_recent_levels(df)

    result.update({
        "pivot": pivot["pivot"],
        "support_1": pivot["s1"],
        "support_2": pivot["s2"],
        "resistance_1": pivot["r1"],
        "resistance_2": pivot["r2"],
        "recent_high": recent["recent_high"],
        "recent_low": recent["recent_low"]
    })

    return result


# ============================================================
# NEAREST LEVEL
# ============================================================

def nearest_level(price, levels):

    price = safe_float(
        price,
        0
    )

    if not isinstance(levels, dict):
        levels = {}

    candidates = {
        "S2": safe_float(
            levels.get("support_2"),
            0
        ),
        "S1": safe_float(
            levels.get("support_1"),
            0
        ),
        "R1": safe_float(
            levels.get("resistance_1"),
            0
        ),
        "R2": safe_float(
            levels.get("resistance_2"),
            0
        )
    }

    candidates = {
        name: value
        for name, value in candidates.items()
        if value > 0
    }

    if (
        price <= 0
        or not candidates
    ):

        return {
            "name": None,
            "price": None,
            "distance": None
        }

    name = min(
        candidates,
        key=lambda x: abs(
            price - candidates[x]
        )
    )

    level_price = candidates[name]

    return {
        "name": name,
        "price": round(
            level_price,
            2
        ),
        "distance": round(
            abs(
                price - level_price
            ),
            2
        )
    }


# ============================================================
# DISTANCE %
# ============================================================

def calculate_distance(price, level):

    price = safe_float(
        price,
        0
    )

    level = safe_float(
        level,
        0
    )

    if (
        price <= 0
        or level <= 0
    ):

        return None

    return round(
        abs(
            price - level
        )
        / price
        * 100,
        3
    )


# ============================================================
# PRICE ZONE
# ============================================================

def detect_price_zone(price, sr):

    price = safe_float(
        price,
        0
    )

    if not isinstance(sr, dict):
        sr = {}

    s1 = safe_float(
        sr.get("support_1"),
        0
    )

    r1 = safe_float(
        sr.get("resistance_1"),
        0
    )

    result = {
        "zone": "UNKNOWN",
        "distance_r1": calculate_distance(
            price,
            r1
        ),
        "distance_s1": calculate_distance(
            price,
            s1
        )
    }

    if price <= 0:
        return result

    if (
        r1 > 0
        and
        result["distance_r1"] is not None
        and
        result["distance_r1"] <= ZONE_PERCENT
    ):

        result["zone"] = "RESISTANCE"
        return result

    if (
        s1 > 0
        and
        result["distance_s1"] is not None
        and
        result["distance_s1"] <= ZONE_PERCENT
    ):

        result["zone"] = "SUPPORT"
        return result

    if (
        s1 > 0
        and
        r1 > 0
        and
        s1 < price < r1
    ):

        result["zone"] = "MIDDLE"

    return result


# ============================================================
# BREAKOUT BUFFER
# ============================================================

def breakout_buffer(level):

    level = safe_float(
        level,
        0
    )

    if level <= 0:
        return 0.0

    return (
        level *
        BREAKOUT_BUFFER_PERCENT /
        100
    )


# ============================================================
# RESISTANCE BREAKOUT
# ============================================================

def resistance_breakout(price, sr):

    if not isinstance(sr, dict):
        return False

    r1 = safe_float(
        sr.get("resistance_1"),
        0
    )

    if r1 <= 0:
        return False

    return (
        safe_float(price, 0)
        >
        r1 + breakout_buffer(r1)
    )


# ============================================================
# SUPPORT BREAKDOWN
# ============================================================

def support_breakdown(price, sr):

    if not isinstance(sr, dict):
        return False

    s1 = safe_float(
        sr.get("support_1"),
        0
    )

    if s1 <= 0:
        return False

    return (
        safe_float(price, 0)
        <
        s1 - breakout_buffer(s1)
    )


# ============================================================
# CANDLE DIRECTION
# ============================================================

def candle_direction(df):

    if not validate_dataframe(df):
        return "UNKNOWN"

    data = clean_dataframe(df)

    if data.empty:
        return "UNKNOWN"

    last = data.iloc[-1]

    open_price = safe_float(
        last["Open"]
    )

    close = safe_float(
        last["Close"]
    )

    if close > open_price:
        return "BULLISH"

    if close < open_price:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# VOLUME RATIO
# ============================================================

def calculate_volume_ratio(df):

    if not validate_dataframe(df):
        return 0.0

    data = clean_dataframe(df)

    if len(data) < VOLUME_LOOKBACK + 1:
        return 0.0

    current_volume = safe_float(
        data["Volume"].iloc[-1],
        0.0
    )

    previous_volumes = data[
        "Volume"
    ].iloc[
        -(VOLUME_LOOKBACK + 1):-1
    ]

    if previous_volumes.empty:
        return 0.0

    average_volume = safe_float(
        previous_volumes.mean(),
        0.0
    )

    if (
        current_volume <= 0
        or
        average_volume <= 0
    ):

        return 0.0

    return round(
        current_volume /
        average_volume,
        2
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def volume_ratio_calculator(df):
    return calculate_volume_ratio(df)


def volume_ratio_fn(df):
    return calculate_volume_ratio(df)


# ============================================================
# BREAKOUT ANALYZER
# ============================================================

def analyze_breakout(df, levels):

    current_volume_ratio = calculate_volume_ratio(df)

    result = {
        "direction": None,
        "level": None,
        "attempt": False,
        "confirmed": False,
        "volume_ratio": current_volume_ratio,
        "candle": candle_direction(df),
        "strength": 0.0,
        "close": 0.0,
        "previous_close": 0.0,
        "buffer": 0.0,
        "reason": ""
    }

    if not validate_dataframe(df):
        return result

    if not isinstance(levels, dict):
        return result

    data = clean_dataframe(df)

    if data.empty:
        return result

    close = safe_float(
        data["Close"].iloc[-1]
    )

    previous_close = (
        safe_float(
            data["Close"].iloc[-2]
        )
        if len(data) >= 2
        else close
    )

    r1 = safe_float(
        levels.get("resistance_1"),
        0
    )

    s1 = safe_float(
        levels.get("support_1"),
        0
    )

    result["close"] = close
    result["previous_close"] = previous_close

    # --------------------------------------------------------
    # RESISTANCE BREAKOUT ATTEMPT
    # --------------------------------------------------------

    if r1 > 0:

        r1_buffer = breakout_buffer(r1)

        if close > r1 + r1_buffer:

            result["direction"] = "BULLISH"
            result["level"] = "R1"
            result["attempt"] = True
            result["buffer"] = r1_buffer

            result["confirmed"] = (
                result["candle"] == "BULLISH"
                and
                current_volume_ratio >=
                MIN_BREAKOUT_VOLUME_RATIO
            )

            result["strength"] = breakout_strength(
                data
            )

            if result["confirmed"]:
                result["reason"] = (
                    "R1 üzerinde kapanış + bullish mum + "
                    "hacim teyidi."
                )
            else:
                result["reason"] = (
                    "R1 üstü breakout denemesi var ancak "
                    "mum/hacim teyidi yetersiz."
                )

            return result

    # --------------------------------------------------------
    # SUPPORT BREAKDOWN ATTEMPT
    # --------------------------------------------------------

    if s1 > 0:

        s1_buffer = breakout_buffer(s1)

        if close < s1 - s1_buffer:

            result["direction"] = "BEARISH"
            result["level"] = "S1"
            result["attempt"] = True
            result["buffer"] = s1_buffer

            result["confirmed"] = (
                result["candle"] == "BEARISH"
                and
                current_volume_ratio >=
                MIN_BREAKOUT_VOLUME_RATIO
            )

            result["strength"] = breakout_strength(
                data
            )

            if result["confirmed"]:
                result["reason"] = (
                    "S1 altında kapanış + bearish mum + "
                    "hacim teyidi."
                )
            else:
                result["reason"] = (
                    "S1 altı breakdown denemesi var ancak "
                    "mum/hacim teyidi yetersiz."
                )

            return result

    return result


# ============================================================
# REJECTION ANALYZER
# ============================================================

def analyze_rejection(df, levels):

    result = {
        "direction": None,
        "level": None,
        "confirmed": False,
        "type": None,
        "reason": ""
    }

    if not validate_dataframe(df):
        return result

    if not isinstance(levels, dict):
        return result

    data = clean_dataframe(df)

    if data.empty:
        return result

    last = data.iloc[-1]

    high = safe_float(last["High"])
    low = safe_float(last["Low"])
    close = safe_float(last["Close"])
    open_price = safe_float(last["Open"])

    previous_close = (
        safe_float(
            data["Close"].iloc[-2]
        )
        if len(data) >= 2
        else close
    )

    r1 = safe_float(
        levels.get("resistance_1"),
        0
    )

    s1 = safe_float(
        levels.get("support_1"),
        0
    )

    # --------------------------------------------------------
    # RESISTANCE REJECTION
    #
    # 1) Classical wick rejection:
    #    R1 touched/penetrated, closes back below R1,
    #    bearish candle.
    #
    # 2) Failed breakout:
    #    Previous close was above R1 OR current high pushed
    #    materially above R1, but current close is back below.
    # --------------------------------------------------------

    if r1 > 0:

        failed_breakout = (
            (
                previous_close > r1
                or
                high >= r1 + breakout_buffer(r1)
            )
            and
            close < r1
        )

        classic_rejection = (
            high >= r1
            and
            close < r1
            and
            close < open_price
        )

        if failed_breakout or classic_rejection:

            result["direction"] = "RESISTANCE"
            result["level"] = "R1"
            result["confirmed"] = True

            if failed_breakout:
                result["type"] = "FAILED_BREAKOUT"
                result["reason"] = (
                    "R1 üstü deneme başarısız; fiyat tekrar "
                    "R1 altına kapandı."
                )
            else:
                result["type"] = "WICK_REJECTION"
                result["reason"] = (
                    "R1 teması sonrası bearish mum ile "
                    "R1 altında kapanış."
                )

            return result

    # --------------------------------------------------------
    # SUPPORT BOUNCE
    #
    # Symmetric logic:
    # failed breakdown reclaim or classical bullish rejection.
    # --------------------------------------------------------

    if s1 > 0:

        failed_breakdown = (
            (
                previous_close < s1
                or
                low <= s1 - breakout_buffer(s1)
            )
            and
            close > s1
        )

        classic_bounce = (
            low <= s1
            and
            close > s1
            and
            close > open_price
        )

        if failed_breakdown or classic_bounce:

            result["direction"] = "SUPPORT"
            result["level"] = "S1"
            result["confirmed"] = True

            if failed_breakdown:
                result["type"] = "FAILED_BREAKDOWN"
                result["reason"] = (
                    "S1 altı deneme başarısız; fiyat tekrar "
                    "S1 üstüne kapandı."
                )
            else:
                result["type"] = "WICK_BOUNCE"
                result["reason"] = (
                    "S1 teması sonrası bullish mum ile "
                    "S1 üzerinde kapanış."
                )

            return result

    return result


# ============================================================
# SWING HIGH
# ============================================================

def calculate_swing_high(df):

    if not validate_dataframe(df):
        return 0.0

    data = clean_dataframe(df)

    if data.empty:
        return 0.0

    if len(data) < SWING_WINDOW * 2 + 1:

        return round(
            safe_float(
                data["High"].max()
            ),
            2
        )

    highs = data["High"].to_numpy()

    start = (
        len(highs)
        - SWING_WINDOW
        - 1
    )

    for i in range(
        start,
        SWING_WINDOW - 1,
        -1
    ):

        center = safe_float(
            highs[i]
        )

        left = highs[
            i - SWING_WINDOW:i
        ]

        right = highs[
            i + 1:
            i + SWING_WINDOW + 1
        ]

        if (
            center > max(left)
            and
            center > max(right)
        ):

            return round(
                center,
                2
            )

    return round(
        safe_float(
            data["High"].max()
        ),
        2
    )


# ============================================================
# SWING LOW
# ============================================================

def calculate_swing_low(df):

    if not validate_dataframe(df):
        return 0.0

    data = clean_dataframe(df)

    if data.empty:
        return 0.0

    if len(data) < SWING_WINDOW * 2 + 1:

        return round(
            safe_float(
                data["Low"].min()
            ),
            2
        )

    lows = data["Low"].to_numpy()

    start = (
        len(lows)
        - SWING_WINDOW
        - 1
    )

    for i in range(
        start,
        SWING_WINDOW - 1,
        -1
    ):

        center = safe_float(
            lows[i]
        )

        left = lows[
            i - SWING_WINDOW:i
        ]

        right = lows[
            i + 1:
            i + SWING_WINDOW + 1
        ]

        if (
            center < min(left)
            and
            center < min(right)
        ):

            return round(
                center,
                2
            )

    return round(
        safe_float(
            data["Low"].min()
        ),
        2
    )


# ============================================================
# RESISTANCE REJECTION
# ============================================================

def resistance_rejection(df, sr):

    return (
        analyze_rejection(
            df,
            sr
        )["direction"]
        ==
        "RESISTANCE"
    )


# ============================================================
# SUPPORT BOUNCE
# ============================================================

def support_bounce(df, sr):

    return (
        analyze_rejection(
            df,
            sr
        )["direction"]
        ==
        "SUPPORT"
    )


# ============================================================
# BREAKOUT STRENGTH
# ============================================================

def breakout_strength(df):

    if not validate_dataframe(df):
        return 0.0

    data = clean_dataframe(df)

    if data.empty:
        return 0.0

    last = data.iloc[-1]

    open_price = safe_float(
        last["Open"]
    )

    close = safe_float(
        last["Close"]
    )

    high = safe_float(
        last["High"]
    )

    low = safe_float(
        last["Low"]
    )

    body = abs(
        close - open_price
    )

    candle_range = (
        high - low
    )

    if candle_range <= 0:
        return 0.0

    body_strength = (
        body /
        candle_range *
        100
    )

    vol_ratio = calculate_volume_ratio(
        data
    )

    volume_strength = min(
        vol_ratio /
        2.0 *
        100,
        100
    )

    strength = (
        body_strength * 0.60
        +
        volume_strength * 0.40
    )

    return round(
        min(strength, 100),
        1
    )


# ============================================================
# LEVEL STRENGTH
# ============================================================

def calculate_level_strength(
    df,
    level,
    tolerance=None
):

    result = {
        "touches": 0,
        "rejections": 0,
        "breakouts": 0,
        "strength": 0
    }

    if not validate_dataframe(df):
        return result

    level = safe_float(
        level,
        0
    )

    if level <= 0:
        return result

    data = clean_dataframe(df)

    if data.empty:
        return result

    if tolerance is None:

        tolerance = (
            level *
            LEVEL_TOLERANCE_PERCENT /
            100
        )

    else:

        tolerance = safe_float(
            tolerance,
            0.30
        )

    if tolerance <= 0:

        tolerance = (
            level *
            LEVEL_TOLERANCE_PERCENT /
            100
        )

    # PERFORMANCE OPTIMIZATION:
    # The original implementation repeatedly used Series.iloc inside a Python
    # loop. Converting the four columns to NumPy arrays once preserves the
    # exact decision logic while removing thousands of pandas indexing calls.
    highs = data["High"].to_numpy(dtype=float, copy=False)
    lows = data["Low"].to_numpy(dtype=float, copy=False)
    closes = data["Close"].to_numpy(dtype=float, copy=False)

    for i in range(1, len(data)):

        high = highs[i]
        low = lows[i]
        close = closes[i]
        previous_close = closes[i - 1]

        touched = (
            abs(high - level) <= tolerance
            or
            abs(low - level) <= tolerance
            or
            low <= level <= high
        )

        if not touched:
            continue

        result["touches"] += 1

        if (
            previous_close <= level
            and
            close < level
        ):

            result["rejections"] += 1

        elif (
            previous_close >= level
            and
            close > level
        ):

            result["rejections"] += 1

        if (
            previous_close <= level
            and
            close > level + tolerance
        ):

            result["breakouts"] += 1

        elif (
            previous_close >= level
            and
            close < level - tolerance
        ):

            result["breakouts"] += 1

    raw_strength = (
        result["touches"] *
        TOUCH_WEIGHT
        +
        result["rejections"] *
        REJECTION_WEIGHT
        +
        result["breakouts"] *
        BREAKOUT_WEIGHT
    )

    result["strength"] = int(
        min(
            raw_strength,
            100
        )
    )

    return result


# ============================================================
# EVENT STRENGTH
# ============================================================

def calculate_event_strength(
    breakout_data,
    event,
    support_strength,
    resistance_strength,
    volume_ratio_value
):

    event = safe_string(event)

    volume_value = safe_float(
        volume_ratio_value,
        0.0
    )

    volume_score = min(
        volume_value /
        2.0 *
        100,
        100
    )

    support_score = safe_float(
        support_strength.get("strength"),
        0
    )

    resistance_score = safe_float(
        resistance_strength.get("strength"),
        0
    )

    breakout_score = safe_float(
        breakout_data.get("strength"),
        0
    )

    if event == "RESISTANCE_BREAK":

        score = (
            breakout_score *
            EVENT_BREAKOUT_WEIGHT
            +
            resistance_score *
            EVENT_LEVEL_WEIGHT
            +
            volume_score *
            EVENT_VOLUME_WEIGHT
        )

        return round(
            min(score, 100),
            1
        )

    if event == "SUPPORT_BREAK":

        score = (
            breakout_score *
            EVENT_BREAKOUT_WEIGHT
            +
            support_score *
            EVENT_LEVEL_WEIGHT
            +
            volume_score *
            EVENT_VOLUME_WEIGHT
        )

        return round(
            min(score, 100),
            1
        )

    if event == "RESISTANCE_REJECTION":

        score = (
            resistance_score * 0.70
            +
            volume_score * 0.30
        )

        return round(
            min(score, 100),
            1
        )

    if event == "SUPPORT_BOUNCE":

        score = (
            support_score * 0.70
            +
            volume_score * 0.30
        )

        return round(
            min(score, 100),
            1
        )

    strongest_level = max(
        support_score,
        resistance_score
    )

    score = (
        strongest_level * 0.70
        +
        volume_score * 0.30
    )

    return round(
        min(score, 100),
        1
    )


# ============================================================
# SR EVENT ENGINE
# ============================================================

def detect_sr_events(
    df,
    price,
    sr
):

    if not isinstance(sr, dict):
        sr = {}

    zone = detect_price_zone(
        price,
        sr
    )

    breakout = analyze_breakout(
        df,
        sr
    )

    rejection = analyze_rejection(
        df,
        sr
    )

    # ========================================================
    # 1. STRUCTURAL REJECTION / BOUNCE HAS PRIORITY
    # ========================================================

    if (
        rejection.get("direction")
        == "RESISTANCE"
        and
        rejection.get("confirmed")
        is True
    ):

        signal = "RESISTANCE_REJECTION"
        event = "RESISTANCE_REJECTION"

    elif (
        rejection.get("direction")
        == "SUPPORT"
        and
        rejection.get("confirmed")
        is True
    ):

        signal = "SUPPORT_BOUNCE"
        event = "SUPPORT_BOUNCE"

    # ========================================================
    # 2. RESISTANCE BREAKOUT - STRICT CONFIRMATION
    #
    # Replay audit showed RESISTANCE_BREAK -> CALL was weak.
    # Therefore bullish break requires candle + volume confirm.
    # ========================================================

    elif (
        breakout.get("direction")
        == "BULLISH"
        and
        breakout.get("confirmed")
        is True
    ):

        signal = "BREAKOUT_UP"
        event = "RESISTANCE_BREAK"

    # ========================================================
    # 3. SUPPORT BREAKDOWN - PRESERVE WORKING PUT SIDE
    #
    # v5.4 SUPPORT_BREAK showed materially better replay
    # performance. Do NOT require the new strict confirmation
    # here; the price-buffer breakdown itself remains the event.
    # ========================================================

    elif (
        breakout.get("direction")
        == "BEARISH"
        and
        breakout.get("attempt")
        is True
    ):

        signal = "BREAKOUT_DOWN"
        event = "SUPPORT_BREAK"

    # ========================================================
    # 4. UNCONFIRMED BULLISH BREAK = ATTEMPT ONLY
    # ========================================================

    elif (
        breakout.get("direction")
        == "BULLISH"
        and
        breakout.get("attempt")
        is True
    ):

        signal = "BREAKOUT_ATTEMPT_UP"
        event = "INSIDE_RANGE"

    else:

        signal = "INSIDE_RANGE"
        event = "INSIDE_RANGE"

    return {
        "signal": signal,
        "event": event,
        "zone": zone["zone"],
        "breakout": breakout,
        "rejection": rejection,
        "bounce": (
            rejection.get("direction")
            ==
            "SUPPORT"
        ),
        "breakout_attempt": bool(
            breakout.get(
                "attempt",
                False
            )
        ),
        "breakout_confirmed": bool(
            breakout.get(
                "confirmed",
                False
            )
        ),
        "strength": breakout_strength(df),
        "volume_ratio": calculate_volume_ratio(df)
    }


# ============================================================
# SR BEHAVIOR
# ============================================================

def analyze_sr_behavior(
    current_price,
    previous_price,
    support_1,
    resistance_1,
    tolerance=0.20
):

    result = {
        "signal": "INSIDE_RANGE",
        "event": "INSIDE_RANGE",
        "reason": "",
        "zone": "NONE"
    }

    try:

        current_price = float(
            current_price
        )

        previous_price = float(
            previous_price
        )

        support_1 = float(
            support_1
        )

        resistance_1 = float(
            resistance_1
        )

        tolerance = float(
            tolerance
        )

    except Exception:

        return result

    if (
        previous_price <= resistance_1
        and
        current_price >
        resistance_1 + tolerance
    ):

        result.update({
            "signal": "BREAKOUT_UP",
            "event": "RESISTANCE_BREAK",
            "zone": "R1",
            "reason": "Direnç yukarı kırıldı."
        })

        return result

    if (
        previous_price >= support_1
        and
        current_price <
        support_1 - tolerance
    ):

        result.update({
            "signal": "BREAKOUT_DOWN",
            "event": "SUPPORT_BREAK",
            "zone": "S1",
            "reason": "Destek aşağı kırıldı."
        })

        return result

    if (
        abs(
            current_price -
            resistance_1
        )
        <= tolerance
        and
        current_price <
        previous_price
    ):

        result.update({
            "signal": "REJECT_RESISTANCE",
            "event": "RESISTANCE_REJECTION",
            "zone": "R1",
            "reason": "Dirençten satış geldi."
        })

        return result

    if (
        abs(
            current_price -
            support_1
        )
        <= tolerance
        and
        current_price >
        previous_price
    ):

        result.update({
            "signal": "REJECT_SUPPORT",
            "event": "SUPPORT_BOUNCE",
            "zone": "S1",
            "reason": "Destekten tepki alımı geldi."
        })

        return result

    return result


# ============================================================
# MASTER ANALYZER
# ============================================================

def analyze_support_resistance(
    df,
    price,
    signal=None,
    ema9=None,
    ema21=None,
    vwap=None,
    rsi=None,
    volume_ratio=None,
    gap_direction=None,
    volume_ratio_value=None
):

    if not validate_dataframe(df):

        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "signal": "INSIDE_RANGE",
            "event": "INSIDE_RANGE",
            "behavior": "INSIDE_RANGE",
            "signal_event": "INSIDE_RANGE",
            "breakout": "INSIDE_RANGE",
            "breakout_data": {},
            "rejection": "",
            "rejection_data": {},
            "bounce": "",
            "pivot": 0.0,
            "support": 0.0,
            "support_1": 0.0,
            "support_2": 0.0,
            "resistance": 0.0,
            "resistance_1": 0.0,
            "resistance_2": 0.0,
            "recent_high": 0.0,
            "recent_low": 0.0,
            "nearest_level": {
                "name": None,
                "price": None,
                "distance": None
            },
            "zone": "UNKNOWN",
            "strength": 0.0,
            "breakout_strength": 0.0,
            "support_strength": {},
            "resistance_strength": {},
            "volume_ratio": 0.0,
            "calculated_volume_ratio": 0.0,
            "confirmations": {},
            "swing_high": 0.0,
            "swing_low": 0.0,
            "gap_direction": safe_string(
                gap_direction
            )
        }

    data = clean_dataframe(df)

    if data.empty:

        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "signal": "INSIDE_RANGE",
            "event": "INSIDE_RANGE",
            "behavior": "INSIDE_RANGE",
            "signal_event": "INSIDE_RANGE"
        }

    calculated_volume_ratio = (
        calculate_volume_ratio(data)
    )

    if (
        volume_ratio is not None
        and
        not callable(volume_ratio)
    ):

        effective_volume_ratio = safe_float(
            volume_ratio,
            calculated_volume_ratio
        )

    elif volume_ratio_value is not None:

        effective_volume_ratio = safe_float(
            volume_ratio_value,
            calculated_volume_ratio
        )

    else:

        effective_volume_ratio = (
            calculated_volume_ratio
        )

    levels = calculate_support_resistance(
        data
    )

    s1 = safe_float(
        levels.get("support_1")
    )

    s2 = safe_float(
        levels.get("support_2")
    )

    r1 = safe_float(
        levels.get("resistance_1")
    )

    r2 = safe_float(
        levels.get("resistance_2")
    )

    nearest = nearest_level(
        price,
        levels
    )

    events = detect_sr_events(
        data,
        price,
        levels
    )

    event = safe_string(
        events.get(
            "event"
        ),
        "INSIDE_RANGE"
    )

    signal_event = safe_string(
        events.get(
            "signal"
        ),
        "INSIDE_RANGE"
    )

    s1_strength = calculate_level_strength(
        data,
        s1
    )

    r1_strength = calculate_level_strength(
        data,
        r1
    )

    raw_breakout_strength = breakout_strength(
        data
    )

    strength = calculate_event_strength(
        {
            "strength":
                raw_breakout_strength
        },
        event,
        s1_strength,
        r1_strength,
        effective_volume_ratio
    )

    price_value = safe_float(
        price
    )

    ema9_value = safe_float(
        ema9
    )

    ema21_value = safe_float(
        ema21
    )

    vwap_value = safe_float(
        vwap
    )

    rsi_value = safe_float(
        rsi
    )

    confirmations = {

        "ema_bullish": (
            ema9 is not None
            and
            ema21 is not None
            and
            ema9_value >
            ema21_value
        ),

        "ema_bearish": (
            ema9 is not None
            and
            ema21 is not None
            and
            ema9_value <
            ema21_value
        ),

        "above_vwap": (
            vwap is not None
            and
            price_value >
            vwap_value
        ),

        "below_vwap": (
            vwap is not None
            and
            price_value <
            vwap_value
        ),

        "volume_strong": (
            effective_volume_ratio
            >=
            MIN_BREAKOUT_VOLUME_RATIO
        ),

        "rsi_bullish": (
            rsi is not None
            and
            rsi_value >= 50
        ),

        "rsi_bearish": (
            rsi is not None
            and
            rsi_value < 50
        )
    }

    normalized_gap = safe_string(
        gap_direction
    )

    rejection = ""

    if event == "RESISTANCE_REJECTION":
        rejection = "RESISTANCE"

    elif event == "SUPPORT_BOUNCE":
        rejection = "SUPPORT"

    bounce = ""

    if event == "SUPPORT_BOUNCE":
        bounce = "SUPPORT"

    return {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "signal":
            event,

        "event":
            event,

        "behavior":
            event,

        "signal_event":
            signal_event,

        "breakout":
            signal_event,

        "breakout_data":
            events.get(
                "breakout",
                {}
            ),

        "breakout_attempt":
            events.get(
                "breakout_attempt",
                False
            ),

        "breakout_confirmed":
            events.get(
                "breakout_confirmed",
                False
            ),

        "rejection":
            rejection,

        "rejection_data":
            events.get(
                "rejection",
                {}
            ),

        "bounce":
            bounce,

        "pivot":
            levels.get(
                "pivot",
                0.0
            ),

        "support":
            s1,

        "support_1":
            s1,

        "support_2":
            s2,

        "resistance":
            r1,

        "resistance_1":
            r1,

        "resistance_2":
            r2,

        "recent_high":
            levels.get(
                "recent_high",
                0.0
            ),

        "recent_low":
            levels.get(
                "recent_low",
                0.0
            ),

        "nearest_level":
            nearest,

        "zone":
            events.get(
                "zone",
                "UNKNOWN"
            ),

        "strength":
            strength,

        "breakout_strength":
            raw_breakout_strength,

        "support_strength":
            s1_strength,

        "resistance_strength":
            r1_strength,

        "volume_ratio":
            effective_volume_ratio,

        "calculated_volume_ratio":
            calculated_volume_ratio,

        "confirmations":
            confirmations,

        "swing_high":
            calculate_swing_high(
                data
            ),

        "swing_low":
            calculate_swing_low(
                data
            ),

        "gap_direction":
            normalized_gap
    }


# ============================================================
# HEALTH CHECK
# ============================================================

def support_resistance_health():

    return {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "status":
            "READY",

        "features": [

            "DAILY_PIVOT",
            "S1_S2_R1_R2",
            "RECENT_HIGH_LOW",
            "SWING_LEVELS",
            "BREAKOUT_ATTEMPT",
            "CONFIRMED_BREAKOUT",
            "BREAKOUT",
            "BREAKDOWN",
            "RESISTANCE_REJECTION",
            "SUPPORT_BOUNCE",
            "LEVEL_STRENGTH",
            "EVENT_STRENGTH",
            "VOLUME_CONFIRMATION",
            "REAL_VOLUME_RATIO",
            "SR_EVENT_NORMALIZATION",
            "VOLUME_RATIO_COMPATIBILITY",
            "INTEGRATION_TEST_COMPATIBILITY"
        ]
    }


# ============================================================
# BACKWARD COMPATIBILITY ALIASES
# ============================================================

volume_ratio = calculate_volume_ratio
calculate_sr = calculate_support_resistance
analyze_sr = analyze_support_resistance


# ============================================================
# MODULE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("QQQ PRO SUPPORT / RESISTANCE ENGINE")
    print(f"VERSION : {ENGINE_VERSION}")
    print("STATUS  : READY")
    print("=" * 60)

    print(
        support_resistance_health()
    )