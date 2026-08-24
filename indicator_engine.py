# ============================================================
# QQQ PRO v6
# indicator_engine.py
#
# Institutional Indicator Analysis Engine
#
# Version : 6.0
#
# Sorumluluk:
#   Indicators.py tarafından hesaplanan indikatörleri
#   yorumlayarak Decision Engine'e standart skor üretmek.
#
# Bu dosya indikatör HESAPLAMAZ.
# Sadece ANALİZ eder.
# ============================================================

import numpy as np
import pandas as pd

from indicators import (
    hesapla_ema,
    hesapla_rsi,
    hesapla_vwap,
    hesapla_atr,
    hesapla_macd
)

# ============================================================
# CONSTANTS
# ============================================================

EMA_FAST = 9
EMA_MID = 21
EMA_SLOW = 50
EMA_LONG = 200

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

ADX_STRONG = 25

CONFIDENCE_MAX = 100

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
# DATAFRAME VALIDATION
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
# DEFAULT RESULT
# ============================================================

def default_result():
    return {
        "signal": "WAIT",
        "score": 50,
        "confidence": 50,
        "bias": "NEUTRAL",
        "trend_score": 50,
        "momentum_score": 50,
        "volatility_score": 50,
        "reasons": [],
        "warnings": []
    }


# ============================================================
# NORMALIZE SCORE
# ============================================================

def normalize_score(score):
    score = safe_float(score)

    if score < 0:
        return 0

    if score > 100:
        return 100

    return round(score, 1)


# ============================================================
# SCORE TO BIAS
# ============================================================

def score_to_bias(score):
    score = normalize_score(score)

    if score >= 65:
        return "BULLISH"

    if score <= 35:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# SCORE TO SIGNAL
# ============================================================

def score_to_signal(score):
    score = normalize_score(score)

    if score >= 80:
        return "CALL"

    if score >= 65:
        return "CALL_SETUP"

    if score <= 20:
        return "PUT"

    if score <= 35:
        return "PUT_SETUP"

    return "WAIT"


# ============================================================
# CONFIDENCE CALCULATOR
# ============================================================

def calculate_confidence(scores):
    if not scores:
        return 50

    scores = np.array(scores, dtype=float)

    mean_score = scores.mean()

    std = scores.std()

    confidence = 100 - (std * 2)

    confidence = max(0, min(100, confidence))

    return round(confidence, 1)


# ============================================================
# SCORE WEIGHTED AVERAGE
# ============================================================

def weighted_score(values, weights):
    if len(values) != len(weights):
        return 50

    total_weight = sum(weights)

    if total_weight == 0:
        return 50

    score = sum(
        v * w
        for v, w in zip(values, weights)
    ) / total_weight

    return normalize_score(score)


# ============================================================
# EMA ALIGNMENT
# ============================================================

def analyze_ema_alignment(df):
    """
    EMA hizalamasını analiz eder.

    Döndürür

    score
    bias
    reason
    """

    result = {
        "score": 50,
        "bias": "NEUTRAL",
        "reason": ""
    }

    if not validate_dataframe(df):
        return result

    close = df["Close"]

    ema9 = hesapla_ema(close, EMA_FAST).iloc[-1]
    ema21 = hesapla_ema(close, EMA_MID).iloc[-1]
    ema50 = hesapla_ema(close, EMA_SLOW).iloc[-1]
    ema200 = hesapla_ema(close, EMA_LONG).iloc[-1]

    # Perfect Bull Alignment
    if ema9 > ema21 > ema50 > ema200:
        result["score"] = 100
        result["bias"] = "BULLISH"
        result["reason"] = "EMA hizalaması güçlü yukarı."
        return result

    # Perfect Bear Alignment
    if ema9 < ema21 < ema50 < ema200:
        result["score"] = 0
        result["bias"] = "BEARISH"
        result["reason"] = "EMA hizalaması güçlü aşağı."
        return result

    score = 50

    if ema9 > ema21:
        score += 15
    else:
        score -= 15

    if ema21 > ema50:
        score += 10
    else:
        score -= 10

    if ema50 > ema200:
        score += 10
    else:
        score -= 10

    result["score"] = normalize_score(score)
    result["bias"] = score_to_bias(score)

    return result


# ============================================================
# EMA SLOPE
# ============================================================

def analyze_ema_slope(df):
    """
    EMA9 eğimini analiz eder.
    """

    result = {
        "score": 50,
        "slope": 0,
        "reason": ""
    }

    if not validate_dataframe(df):
        return result

    ema = hesapla_ema(
        df["Close"],
        EMA_FAST
    )

    if len(ema) < 6:
        return result

    slope = ema.iloc[-1] - ema.iloc[-6]

    result["slope"] = round(
        slope,
        4
    )

    score = 50

    if slope > 0:
        score += min(
            slope * 50,
            50
        )
        result["reason"] = "EMA yukarı eğimli."

    elif slope < 0:
        score -= min(
            abs(slope) * 50,
            50
        )
        result["reason"] = "EMA aşağı eğimli."

    result["score"] = normalize_score(score)

    return result


# ============================================================
# EMA SEPARATION
# ============================================================

def analyze_ema_separation(df):
    """
    EMA9 ile EMA21 arasındaki mesafeyi ölçer.

    Trendin olgunluğunu gösterir.
    """

    result = {
        "distance": 0,
        "score": 50
    }

    if not validate_dataframe(df):
        return result

    ema9 = hesapla_ema(
        df["Close"],
        EMA_FAST
    ).iloc[-1]

    ema21 = hesapla_ema(
        df["Close"],
        EMA_MID
    ).iloc[-1]

    price = safe_float(
        df["Close"].iloc[-1]
    )

    if price <= 0:
        return result

    distance = abs(
        ema9 - ema21
    ) / price * 100

    result["distance"] = round(
        distance,
        2
    )

    score = min(
        distance * 30,
        100
    )

    result["score"] = normalize_score(
        score
    )

    return result


# ============================================================
# VWAP POSITION
# ============================================================

def analyze_vwap_position(df):
    """
    Fiyatın VWAP'a göre konumu.
    """

    result = {
        "score": 50,
        "bias": "NEUTRAL",
        "reason": ""
    }

    if not validate_dataframe(df):
        return result

    price = safe_float(
        df["Close"].iloc[-1]
    )

    vwap = safe_float(
        hesapla_vwap(df).iloc[-1]
    )

    if price > vwap:
        result["score"] = 80
        result["bias"] = "BULLISH"
        result["reason"] = "VWAP üzerinde."

    elif price < vwap:
        result["score"] = 20
        result["bias"] = "BEARISH"
        result["reason"] = "VWAP altında."

    return result


# ============================================================
# VWAP DISTANCE
# ============================================================

def analyze_vwap_distance(df):
    """
    VWAP uzaklığını analiz eder.
    """

    result = {
        "distance": 0,
        "score": 50
    }

    if not validate_dataframe(df):
        return result

    price = safe_float(
        df["Close"].iloc[-1]
    )

    vwap = safe_float(
        hesapla_vwap(df).iloc[-1]
    )

    if vwap <= 0:
        return result

    distance = (
        abs(
            price - vwap
        )
        /
        vwap
    ) * 100

    result["distance"] = round(
        distance,
        2
    )

    score = 50

    if distance < 0.30:
        score = 80

    elif distance < 0.80:
        score = 65

    elif distance > 2:
        score = 35

    result["score"] = normalize_score(
        score
    )

    return result


# ============================================================
# RSI ANALYSIS
# ============================================================

def analyze_rsi(df):
    """
    RSI seviyesini analiz eder.
    """

    result = {
        "score": 50,
        "bias": "NEUTRAL",
        "rsi": 50,
        "state": "NORMAL"
    }

    if not validate_dataframe(df):
        return result

    rsi = safe_float(
        hesapla_rsi(df["Close"]).iloc[-1]
    )

    result["rsi"] = round(rsi, 2)

    if rsi <= 20:
        result["score"] = 90
        result["bias"] = "BULLISH"
        result["state"] = "EXTREME_OVERSOLD"

    elif rsi <= RSI_OVERSOLD:
        result["score"] = 75
        result["bias"] = "BULLISH"
        result["state"] = "OVERSOLD"

    elif rsi >= 80:
        result["score"] = 10
        result["bias"] = "BEARISH"
        result["state"] = "EXTREME_OVERBOUGHT"

    elif rsi >= RSI_OVERBOUGHT:
        result["score"] = 25
        result["bias"] = "BEARISH"
        result["state"] = "OVERBOUGHT"

    return result


# ============================================================
# RSI MOMENTUM
# ============================================================

def analyze_rsi_momentum(df):
    """
    RSI yükseliyor mu düşüyor mu?
    """

    result = {
        "score": 50,
        "direction": "FLAT",
        "delta": 0
    }

    if not validate_dataframe(df):
        return result

    rsi = hesapla_rsi(df["Close"])

    if len(rsi) < 6:
        return result

    delta = safe_float(
        rsi.iloc[-1] - rsi.iloc[-6]
    )

    result["delta"] = round(delta, 2)

    if delta > 5:
        result["score"] = 80
        result["direction"] = "UP"

    elif delta > 2:
        result["score"] = 65
        result["direction"] = "UP"

    elif delta < -5:
        result["score"] = 20
        result["direction"] = "DOWN"

    elif delta < -2:
        result["score"] = 35
        result["direction"] = "DOWN"

    return result


# ============================================================
# MACD ANALYSIS
# ============================================================

def analyze_macd(df):
    """
    MACD ana analizi
    """

    result = {
        "score": 50,
        "bias": "NEUTRAL",
        "cross": False,
        "histogram": 0
    }

    if not validate_dataframe(df):
        return result

    macd = hesapla_macd(df)

    if macd is None or len(macd) < 2:
        return result

    macd_line = safe_float(
        macd["MACD"].iloc[-1]
    )

    signal_line = safe_float(
        macd["Signal"].iloc[-1]
    )

    histogram = safe_float(
        macd["Histogram"].iloc[-1]
    )

    result["histogram"] = round(
        histogram,
        4
    )

    if macd_line > signal_line:
        result["score"] = 80
        result["bias"] = "BULLISH"

    elif macd_line < signal_line:
        result["score"] = 20
        result["bias"] = "BEARISH"

    prev_macd = safe_float(
        macd["MACD"].iloc[-2]
    )

    prev_signal = safe_float(
        macd["Signal"].iloc[-2]
    )

    if (
        prev_macd < prev_signal
        and
        macd_line > signal_line
    ):
        result["cross"] = True

    if (
        prev_macd > prev_signal
        and
        macd_line < signal_line
    ):
        result["cross"] = True

    return result


# ============================================================
# ATR ANALYSIS
# ============================================================

def analyze_atr(df):
    """
    Volatilite analizi
    """

    result = {
        "score": 50,
        "atr": 0,
        "atr_percent": 0
    }

    if not validate_dataframe(df):
        return result

    atr = safe_float(
        hesapla_atr(df).iloc[-1]
    )

    price = safe_float(
        df["Close"].iloc[-1]
    )

    if price <= 0:
        return result

    atr_percent = (
        atr / price
    ) * 100

    result["atr"] = round(atr, 2)
    result["atr_percent"] = round(atr_percent, 2)

    if atr_percent > 2.0:
        result["score"] = 85

    elif atr_percent > 1.2:
        result["score"] = 70

    elif atr_percent < 0.5:
        result["score"] = 30

    return result


# ============================================================
# MOMENTUM MASTER
# ============================================================

def analyze_momentum(df):
    """
    RSI + RSI Momentum + MACD + ATR
    """

    rsi = analyze_rsi(df)

    rsi_momentum = analyze_rsi_momentum(df)

    macd = analyze_macd(df)

    atr = analyze_atr(df)

    score = weighted_score(
        [
            rsi["score"],
            rsi_momentum["score"],
            macd["score"],
            atr["score"]
        ],
        [
            0.30,
            0.20,
            0.35,
            0.15
        ]
    )

    return {
        "signal": score_to_signal(score),
        "bias": score_to_bias(score),
        "score": score,
        "confidence": calculate_confidence(
            [
                rsi["score"],
                rsi_momentum["score"],
                macd["score"],
                atr["score"]
            ]
        ),
        "rsi": rsi,
        "rsi_momentum": rsi_momentum,
        "macd": macd,
        "atr": atr
    }


# ============================================================
# INDICATOR ENGINE
# ============================================================

def indicator_engine(market_data):
    """
    QQQ PRO v6 Institutional Indicator Engine

    Sadece indikatörleri analiz eder.

    Decision Engine için standart çıktı üretir.
    """

    result = default_result()

    if not isinstance(market_data, dict):
        result["warnings"].append(
            "market_data dictionary değil."
        )
        return result

    df = market_data.get("df_5m")

    if not validate_dataframe(df):
        result["warnings"].append(
            "5m veri bulunamadı."
        )
        return result

    # ========================================================
    # ALT ANALİZLER
    # ========================================================

    ema_alignment = analyze_ema_alignment(df)

    ema_slope = analyze_ema_slope(df)

    ema_separation = analyze_ema_separation(df)

    vwap_position = analyze_vwap_position(df)

    vwap_distance = analyze_vwap_distance(df)

    momentum = analyze_momentum(df)

    # ========================================================
    # MASTER SCORE
    # ========================================================

    scores = [
        ema_alignment["score"],
        ema_slope["score"],
        ema_separation["score"],
        vwap_position["score"],
        vwap_distance["score"],
        momentum["score"]
    ]

    weights = [
        0.25,
        0.15,
        0.10,
        0.20,
        0.10,
        0.20
    ]

    final_score = weighted_score(
        scores,
        weights
    )

    confidence = calculate_confidence(
        scores
    )

    # ========================================================
    # FINAL SIGNAL
    # ========================================================

    result["signal"] = score_to_signal(
        final_score
    )

    result["score"] = normalize_score(
        final_score
    )

    result["confidence"] = confidence

    result["bias"] = score_to_bias(
        final_score
    )

    result["trend_score"] = weighted_score(
        [
            ema_alignment["score"],
            ema_slope["score"],
            ema_separation["score"],
            vwap_position["score"]
        ],
        [
            0.35,
            0.25,
            0.15,
            0.25
        ]
    )

    result["momentum_score"] = momentum["score"]

    result["volatility_score"] = momentum["atr"]["score"]

    # ========================================================
    # REASONS
    # ========================================================

    if ema_alignment["reason"]:
        result["reasons"].append(
            ema_alignment["reason"]
        )

    if ema_slope["reason"]:
        result["reasons"].append(
            ema_slope["reason"]
        )

    if vwap_position["reason"]:
        result["reasons"].append(
            vwap_position["reason"]
        )

    # ========================================================
    # DETAILS
    # ========================================================

    result["details"] = {
        "ema_alignment": ema_alignment,
        "ema_slope": ema_slope,
        "ema_separation": ema_separation,
        "vwap_position": vwap_position,
        "vwap_distance": vwap_distance,
        "momentum": momentum
    }

    return result


# ============================================================
# DEBUG
# ============================================================

def debug_indicator_engine(result):
    if not isinstance(result, dict):
        return {}

    return {
        "signal": result.get("signal"),
        "score": result.get("score"),
        "confidence": result.get("confidence"),
        "bias": result.get("bias"),
        "trend_score": result.get("trend_score"),
        "momentum_score": result.get("momentum_score"),
        "volatility_score": result.get("volatility_score")
    }


# ============================================================
# HEALTH
# ============================================================

def indicator_engine_health():
    return {
        "engine": "QQQ PRO v6 Indicator Engine",
        "version": "6.0",
        "status": "READY",
        "functions": [
            "analyze_ema_alignment",
            "analyze_ema_slope",
            "analyze_ema_separation",
            "analyze_vwap_position",
            "analyze_vwap_distance",
            "analyze_rsi",
            "analyze_rsi_momentum",
            "analyze_macd",
            "analyze_atr",
            "analyze_momentum",
            "indicator_engine"
        ]
    }