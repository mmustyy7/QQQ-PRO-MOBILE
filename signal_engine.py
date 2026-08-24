# ============================================================
#
# QQQ PRO
# signal_engine.py
#
# VERSION: 5.5
#
# DIRECTIONAL SIGNAL ENGINE
#
# GÖREV:
# - Trend Engine verisini almak
# - 1m / 5m / 15m göstergelerini analiz etmek
# - RSI / Volume / Momentum / EMA / VWAP değerlendirmek
# - Trend + Indicator birleşik skor üretmek
# - CALL / PUT / BEKLE yönünü belirlemek
# - Güven seviyesini hesaplamak
# - Decision Engine 5.4'e standart veri göndermek
#
# BU DOSYANIN GÖREVİ DEĞİL:
# - Nihai pozisyon açmak
# - Opsiyon seçmek
# - Destek / direnç kırılımı kararı vermek
# - Pozisyon kapatmak
#
# VERİ AKIŞI:
#
# market_data.py
#       ↓
# trend_engine.py
#       ↓
# signal_engine.py
#       ↓
# decision_engine.py
#       ↓
# app.py
#
# ============================================================

import numpy as np
import pandas as pd


# ============================================================
# ENGINE INFORMATION
# ============================================================

ENGINE_NAME = "QQQ PRO Signal Engine"
ENGINE_VERSION = "5.5"


# ============================================================
# SETTINGS
# ============================================================

RSI_PERIOD = 14

SIGNAL_CALL_THRESHOLD = 60
SIGNAL_PUT_THRESHOLD = 40

STRONG_CALL_THRESHOLD = 75
STRONG_PUT_THRESHOLD = 25

MIN_SIGNAL_CONFIDENCE = 60

WEIGHT_1M = 1
WEIGHT_5M = 2
WEIGHT_15M = 2

TREND_WEIGHT = 0.55
INDICATOR_WEIGHT = 0.45

MIN_DIRECTIONAL_ADVANTAGE = 2

MOMENTUM_THRESHOLD = 0.05

VOLUME_CONFIRMATION_RATIO = 1.20


# ============================================================
# SCORE LIMITS
# ============================================================

MIN_SCORE = 0.0
MAX_SCORE = 100.0

INDICATOR_MIN_SCORE = 20.0
INDICATOR_MAX_SCORE = 80.0

MAX_CONFIDENCE = 95


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

        result = float(value)

        if not np.isfinite(result):
            return default

        return result

    except Exception:

        return default


# ============================================================
# SAFE STRING
# ============================================================

def safe_string(value, default=""):

    try:

        if value is None:
            return default

        return str(value).strip()

    except Exception:

        return default


# ============================================================
# SAFE BOOL
# ============================================================

def safe_bool(value, default=False):

    try:

        if value is None:
            return default

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return bool(value)

        text = safe_string(value).upper()

        if text in (
            "TRUE",
            "1",
            "YES",
            "EVET",
            "DOĞRU",
            "DOGRU",
        ):
            return True

        if text in (
            "FALSE",
            "0",
            "NO",
            "HAYIR",
            "YANLIŞ",
            "YANLIS",
        ):
            return False

        return default

    except Exception:

        return default


# ============================================================
# CLAMP
# ============================================================

def clamp(value, low, high):

    value = safe_float(
        value,
        low
    )

    return max(
        low,
        min(
            value,
            high
        )
    )


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

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required_columns:

        if column not in df.columns:
            return False

    try:

        close = pd.to_numeric(
            df["Close"],
            errors="coerce"
        )

        if close.dropna().empty:
            return False

        if safe_float(
            close.dropna().iloc[-1],
            0.0
        ) <= 0:

            return False

    except Exception:

        return False

    return True


# ============================================================
# EMPTY TIMEFRAME
# ============================================================

def empty_timeframe():

    return {

        "rsi": 50.0,

        "volume_ratio": 1.0,

        "momentum": 0.0,

        "price": 0.0,

        "ema9": 0.0,

        "ema21": 0.0,

        "vwap": 0.0,

        "bullish_points": 0,

        "bearish_points": 0,

        "net_points": 0,

        "direction": "NEUTRAL",

    }


# ============================================================
# EMPTY SIGNAL
#
# Decision Engine 5.4 CONTRACT
# ============================================================

def empty_signal():

    return {

        "engine": ENGINE_NAME,

        "version": ENGINE_VERSION,

        # ------------------------------
        # MAIN DECISION FIELDS
        # ------------------------------

        "signal": "BEKLE",

        "final_signal": "BEKLE",

        "signal_strength": "KARARSIZ",

        "score": 50,

        "final_score": 50,

        "trend_score": 50,

        "indicator_score": 50,

        "confidence": 0,

        "trend_confidence": 0,

        # ------------------------------
        # DIRECTION DATA
        # ------------------------------

        "bullish_points": 0,

        "bearish_points": 0,

        "net_points": 0,

        "call_strength": 0,

        "put_strength": 0,

        "trend_bias": "NEUTRAL",

        "trend_confirmation": False,

        "timeframe_alignment": "NONE",

        # ------------------------------
        # MARKET DATA
        # ------------------------------

        "price": 0.0,

        "rsi_1m": 50.0,

        "rsi_5m": 50.0,

        "rsi_15m": 50.0,

        "volume_ratio_1m": 1.0,

        "volume_ratio_5m": 1.0,

        "volume_ratio_15m": 1.0,

        "momentum_1m": 0.0,

        "momentum_5m": 0.0,

        "momentum_15m": 0.0,

        # ------------------------------
        # STRUCTURE
        # ------------------------------

        "status": "READY",

        "reason": "Yeterli veri bulunamadı.",

        "timeframes": {},

        "debug": {},

    }


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    df,
    period=RSI_PERIOD
):

    if not validate_dataframe(df):

        return 50.0

    try:

        close = pd.to_numeric(
            df["Close"],
            errors="coerce"
        ).dropna()

        if len(close) < period + 1:

            return 50.0

        delta = close.diff()

        gain = delta.clip(
            lower=0
        )

        loss = -delta.clip(
            upper=0
        )

        avg_gain = gain.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        avg_loss = loss.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period
        ).mean()

        latest_loss = safe_float(
            avg_loss.iloc[-1],
            0.0
        )

        latest_gain = safe_float(
            avg_gain.iloc[-1],
            0.0
        )

        if latest_loss == 0:

            if latest_gain > 0:
                return 100.0

            return 50.0

        rs = (
            avg_gain /
            avg_loss
        )

        rsi = (
            100 -
            (
                100 /
                (1 + rs)
            )
        )

        result = rsi.dropna()

        if result.empty:
            return 50.0

        value = safe_float(
            result.iloc[-1],
            50.0
        )

        return clamp(
            value,
            0.0,
            100.0
        )

    except Exception:

        return 50.0


# ============================================================
# VOLUME RATIO
# ============================================================

def calculate_volume_ratio(df):

    if not validate_dataframe(df):

        return 1.0

    try:

        volume = pd.to_numeric(
            df["Volume"],
            errors="coerce"
        ).dropna()

        if len(volume) < 21:

            return 1.0

        current_volume = safe_float(
            volume.iloc[-1],
            0.0
        )

        average_volume = safe_float(
            volume.iloc[-21:-1].mean(),
            0.0
        )

        if average_volume <= 0:

            return 1.0

        ratio = (
            current_volume /
            average_volume
        )

        return clamp(
            ratio,
            0.0,
            10.0
        )

    except Exception:

        return 1.0


# ============================================================
# PRICE MOMENTUM
# ============================================================

def calculate_price_momentum(df):

    if not validate_dataframe(df):

        return 0.0

    try:

        close = pd.to_numeric(
            df["Close"],
            errors="coerce"
        ).dropna()

        if len(close) < 6:

            return 0.0

        current = safe_float(
            close.iloc[-1],
            0.0
        )

        previous = safe_float(
            close.iloc[-6],
            0.0
        )

        if previous <= 0:

            return 0.0

        momentum = (
            (
                current -
                previous
            )
            /
            previous
        ) * 100

        return safe_float(
            momentum,
            0.0
        )

    except Exception:

        return 0.0


# ============================================================
# TREND VALUE EXTRACTION
# ============================================================

def extract_trend_value(
    trend_data,
    key,
    default=0.0
):

    if not isinstance(
        trend_data,
        dict
    ):

        return default

    return safe_float(
        trend_data.get(
            key,
            default
        ),
        default
    )


# ============================================================
# SINGLE TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    df,
    trend_data=None
):

    if not validate_dataframe(df):

        return empty_timeframe()

    try:

        close = safe_float(
            df["Close"].iloc[-1],
            0.0
        )

        rsi = calculate_rsi(df)

        volume_ratio = calculate_volume_ratio(df)

        momentum = calculate_price_momentum(df)

        ema9 = 0.0
        ema21 = 0.0
        vwap = 0.0

        if isinstance(
            trend_data,
            dict
        ):

            ema9 = extract_trend_value(
                trend_data,
                "ema9",
                0.0
            )

            ema21 = extract_trend_value(
                trend_data,
                "ema21",
                0.0
            )

            vwap = extract_trend_value(
                trend_data,
                "vwap",
                0.0
            )

        bullish_points = 0
        bearish_points = 0

        # ----------------------------------------------------
        # EMA 9 / EMA 21
        # ----------------------------------------------------

        if (
            ema9 > 0
            and
            ema21 > 0
        ):

            if ema9 > ema21:

                bullish_points += 2

            elif ema9 < ema21:

                bearish_points += 2

        # ----------------------------------------------------
        # PRICE / VWAP
        # ----------------------------------------------------

        if vwap > 0:

            if close > vwap:

                bullish_points += 2

            elif close < vwap:

                bearish_points += 2

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        if rsi >= 55:

            bullish_points += 2

        elif rsi <= 45:

            bearish_points += 2

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        if momentum > MOMENTUM_THRESHOLD:

            bullish_points += 1

        elif momentum < -MOMENTUM_THRESHOLD:

            bearish_points += 1

        # ----------------------------------------------------
        # VOLUME
        #
        # Hacim tek başına yön üretmez.
        # Mevcut yönü teyit eder.
        # ----------------------------------------------------

        volume_confirmed = (
            volume_ratio >=
            VOLUME_CONFIRMATION_RATIO
        )

        if volume_confirmed:

            if bullish_points > bearish_points:

                bullish_points += 2

            elif bearish_points > bullish_points:

                bearish_points += 2

        # ----------------------------------------------------
        # NET
        # ----------------------------------------------------

        net_points = (
            bullish_points -
            bearish_points
        )

        # ----------------------------------------------------
        # DIRECTION
        # ----------------------------------------------------

        if bullish_points > bearish_points:

            direction = "BULLISH"

        elif bearish_points > bullish_points:

            direction = "BEARISH"

        else:

            direction = "NEUTRAL"

        return {

            "rsi": round(
                rsi,
                2
            ),

            "volume_ratio": round(
                volume_ratio,
                2
            ),

            "momentum": round(
                momentum,
                4
            ),

            "price": round(
                close,
                4
            ),

            "ema9": round(
                ema9,
                4
            ),

            "ema21": round(
                ema21,
                4
            ),

            "vwap": round(
                vwap,
                4
            ),

            "bullish_points": int(
                bullish_points
            ),

            "bearish_points": int(
                bearish_points
            ),

            "net_points": int(
                net_points
            ),

            "direction": direction,

        }

    except Exception:

        return empty_timeframe()


# ============================================================
# INDICATOR SCORE
# ============================================================

def calculate_indicator_score(
    signal_1m,
    signal_5m,
    signal_15m
):

    tf1_bull = int(
        signal_1m.get(
            "bullish_points",
            0
        )
    )

    tf1_bear = int(
        signal_1m.get(
            "bearish_points",
            0
        )
    )

    tf5_bull = int(
        signal_5m.get(
            "bullish_points",
            0
        )
    )

    tf5_bear = int(
        signal_5m.get(
            "bearish_points",
            0
        )
    )

    tf15_bull = int(
        signal_15m.get(
            "bullish_points",
            0
        )
    )

    tf15_bear = int(
        signal_15m.get(
            "bearish_points",
            0
        )
    )

    bullish_total = (
        tf1_bull * WEIGHT_1M
        +
        tf5_bull * WEIGHT_5M
        +
        tf15_bull * WEIGHT_15M
    )

    bearish_total = (
        tf1_bear * WEIGHT_1M
        +
        tf5_bear * WEIGHT_5M
        +
        tf15_bear * WEIGHT_15M
    )

    total = (
        bullish_total +
        bearish_total
    )

    if total <= 0:

        return (
            50.0,
            bullish_total,
            bearish_total
        )

    score = (
        bullish_total /
        total
    ) * 100

    score = clamp(
        score,
        INDICATOR_MIN_SCORE,
        INDICATOR_MAX_SCORE
    )

    return (
        score,
        bullish_total,
        bearish_total
    )


# ============================================================
# TREND BIAS NORMALIZATION
# ============================================================

def normalize_trend_bias(
    trend_data
):

    if not isinstance(
        trend_data,
        dict
    ):

        return "NEUTRAL"

    raw = (
        trend_data.get(
            "trend_bias"
        )
        or
        trend_data.get(
            "bias"
        )
        or
        trend_data.get(
            "trend"
        )
        or
        trend_data.get(
            "direction"
        )
        or
        ""
    )

    raw = safe_string(
        raw
    ).upper()

    bullish_words = (
        "BULL",
        "BULLISH",
        "YUKSEL",
        "YÜKSEL",
        "UPTREND",
        "UP",
        "LONG",
    )

    bearish_words = (
        "BEAR",
        "BEARISH",
        "DUS",
        "DÜS",
        "DÜŞ",
        "DOWNTREND",
        "DOWN",
        "SHORT",
    )

    if any(
        word in raw
        for word in bullish_words
    ):

        return "BULLISH"

    if any(
        word in raw
        for word in bearish_words
    ):

        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# TIMEFRAME ALIGNMENT
# ============================================================

def calculate_timeframe_alignment(
    signal_1m,
    signal_5m,
    signal_15m
):

    directions = []

    for signal_data in (
        signal_1m,
        signal_5m,
        signal_15m
    ):

        if not isinstance(
            signal_data,
            dict
        ):

            directions.append(
                "NEUTRAL"
            )

            continue

        direction = safe_string(
            signal_data.get(
                "direction",
                ""
            )
        ).upper()

        if direction in (
            "BULLISH",
            "BEARISH"
        ):

            directions.append(
                direction
            )

        else:

            bull = int(
                signal_data.get(
                    "bullish_points",
                    0
                )
            )

            bear = int(
                signal_data.get(
                    "bearish_points",
                    0
                )
            )

            if bull > bear:

                directions.append(
                    "BULLISH"
                )

            elif bear > bull:

                directions.append(
                    "BEARISH"
                )

            else:

                directions.append(
                    "NEUTRAL"
                )

    if len(directions) != 3:

        return "NONE"

    if all(
        direction == "BULLISH"
        for direction in directions
    ):

        return "BULLISH"

    if all(
        direction == "BEARISH"
        for direction in directions
    ):

        return "BEARISH"

    if (
        directions[1] == "BULLISH"
        and
        directions[2] == "BULLISH"
    ):

        return "BULLISH_5M_15M"

    if (
        directions[1] == "BEARISH"
        and
        directions[2] == "BEARISH"
    ):

        return "BEARISH_5M_15M"

    return "MIXED"


# ============================================================
# SIGNAL CONFIDENCE
#
# QQQ PRO v5.5
#
# Confidence artık sadece final_score mesafesine
# bağlı değildir.
#
# AĞIRLIKLAR:
#
# Final Score Strength     : 45 puan
# Trend Confidence         : 25 puan
# Timeframe Alignment      : 20 puan
# Trend Confirmation       : 10 puan
# Indicator Dominance      : 10 puan
#
# Toplam teorik değer 110 olabilir.
# Sonuç MAX_CONFIDENCE ile 95'e sınırlandırılır.
#
# Amaç:
# Güçlü ve uyumlu CALL / PUT sinyalinin
# gereksiz yere BEKLE'ye düşmesini önlemek.
# ============================================================

def calculate_signal_confidence(
    final_score,
    trend_confidence,
    trend_confirmation,
    timeframe_alignment,
    indicator_bull,
    indicator_bear
):

    try:

        final_score = clamp(
            final_score,
            0,
            100
        )

        trend_confidence = clamp(
            trend_confidence,
            0,
            100
        )

        # ====================================================
        # 1. FINAL SCORE STRENGTH
        #
        # 50 = yönsüz
        # 100 = maksimum CALL
        # 0 = maksimum PUT
        #
        # 45 PUAN
        # ====================================================

        score_distance = abs(
            final_score - 50
        )

        score_component = (
            score_distance /
            50.0
        ) * 45.0

        # ====================================================
        # 2. TREND CONFIDENCE
        #
        # 25 PUAN
        # ====================================================

        trend_component = (
            trend_confidence /
            100.0
        ) * 25.0

        # ====================================================
        # 3. TIMEFRAME ALIGNMENT
        #
        # 20 PUAN
        # ====================================================

        alignment_component = 0.0

        if timeframe_alignment in (
            "BULLISH",
            "BEARISH"
        ):

            # 1m + 5m + 15m aynı yönde
            alignment_component = 20.0

        elif timeframe_alignment in (
            "BULLISH_5M_15M",
            "BEARISH_5M_15M"
        ):

            # Ana 5m + 15m aynı yönde
            alignment_component = 15.0

        elif timeframe_alignment == "MIXED":

            alignment_component = 5.0

        # ====================================================
        # 4. TREND CONFIRMATION
        #
        # 10 PUAN
        # ====================================================

        confirmation_component = 0.0

        if trend_confirmation:

            confirmation_component = 10.0

        # ====================================================
        # 5. INDICATOR DOMINANCE
        #
        # 10 PUAN
        # ====================================================

        indicator_bull = max(
            0.0,
            safe_float(
                indicator_bull,
                0.0
            )
        )

        indicator_bear = max(
            0.0,
            safe_float(
                indicator_bear,
                0.0
            )
        )

        total_indicator_points = (
            indicator_bull +
            indicator_bear
        )

        dominance_component = 0.0

        if total_indicator_points > 0:

            dominance = (
                abs(
                    indicator_bull -
                    indicator_bear
                )
                /
                total_indicator_points
            )

            dominance_component = (
                dominance * 10.0
            )

        # ====================================================
        # FINAL CONFIDENCE
        # ====================================================

        confidence = (
            score_component
            +
            trend_component
            +
            alignment_component
            +
            confirmation_component
            +
            dominance_component
        )

        return int(
            clamp(
                round(confidence),
                0,
                MAX_CONFIDENCE
            )
        )

    except Exception:

        return 0


# ============================================================
# SIGNAL ENGINE
# ============================================================

def signal_engine(
    market_data,
    trend_data
):

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    if not isinstance(
        market_data,
        dict
    ):

        result = empty_signal()

        result["status"] = "ERROR"

        result["reason"] = (
            "market_data sözlük formatında değil."
        )

        return result

    if not isinstance(
        trend_data,
        dict
    ):

        result = empty_signal()

        result["status"] = "ERROR"

        result["reason"] = (
            "trend_data sözlük formatında değil."
        )

        return result

    try:

        # ====================================================
        # MARKET DATA
        # ====================================================

        df_1m = market_data.get(
            "df_1m"
        )

        df_5m = market_data.get(
            "df_5m"
        )

        df_15m = market_data.get(
            "df_15m"
        )

        # ====================================================
        # TREND TIMEFRAMES
        # ====================================================

        trend_timeframes = trend_data.get(
            "timeframes",
            {}
        )

        if not isinstance(
            trend_timeframes,
            dict
        ):

            trend_timeframes = {}

        tf1 = trend_timeframes.get(
            "1m",
            {}
        )

        tf5 = trend_timeframes.get(
            "5m",
            {}
        )

        tf15 = trend_timeframes.get(
            "15m",
            {}
        )

        # ====================================================
        # TIMEFRAME ANALYSIS
        # ====================================================

        signal_1m = analyze_timeframe(
            df_1m,
            tf1
        )

        signal_5m = analyze_timeframe(
            df_5m,
            tf5
        )

        signal_15m = analyze_timeframe(
            df_15m,
            tf15
        )

        # ====================================================
        # TREND
        # ====================================================

        trend_score = safe_float(
            trend_data.get(
                "trend_score",
                50
            ),
            50
        )

        final_trend_score = safe_float(
            trend_data.get(
                "final_score",
                trend_score
            ),
            trend_score
        )

        trend_score = clamp(
            trend_score,
            0,
            100
        )

        final_trend_score = clamp(
            final_trend_score,
            0,
            100
        )

        trend_bias = normalize_trend_bias(
            trend_data
        )

        trend_confirmation = safe_bool(
            trend_data.get(
                "trend_confirmation",
                False
            ),
            False
        )

        trend_confidence = clamp(
            trend_data.get(
                "confidence",
                0
            ),
            0,
            100
        )

        # ====================================================
        # INDICATOR SCORE
        # ====================================================

        (
            indicator_score,
            indicator_bull,
            indicator_bear
        ) = calculate_indicator_score(
            signal_1m,
            signal_5m,
            signal_15m
        )

        # ====================================================
        # FINAL SCORE
        #
        # Decision Engine 5.4 bunu okuyacak.
        # ====================================================

        signal_score = (
            final_trend_score *
            TREND_WEIGHT
            +
            indicator_score *
            INDICATOR_WEIGHT
        )

        final_score = int(
            round(
                clamp(
                    signal_score,
                    0,
                    100
                )
            )
        )

        # ====================================================
        # TIMEFRAME ALIGNMENT
        # ====================================================

        timeframe_alignment = (
            calculate_timeframe_alignment(
                signal_1m,
                signal_5m,
                signal_15m
            )
        )

        # ====================================================
        # CONFIDENCE
        # ====================================================

        signal_confidence = (
            calculate_signal_confidence(
                final_score,
                trend_confidence,
                trend_confirmation,
                timeframe_alignment,
                indicator_bull,
                indicator_bear
            )
        )

        # ====================================================
        # INDICATOR ADVANTAGE
        # ====================================================

        indicator_advantage = (
            indicator_bull -
            indicator_bear
        )

        # ====================================================
        # MAIN DIRECTION
        # ====================================================

        if final_score >= SIGNAL_CALL_THRESHOLD:

            signal = "CALL"

        elif final_score <= SIGNAL_PUT_THRESHOLD:

            signal = "PUT"

        else:

            signal = "BEKLE"

        raw_signal = signal

        # ====================================================
        # CONFLICT PROTECTION
        # ====================================================

        conflict_detected = False

        if (
            trend_bias == "BULLISH"
            and
            indicator_advantage
            <= -MIN_DIRECTIONAL_ADVANTAGE
        ):

            signal = "BEKLE"

            conflict_detected = True

        elif (
            trend_bias == "BEARISH"
            and
            indicator_advantage
            >= MIN_DIRECTIONAL_ADVANTAGE
        ):

            signal = "BEKLE"

            conflict_detected = True

        # ====================================================
        # TREND DIRECTION PROTECTION
        # ====================================================

        trend_direction_block = False

        if (
            signal == "CALL"
            and
            trend_bias == "BEARISH"
        ):

            signal = "BEKLE"

            trend_direction_block = True

        elif (
            signal == "PUT"
            and
            trend_bias == "BULLISH"
        ):

            signal = "BEKLE"

            trend_direction_block = True

        # ====================================================
        # LOW CONFIDENCE PROTECTION
        # ====================================================

        low_confidence_block = False

        if (
            signal in (
                "CALL",
                "PUT"
            )
            and
            signal_confidence
            < MIN_SIGNAL_CONFIDENCE
        ):

            signal = "BEKLE"

            low_confidence_block = True

        # ====================================================
        # SIGNAL STRENGTH
        # ====================================================

        if signal == "CALL":

            if final_score >= STRONG_CALL_THRESHOLD:

                signal_strength = "GÜÇLÜ CALL"

            else:

                signal_strength = "CALL"

        elif signal == "PUT":

            if final_score <= STRONG_PUT_THRESHOLD:

                signal_strength = "GÜÇLÜ PUT"

            else:

                signal_strength = "PUT"

        else:

            signal_strength = "KARARSIZ"

        # ====================================================
        # CALL / PUT STRENGTH
        # ====================================================

        call_strength = int(
            round(
                clamp(
                    indicator_score,
                    0,
                    100
                )
            )
        )

        put_strength = int(
            round(
                clamp(
                    100 - indicator_score,
                    0,
                    100
                )
            )
        )

        # ====================================================
        # PRICE
        # ====================================================

        price = safe_float(
            market_data.get(
                "price",
                signal_5m.get(
                    "price",
                    signal_1m.get(
                        "price",
                        signal_15m.get(
                            "price",
                            0.0
                        )
                    )
                )
            ),
            0.0
        )

        # ====================================================
        # REASON
        # ====================================================

        if conflict_detected:

            reason = (
                "Trend ile göstergeler arasında "
                "yön çatışması var."
            )

        elif trend_direction_block:

            reason = (
                "Signal yönü ana trend ile ters "
                "olduğu için engellendi."
            )

        elif low_confidence_block:

            reason = (
                "Yön skoru oluştu ancak güven seviyesi "
                "0DTE işlem için yetersiz."
            )

        elif signal == "CALL":

            reason = (
                "Bullish trend ve göstergeler "
                "CALL yönünde uyumlu."
            )

        elif signal == "PUT":

            reason = (
                "Bearish trend ve göstergeler "
                "PUT yönünde uyumlu."
            )

        elif (
            trend_bias == "BULLISH"
            and
            indicator_advantage < 0
        ):

            reason = (
                "Trend bullish ancak göstergeler "
                "yeterli bullish teyit vermiyor."
            )

        elif (
            trend_bias == "BEARISH"
            and
            indicator_advantage > 0
        ):

            reason = (
                "Trend bearish ancak göstergeler "
                "yeterli bearish teyit vermiyor."
            )

        else:

            reason = (
                "Net yön teyidi oluşmadı."
            )

        # ====================================================
        # DEBUG
        # ====================================================

        debug = {

            "raw_signal": raw_signal,

            "final_signal": signal,

            "trend_bias": trend_bias,

            "trend_score": int(
                round(
                    trend_score
                )
            ),

            "final_trend_score": int(
                round(
                    final_trend_score
                )
            ),

            "indicator_score": int(
                round(
                    indicator_score
                )
            ),

            "final_score": final_score,

            "trend_confidence": int(
                round(
                    trend_confidence
                )
            ),

            "signal_confidence": signal_confidence,

            "trend_confirmation":
                trend_confirmation,

            "timeframe_alignment":
                timeframe_alignment,

            "indicator_bullish_points":
                int(indicator_bull),

            "indicator_bearish_points":
                int(indicator_bear),

            "indicator_advantage":
                int(indicator_advantage),

            "call_strength":
                call_strength,

            "put_strength":
                put_strength,

            "conflict_detected":
                conflict_detected,

            "trend_direction_block":
                trend_direction_block,

            "low_confidence_block":
                low_confidence_block,

            "timeframes": {

                "1m": signal_1m,

                "5m": signal_5m,

                "15m": signal_15m,

            },

        }

        # ====================================================
        # RESULT
        #
        # DECISION ENGINE 5.4 CONTRACT
        # ====================================================

        return {

            "engine": ENGINE_NAME,

            "version": ENGINE_VERSION,

            "signal": signal,

            "final_signal": signal,

            "signal_strength": signal_strength,

            "score": final_score,

            "final_score": final_score,

            "trend_score": int(
                round(
                    trend_score
                )
            ),

            "indicator_score": int(
                round(
                    indicator_score
                )
            ),

            "confidence": signal_confidence,

            "trend_confidence": int(
                round(
                    trend_confidence
                )
            ),

            "bullish_points":
                int(indicator_bull),

            "bearish_points":
                int(indicator_bear),

            "net_points":
                int(indicator_advantage),

            "call_strength":
                call_strength,

            "put_strength":
                put_strength,

            "trend_bias":
                trend_bias,

            "trend_confirmation":
                trend_confirmation,

            "timeframe_alignment":
                timeframe_alignment,

            "price":
                price,

            "rsi_1m":
                signal_1m["rsi"],

            "rsi_5m":
                signal_5m["rsi"],

            "rsi_15m":
                signal_15m["rsi"],

            "volume_ratio_1m":
                signal_1m["volume_ratio"],

            "volume_ratio_5m":
                signal_5m["volume_ratio"],

            "volume_ratio_15m":
                signal_15m["volume_ratio"],

            "momentum_1m":
                signal_1m["momentum"],

            "momentum_5m":
                signal_5m["momentum"],

            "momentum_15m":
                signal_15m["momentum"],

            "timeframes": {

                "1m": signal_1m,

                "5m": signal_5m,

                "15m": signal_15m,

            },

            "status":
                "READY",

            "reason":
                reason,

            "debug":
                debug,

        }

    except Exception as e:

        result = empty_signal()

        result["status"] = "ERROR"

        result["reason"] = (
            f"Signal engine hatası: {str(e)}"
        )

        result["debug"] = {

            "exception":
                str(e),

            "exception_type":
                type(e).__name__,

        }

        return result


# ============================================================
# HEALTH CHECK
# ============================================================

def signal_engine_health():

    return {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "status":
            "READY",

        "signals": [
            "CALL",
            "PUT",
            "BEKLE",
        ],

        "timeframes": [
            "1m",
            "5m",
            "15m",
        ],

        "decision_engine_contract": {

            "signal": True,

            "score": True,

            "final_score": True,

            "confidence": True,

            "trend_bias": True,

            "trend_score": True,

            "indicator_score": True,

            "timeframe_alignment": True,

        },

    }


# ============================================================
# TEST
# ============================================================

def test_signal_engine(
    market_data,
    trend_data
):

    try:

        result = signal_engine(
            market_data,
            trend_data
        )

        return {

            "status": "OK",

            "result": result,

        }

    except Exception as e:

        return {

            "status": "ERROR",

            "error": str(e),

        }


# ============================================================
# CONTRACT VALIDATION
# ============================================================

def validate_signal_contract(
    result
):

    required_fields = {

        "signal",

        "final_signal",

        "score",

        "final_score",

        "confidence",

        "trend_score",

        "indicator_score",

        "trend_confidence",

        "trend_bias",

        "trend_confirmation",

        "timeframe_alignment",

        "call_strength",

        "put_strength",

        "bullish_points",

        "bearish_points",

        "net_points",

        "price",

        "timeframes",

        "status",

        "reason",

        "debug",

    }

    if not isinstance(
        result,
        dict
    ):

        return {

            "status": "FAIL",

            "missing": list(
                required_fields
            ),

        }

    missing = sorted(
        required_fields -
        set(result.keys())
    )

    invalid = []

    if result.get("signal") not in (
        "CALL",
        "PUT",
        "BEKLE",
    ):

        invalid.append(
            "signal"
        )

    if result.get("final_signal") not in (
        "CALL",
        "PUT",
        "BEKLE",
    ):

        invalid.append(
            "final_signal"
        )

    for field in (
        "score",
        "final_score",
        "confidence",
        "trend_score",
        "indicator_score",
        "trend_confidence",
        "call_strength",
        "put_strength",
    ):

        value = safe_float(
            result.get(field),
            -1
        )

        if value < 0 or value > 100:

            invalid.append(
                field
            )

    status = (
        "PASS"
        if not missing
        and not invalid
        else "FAIL"
    )

    return {

        "status":
            status,

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "missing":
            missing,

        "invalid":
            invalid,

    }


# ============================================================
# SELF VALIDATION
# ============================================================

def validate_signal_engine():

    empty = empty_signal()

    contract = validate_signal_contract(
        empty
    )

    health = signal_engine_health()

    checks = {

        "ENGINE_NAME":
            ENGINE_NAME ==
            "QQQ PRO Signal Engine",

        "ENGINE_VERSION":
            ENGINE_VERSION ==
            "5.5",

        "SIGNAL_CALL_THRESHOLD":
            SIGNAL_CALL_THRESHOLD == 60,

        "SIGNAL_PUT_THRESHOLD":
            SIGNAL_PUT_THRESHOLD == 40,

        "MIN_SIGNAL_CONFIDENCE":
            MIN_SIGNAL_CONFIDENCE == 60,

        "TIMEFRAME_1M":
            WEIGHT_1M == 1,

        "TIMEFRAME_5M":
            WEIGHT_5M == 2,

        "TIMEFRAME_15M":
            WEIGHT_15M == 2,

        "DECISION_CONTRACT":
            contract["status"] == "PASS",

        "HEALTH_STATUS":
            health["status"] == "READY",

        "SIGNAL_CALL":
            "CALL" in health["signals"],

        "SIGNAL_PUT":
            "PUT" in health["signals"],

        "SIGNAL_WAIT":
            "BEKLE" in health["signals"],

    }

    passed = sum(
        1
        for value in checks.values()
        if value
    )

    total = len(checks)

    return {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "status":
            "PASS"
            if passed == total
            else "FAIL",

        "total_tests":
            total,

        "passed":
            passed,

        "failed":
            total - passed,

        "tests":
            checks,

    }


# ============================================================
# PRINT VALIDATION
# ============================================================

def print_signal_validation():

    report = validate_signal_engine()

    print()
    print("=" * 80)
    print("QQQ PRO SIGNAL ENGINE VALIDATION")
    print("=" * 80)

    print(
        f"ENGINE : {report['engine']}"
    )

    print(
        f"VERSION: {report['version']}"
    )

    print(
        f"STATUS : {report['status']}"
    )

    print(
        f"TOTAL  : {report['total_tests']}"
    )

    print(
        f"PASS   : {report['passed']}"
    )

    print(
        f"FAIL   : {report['failed']}"
    )

    print("-" * 80)

    for name, passed in report["tests"].items():

        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{name:<35} | {status}"
        )

    print("-" * 80)

    print(
        f"SONUÇ: "
        f"{report['passed']}/"
        f"{report['total_tests']} TEST PASS"
    )

    print("=" * 80)

    return report


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    print_signal_validation()


# ============================================================
# END OF signal_engine.py
# ============================================================