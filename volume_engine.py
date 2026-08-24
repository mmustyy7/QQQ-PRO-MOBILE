# ============================================================
# QQQ PRO v6
# volume_engine.py
#
# Institutional Volume Analysis Engine
#
# Version : 1.1
# ============================================================

import pandas as pd
import numpy as np

# ============================================================
# SETTINGS
# ============================================================

RVOL_PERIOD = 20

PRESSURE_PERIOD = 10

SPIKE_MULTIPLIER = 1.80

BREAKOUT_MULTIPLIER = 1.50

EXHAUSTION_BARS = 6

# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


# ============================================================
# VALIDATE DATAFRAME
# ============================================================

def validate_dataframe(df):
    if df is None:
        return False

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

    for col in required:
        if col not in df.columns:
            return False

    return True


# ============================================================
# AVERAGE VOLUME
# ============================================================

def calculate_average_volume(df):
    if not validate_dataframe(df):
        return 0

    try:
        return int(
            df["Volume"]
            .tail(RVOL_PERIOD)
            .mean()
        )
    except Exception:
        return 0


# ============================================================
# RELATIVE VOLUME
# ============================================================

def calculate_relative_volume(df):
    if not validate_dataframe(df):
        return 1.0

    avg = calculate_average_volume(df)

    if avg <= 0:
        return 1.0

    current = safe_float(
        df["Volume"].iloc[-1]
    )

    return round(
        current / avg,
        2
    )


# ============================================================
# VOLUME SPIKE
# ============================================================

def detect_volume_spike(df):
    result = {
        "spike": False,
        "ratio": 1.0
    }

    if not validate_dataframe(df):
        return result

    avg = calculate_average_volume(df)

    if avg <= 0:
        return result

    current = safe_float(
        df["Volume"].iloc[-1]
    )

    ratio = current / avg

    result["ratio"] = round(ratio, 2)

    if ratio >= SPIKE_MULTIPLIER:
        result["spike"] = True

    return result


# ============================================================
# ABSORPTION DETECTION
# ============================================================

def detect_absorption(df, volume_ratio=1.0):
    """
    Kurumsal Absorption tespiti.
    """
    result = {
        "detected": False,
        "type": "NONE",
        "strength": 0
    }

    if not validate_dataframe(df):
        return result

    if len(df) < 5:
        return result

    last = df.iloc[-1]

    open_price = safe_float(last["Open"])
    high = safe_float(last["High"])
    low = safe_float(last["Low"])
    close = safe_float(last["Close"])

    candle_range = high - low

    if candle_range <= 0:
        return result

    body = abs(close - open_price)

    body_ratio = body / candle_range

    last_volume = safe_float(last["Volume"])

    avg_volume = safe_float(
        df["Volume"].tail(20).mean()
    )

    if avg_volume <= 0:
        return result

    volume_multiple = last_volume / avg_volume

    if (
        volume_multiple >= 2.0
        and
        body_ratio <= 0.30
    ):
        result["detected"] = True

        strength = (
            (volume_multiple * 30)
            +
            ((1 - body_ratio) * 40)
            +
            (volume_ratio * 20)
        )

        strength = max(
            0,
            min(
                int(strength),
                100
            )
        )

        result["strength"] = strength

        if close >= open_price:
            result["type"] = "BUYING"
        else:
            result["type"] = "SELLING"

    return result


# ============================================================
# CLIMAX VOLUME DETECTION
# ============================================================

def detect_climax_volume(df, lookback=30):
    """
    Climax Volume tespiti.
    """
    result = {
        "detected": False,
        "type": "NONE",
        "strength": 0
    }

    if not validate_dataframe(df):
        return result

    if len(df) < lookback:
        return result

    recent = df.tail(lookback)

    last = recent.iloc[-1]

    last_volume = safe_float(last["Volume"])

    max_volume = safe_float(
        recent["Volume"].max()
    )

    if max_volume <= 0:
        return result

    if last_volume < max_volume:
        return result

    open_price = safe_float(last["Open"])
    close = safe_float(last["Close"])
    high = safe_float(last["High"])
    low = safe_float(last["Low"])

    candle_range = high - low

    if candle_range <= 0:
        return result

    body = abs(close - open_price)

    upper_wick = high - max(
        open_price,
        close
    )

    lower_wick = min(
        open_price,
        close
    ) - low

    body_ratio = body / candle_range
    upper_ratio = upper_wick / candle_range
    lower_ratio = lower_wick / candle_range

    if (
        close > open_price
        and
        upper_ratio >= 0.40
        and
        body_ratio <= 0.50
    ):
        strength = (
            50
            +
            int(upper_ratio * 50)
        )

        result["detected"] = True
        result["type"] = "BUYING_CLIMAX"
        result["strength"] = min(strength, 100)

        return result

    if (
        close < open_price
        and
        lower_ratio >= 0.40
        and
        body_ratio <= 0.50
    ):
        strength = (
            50
            +
            int(lower_ratio * 50)
        )

        result["detected"] = True
        result["type"] = "SELLING_CLIMAX"
        result["strength"] = min(strength, 100)

        return result

    return result


# ============================================================
# VOLUME DRY-UP DETECTION
# ============================================================

def detect_volume_dryup(df, lookback=10):
    result = {
        "detected": False,
        "strength": 0,
        "volume_drop": 0.0,
        "range_compression": 0.0
    }

    if not validate_dataframe(df):
        return result

    if len(df) < lookback + 5:
        return result

    recent = df.tail(lookback)

    volumes = recent["Volume"]

    current_avg = safe_float(
        volumes.mean()
    )

    previous_avg = safe_float(
        df["Volume"]
        .tail(lookback * 2)
        .head(lookback)
        .mean()
    )

    if previous_avg <= 0:
        return result

    volume_drop = (
        (previous_avg - current_avg)
        /
        previous_avg
    ) * 100

    recent_range = safe_float(
        (recent["High"] - recent["Low"]).mean()
    )

    previous_range = safe_float(
        (
            df["High"]
            .tail(lookback * 2)
            .head(lookback)
            -
            df["Low"]
            .tail(lookback * 2)
            .head(lookback)
        ).mean()
    )

    if previous_range <= 0:
        return result

    range_drop = (
        (previous_range - recent_range)
        /
        previous_range
    ) * 100

    result["volume_drop"] = round(volume_drop, 1)
    result["range_compression"] = round(range_drop, 1)

    if (
        volume_drop >= 25
        and
        range_drop >= 20
    ):
        strength = int(
            (
                volume_drop * 0.6
            ) +
            (
                range_drop * 0.4
            )
        )

        result["detected"] = True
        result["strength"] = min(
            strength,
            100
        )

    return result


# ============================================================
# VOLUME DIVERGENCE DETECTION
# ============================================================

def detect_volume_divergence(df, lookback=10):
    result = {
        "detected": False,
        "type": "NONE",
        "strength": 0
    }

    if not validate_dataframe(df):
        return result

    if len(df) < lookback + 5:
        return result

    recent = df.tail(lookback)
    previous = df.tail(lookback * 2).head(lookback)

    recent_high = safe_float(recent["High"].max())
    previous_high = safe_float(previous["High"].max())

    recent_low = safe_float(recent["Low"].min())
    previous_low = safe_float(previous["Low"].min())

    recent_volume = safe_float(recent["Volume"].mean())
    previous_volume = safe_float(previous["Volume"].mean())

    if previous_volume <= 0:
        return result

    volume_change = (
        (recent_volume - previous_volume)
        /
        previous_volume
    ) * 100

    if (
        recent_high > previous_high
        and
        volume_change < -10
    ):
        strength = int(
            min(
                abs(volume_change) * 2,
                100
            )
        )
        result["detected"] = True
        result["type"] = "BEARISH_DIVERGENCE"
        result["strength"] = strength
        return result

    if (
        recent_low < previous_low
        and
        volume_change < -10
    ):
        strength = int(
            min(
                abs(volume_change) * 2,
                100
            )
        )
        result["detected"] = True
        result["type"] = "BULLISH_DIVERGENCE"
        result["strength"] = strength
        return result

    if (
        recent_high > previous_high
        and
        volume_change > 15
    ):
        result["detected"] = True
        result["type"] = "BULLISH_CONFIRMATION"
        result["strength"] = min(
            int(volume_change),
            100
        )
        return result

    if (
        recent_low < previous_low
        and
        volume_change > 15
    ):
        result["detected"] = True
        result["type"] = "BEARISH_CONFIRMATION"
        result["strength"] = min(
            int(volume_change),
            100
        )
        return result

    return result


# ============================================================
# BUY PRESSURE
# ============================================================

def calculate_buy_pressure(df):
    if not validate_dataframe(df):
        return 50

    recent = df.tail(PRESSURE_PERIOD)

    buy = 0
    sell = 0

    for _, row in recent.iterrows():
        volume = safe_float(row["Volume"])

        if row["Close"] >= row["Open"]:
            buy += volume
        else:
            sell += volume

    total = buy + sell

    if total <= 0:
        return 50

    return round(
        (buy / total) * 100,
        1
    )


# ============================================================
# SELL PRESSURE
# ============================================================

def calculate_sell_pressure(df):
    return round(
        100 -
        calculate_buy_pressure(df),
        1
    )


# ============================================================
# TREND CONFIRMATION
# ============================================================

def detect_volume_confirmation(df):
    if not validate_dataframe(df):
        return False

    if len(df) < 5:
        return False

    last = df.tail(5)

    volume_up = (
        safe_float(last["Volume"].iloc[-1])
        >
        safe_float(last["Volume"].iloc[0])
    )

    price_up = (
        safe_float(last["Close"].iloc[-1])
        >
        safe_float(last["Close"].iloc[0])
    )

    return volume_up == price_up


# ============================================================
# BREAKOUT CONFIRMATION
# ============================================================

def detect_breakout_confirmation(df):
    if not validate_dataframe(df):
        return False

    spike = detect_volume_spike(df)

    if not spike["spike"]:
        return False

    last = df.iloc[-1]

    body = abs(
        safe_float(last["Close"])
        -
        safe_float(last["Open"])
    )

    candle = (
        safe_float(last["High"])
        -
        safe_float(last["Low"])
    )

    if candle <= 0:
        return False

    strength = body / candle

    return strength >= 0.60


# ============================================================
# REJECTION CONFIRMATION
# ============================================================

def detect_rejection_confirmation(df):
    if not validate_dataframe(df):
        return False

    spike = detect_volume_spike(df)

    if not spike["spike"]:
        return False

    last = df.iloc[-1]

    upper = (
        safe_float(last["High"])
        -
        max(
            safe_float(last["Open"]),
            safe_float(last["Close"])
        )
    )

    candle = (
        safe_float(last["High"])
        -
        safe_float(last["Low"])
    )

    if candle <= 0:
        return False

    return (
        upper / candle
    ) >= 0.40


# ============================================================
# VOLUME EXHAUSTION
# ============================================================

def detect_volume_exhaustion(df):
    if not validate_dataframe(df):
        return False

    if len(df) < EXHAUSTION_BARS:
        return False

    recent = df.tail(EXHAUSTION_BARS)

    closes = recent["Close"].values
    volumes = recent["Volume"].values

    price_up = True
    for i in range(1, len(closes)):
        if closes[i] <= closes[i - 1]:
            price_up = False
            break

    volume_down = True
    for i in range(1, len(volumes)):
        if volumes[i] >= volumes[i - 1]:
            volume_down = False
            break

    return price_up and volume_down


# ============================================================
# VOLUME SCORE
# ============================================================

def calculate_volume_score(df):
    score = 0

    rvol = calculate_relative_volume(df)
    buy = calculate_buy_pressure(df)
    spike = detect_volume_spike(df)
    confirm = detect_volume_confirmation(df)
    breakout = detect_breakout_confirmation(df)
    rejection = detect_rejection_confirmation(df)
    exhaustion = detect_volume_exhaustion(df)

    if rvol >= 2.0:
        score += 25
    elif rvol >= 1.5:
        score += 20
    elif rvol >= 1.2:
        score += 15
    elif rvol >= 1.0:
        score += 10
    else:
        score += 5

    score += int((buy / 100) * 25)

    if spike["spike"]:
        score += 15

    if confirm:
        score += 20

    if breakout:
        score += 15

    if rejection:
        score += 10

    if exhaustion:
        score -= 10

    score = max(0, min(score, 100))

    return score


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(df):
    score = calculate_volume_score(df)
    rvol = calculate_relative_volume(df)
    confidence = score

    if rvol >= 2:
        confidence += 5

    if detect_volume_confirmation(df):
        confidence += 5

    if detect_breakout_confirmation(df):
        confidence += 5

    confidence = min(confidence, 100)

    return confidence


# ============================================================
# STATE
# ============================================================

def calculate_volume_state(score):
    if score >= 90:
        return "STRONG_BUYING"
    if score >= 70:
        return "BUYING"
    if score >= 40:
        return "NEUTRAL"
    if score >= 20:
        return "SELLING"
    return "STRONG_SELLING"


# ============================================================
# SIGNAL
# ============================================================

def calculate_signal(score):
    if score >= 80:
        return "BUY_CONFIRMATION"
    if score <= 20:
        return "SELL_CONFIRMATION"
    return "NO_VOLUME_CONFIRMATION"


# ============================================================
# INSTITUTIONAL BUYING
# ============================================================

def detect_institutional_buying(market):
    result = {
        "active": False,
        "score": 0,
        "reason": []
    }

    if not market:
        return result

    price = safe_float(market.get("price"))
    ema9 = safe_float(market.get("ema9"))
    ema21 = safe_float(market.get("ema21"))
    vwap = safe_float(market.get("vwap"))
    rvol = safe_float(market.get("relative_volume"), 1)
    trend = market.get("trend", "")

    df = market.get("df_5m")

    if not validate_dataframe(df):
        return result

    score = 0

    if price > vwap:
        score += 20
        result["reason"].append("VWAP üstü")

    if ema9 > ema21:
        score += 20
        result["reason"].append("EMA9>EMA21")

    if rvol >= 1.5:
        score += 20
        result["reason"].append("RVOL yüksek")

    if trend == "UP":
        score += 20
        result["reason"].append("Trend yukarı")

    if calculate_buy_pressure(df) >= 65:
        score += 20
        result["reason"].append("Alım baskısı")

    result["score"] = score
    result["active"] = score >= 80

    return result


# ============================================================
# INSTITUTIONAL SELLING
# ============================================================

def detect_institutional_selling(market):
    result = {
        "active": False,
        "score": 0,
        "reason": []
    }

    if not market:
        return result

    price = safe_float(market.get("price"))
    ema9 = safe_float(market.get("ema9"))
    ema21 = safe_float(market.get("ema21"))
    vwap = safe_float(market.get("vwap"))
    rvol = safe_float(market.get("relative_volume"), 1)
    trend = market.get("trend", "")

    df = market.get("df_5m")

    if not validate_dataframe(df):
        return result

    score = 0

    if price < vwap:
        score += 20
        result["reason"].append("VWAP altı")

    if ema9 < ema21:
        score += 20
        result["reason"].append("EMA9<EMA21")

    if rvol >= 1.5:
        score += 20
        result["reason"].append("RVOL yüksek")

    if trend == "DOWN":
        score += 20
        result["reason"].append("Trend aşağı")

    if calculate_sell_pressure(df) >= 65:
        score += 20
        result["reason"].append("Satış baskısı")

    result["score"] = score
    result["active"] = score >= 80

    return result


# ============================================================
# VWAP CONFIRMATION
# ============================================================

def detect_vwap_confirmation(market):
    if not market:
        return False

    price = safe_float(market.get("price"))
    vwap = safe_float(market.get("vwap"))
    trend = market.get("trend")

    if trend == "UP":
        return price > vwap

    if trend == "DOWN":
        return price < vwap

    return False


# ============================================================
# SUPPORT VOLUME
# ============================================================

def detect_support_volume(market):
    if not market:
        return False
    df = market.get("df_5m")

    if not validate_dataframe(df):
        return False

    pressure = calculate_buy_pressure(df)

    rvol = safe_float(
        market.get("relative_volume"),
        1
    )

    return pressure >= 65 and rvol >= 1.2


# ============================================================
# RESISTANCE VOLUME
# ============================================================

def detect_resistance_volume(market):
    if not market:
        return False
    df = market.get("df_5m")

    if not validate_dataframe(df):
        return False

    pressure = calculate_sell_pressure(df)

    rvol = safe_float(
        market.get("relative_volume"),
        1
    )

    return pressure >= 65 and rvol >= 1.2


# ============================================================
# GAP VOLUME
# ============================================================

def detect_gap_volume(market):
    if not market:
        return "NONE"

    gap = market.get("gap", {})
    direction = gap.get("direction", "NONE")

    rvol = safe_float(
        market.get("relative_volume"),
        1
    )

    if direction == "UP" and rvol > 1.5:
        return "GAP_UP_CONFIRMED"

    if direction == "DOWN" and rvol > 1.5:
        return "GAP_DOWN_CONFIRMED"

    return "NONE"


# ============================================================
# TREND VOLUME (Düzeltme 2)
# ============================================================

def detect_trend_volume(market):
    if not market:
        return False

    df = market.get("df_5m")
    if not validate_dataframe(df):
        return False

    trend = market.get("trend", "")

    buy = calculate_buy_pressure(df)
    sell = calculate_sell_pressure(df)

    if trend == "UP" and buy > 60:
        return True

    if trend == "DOWN" and sell > 60:
        return True

    return False


# ============================================================
# VOLUME QUALITY (Düzeltme 3)
# ============================================================

def calculate_volume_quality(market):
    if not market:
        return 0

    score = 0

    if detect_vwap_confirmation(market):
        score += 20

    if detect_trend_volume(market):
        score += 20

    if detect_support_volume(market):
        score += 20

    if detect_resistance_volume(market):
        score += 20

    df = market.get("df_5m")
    if validate_dataframe(df):
        if detect_volume_spike(df)["spike"]:
            score += 20

    return score


# ============================================================
# VOLUME PROBABILITY
# ============================================================

def calculate_volume_probability(market):
    quality = calculate_volume_quality(
        market
    )

    df = market.get("df_5m")
    score = calculate_volume_score(df) if validate_dataframe(df) else 0

    probability = (
        quality * 0.40 +
        score * 0.60
    )

    return round(probability, 1)


# ============================================================
# INSTITUTIONAL ANALYZE VOLUME (Düzeltme 1 ve 4)
# ============================================================

def analyze_volume(market):
    """
    Institutional Volume Engine
    """
    result = {
        "score": 0,
        "final_score": 0,  # Decision Engine uyumluluğu
        "confidence": 0,
        "state": "NEUTRAL",
        "signal": "NO_VOLUME_CONFIRMATION",
        "average_volume": 0,
        "relative_volume": 1.0,
        "buy_pressure": 50,
        "sell_pressure": 50,
        "volume_spike": False,
        "trend_confirmation": False,
        "breakout_confirmation": False,
        "rejection_confirmation": False,
        "institutional_buying": False,
        "institutional_selling": False,
        "support_volume": False,
        "resistance_volume": False,
        "gap_volume": "NONE",
        "volume_quality": 0,
        "probability": 0,
        "exhaustion": False,
        "reason": []
    }

    if not market:
        return result

    df = market.get("df_5m")

    if not validate_dataframe(df):
        return result

    # ----------------------------------------------------
    # BASIC VALUES
    # ----------------------------------------------------

    result["average_volume"] = calculate_average_volume(df)
    result["relative_volume"] = calculate_relative_volume(df)
    result["buy_pressure"] = calculate_buy_pressure(df)
    result["sell_pressure"] = calculate_sell_pressure(df)

    spike = detect_volume_spike(df)
    result["volume_spike"] = spike["spike"]

    result["trend_confirmation"] = detect_volume_confirmation(df)
    result["breakout_confirmation"] = detect_breakout_confirmation(df)
    result["rejection_confirmation"] = detect_rejection_confirmation(df)
    result["exhaustion"] = detect_volume_exhaustion(df)

    # ----------------------------------------------------
    # INSTITUTIONAL
    # ----------------------------------------------------

    buying = detect_institutional_buying(market)
    selling = detect_institutional_selling(market)

    result["institutional_buying"] = buying["active"]
    result["institutional_selling"] = selling["active"]

    result["support_volume"] = detect_support_volume(market)
    result["resistance_volume"] = detect_resistance_volume(market)
    result["gap_volume"] = detect_gap_volume(market)

    result["volume_quality"] = calculate_volume_quality(market)
    result["probability"] = calculate_volume_probability(market)

    # ----------------------------------------------------
    # SCORE & FINAL SCORE
    # ----------------------------------------------------

    score = calculate_volume_score(df)

    score += int(result["volume_quality"] * 0.25)

    if buying["active"]:
        score += 15

    if selling["active"]:
        score += 15

    if result["trend_confirmation"]:
        score += 5

    if result["breakout_confirmation"]:
        score += 5

    if result["exhaustion"]:
        score -= 10

    score = max(0, min(score, 100))

    result["score"] = score
    result["final_score"] = score  # Standart uyumluluk için eklendi

    # ----------------------------------------------------
    # CONFIDENCE
    # ----------------------------------------------------

    confidence = score

    confidence += int(result["probability"] * 0.15)

    confidence = max(0, min(confidence, 100))

    result["confidence"] = confidence

    # ----------------------------------------------------
    # STATE
    # ----------------------------------------------------

    result["state"] = calculate_volume_state(score)

    # ----------------------------------------------------
    # SIGNAL
    # ----------------------------------------------------

    if buying["active"] and confidence >= 85:
        result["signal"] = "BUY_CONFIRMATION"
        result["reason"] = buying["reason"]

    elif selling["active"] and confidence >= 85:
        result["signal"] = "SELL_CONFIRMATION"
        result["reason"] = selling["reason"]

    else:
        result["signal"] = "NO_VOLUME_CONFIRMATION"

    return result