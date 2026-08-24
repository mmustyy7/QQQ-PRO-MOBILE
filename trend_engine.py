# ============================================================
# QQQ PRO
# trend_engine.py
#
# MULTI TIMEFRAME TREND ENGINE
# FINAL ARCHITECTURE - 5.4 COMPATIBLE
#
# GÖREV:
#   1m / 5m / 15m trend analizi
#   EMA 9 / 21 / 50 / 200
#   VWAP
#   ATR
#   Multi-Timeframe alignment
#   Trend score
#   Confidence
#   Final score
#
# BU DOSYANIN GÖREVİ DEĞİL:
#   CALL AL
#   PUT AL
#   CALL KAPAT
#   PUT KAPAT
#   Pozisyon yönetimi
#   Opsiyon seçimi
#   S/R nihai karar
#
# VERİ AKIŞI:
#
#   market_data.py
#        ↓
#   trend_engine.py
#        ↓
#   signal_engine.py
#        ↓
#   decision_engine.py
#        ↓
#   app.py
#
# ============================================================

import numpy as np
import pandas as pd


# ============================================================
# ENGINE INFORMATION
# ============================================================

ENGINE_NAME = "QQQ PRO Trend Engine"
ENGINE_VERSION = "5.4"


# ============================================================
# INDICATOR CONSTANTS
# ============================================================

EMA_FAST = 9
EMA_MID = 21
EMA_SLOW = 50
EMA_LONG = 200

ATR_PERIOD = 14


# ============================================================
# TIMEFRAME WEIGHTS
#
# 1m = giriş hassasiyeti
# 5m = ana intraday yön
# 15m = üst zaman dilimi teyidi
# ============================================================

TIMEFRAME_WEIGHTS = {
    "1m": 0.20,
    "5m": 0.40,
    "15m": 0.40,
}


# ============================================================
# SCORE THRESHOLDS
# ============================================================

BULLISH_THRESHOLD = 60
BEARISH_THRESHOLD = 40

STRONG_BULLISH_THRESHOLD = 75
STRONG_BEARISH_THRESHOLD = 25

VERY_STRONG_BULLISH_THRESHOLD = 90
VERY_STRONG_BEARISH_THRESHOLD = 10


# ============================================================
# CONFIDENCE LIMITS
# ============================================================

MIN_CONFIDENCE = 0
MAX_CONFIDENCE = 98


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value, default=0.0):
    """
    Her türlü güvenli numerik değeri float'a çevirir.

    Series / DataFrame / list / tuple / ndarray destekler.
    """

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
    """
    Güvenli string dönüşümü.
    """

    try:

        if value is None:
            return default

        return str(value).strip()

    except Exception:
        return default


# ============================================================
# EMPTY TIMEFRAME RESULT
# ============================================================

def empty_timeframe_result():
    """
    Veri bulunamadığında standart timeframe çıktısı.
    """

    return {

        "score": 50,
        "signal": "BEKLE",
        "trend": "VERİ YOK",

        "price": 0.0,
        "close": 0.0,
        "open": 0.0,

        "ema9": 0.0,
        "ema21": 0.0,
        "ema50": 0.0,
        "ema200": 0.0,

        "vwap": 0.0,
        "atr": 0.0,

        "bullish": False,
        "bearish": False,

        "ema_alignment": "MIXED",
        "vwap_bias": "NEUTRAL",

        "valid": False,
    }


# ============================================================
# EMPTY ENGINE RESULT
# ============================================================

def empty_engine_result(price=0.0):
    """
    Trend Engine ana çıktısının boş / güvenli hali.
    """

    price = safe_float(price, 0.0)

    return {

        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,

        # ----------------------------------------------------
        # SCORE CONTRACT
        # ----------------------------------------------------

        "score": 50,
        "final_score": 50,
        "trend_score": 50,

        # ----------------------------------------------------
        # SIGNAL CONTRACT
        # ----------------------------------------------------

        "signal": "BEKLE",
        "final_signal": "BEKLE",

        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        "trend_bias": "NEUTRAL",
        "trend": "VERİ YOK",

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        "confidence": 0,

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        "price": price,
        "live_price": price,

        # ----------------------------------------------------
        # INDICATORS
        # ----------------------------------------------------

        "vwap": 0.0,
        "atr": 0.0,

        # ----------------------------------------------------
        # TIMEFRAMES
        # ----------------------------------------------------

        "timeframes": {},

        # ----------------------------------------------------
        # ALIGNMENT
        # ----------------------------------------------------

        "ema_alignment": "MIXED",
        "timeframe_alignment": "MIXED",

        "entry_alignment": False,
        "trend_confirmation": False,

        # ----------------------------------------------------
        # DATA STATUS
        # ----------------------------------------------------

        "valid": False,
        "valid_timeframes": [],
        "data_quality": 0,
    }


# ============================================================
# DATAFRAME VALIDATOR
# ============================================================

def validate_dataframe(df):
    """
    OHLCV DataFrame geçerlilik kontrolü.
    """

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
            errors="coerce",
        )

        valid_close = close.dropna()

        if valid_close.empty:
            return False

        if safe_float(
            valid_close.iloc[-1],
            0.0,
        ) <= 0:
            return False

    except Exception:
        return False

    return True


# ============================================================
# PREPARE OHLCV
# ============================================================

def prepare_dataframe(df):
    """
    OHLCV kolonlarını numerik hale getirir.
    """

    if not validate_dataframe(df):
        return pd.DataFrame()

    try:

        data = df.copy()

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

        data = data.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        if data.empty:
            return pd.DataFrame()

        return data

    except Exception:
        return pd.DataFrame()


# ============================================================
# EMA CALCULATOR
# ============================================================

def calculate_emas(df):
    """
    EMA 9 / 21 / 50 / 200 hesaplar.
    """

    data = prepare_dataframe(df)

    if data.empty:
        return pd.DataFrame()

    try:

        close = data["Close"]

        data["EMA9"] = close.ewm(
            span=EMA_FAST,
            adjust=False,
            min_periods=EMA_FAST,
        ).mean()

        data["EMA21"] = close.ewm(
            span=EMA_MID,
            adjust=False,
            min_periods=EMA_MID,
        ).mean()

        data["EMA50"] = close.ewm(
            span=EMA_SLOW,
            adjust=False,
            min_periods=EMA_SLOW,
        ).mean()

        data["EMA200"] = close.ewm(
            span=EMA_LONG,
            adjust=False,
            min_periods=EMA_LONG,
        ).mean()

        return data

    except Exception:
        return pd.DataFrame()


# ============================================================
# SESSION VWAP
# ============================================================

def calculate_vwap(df):
    """
    Sadece son işlem gününün VWAP'ını hesaplar.
    """

    data = prepare_dataframe(df)

    if data.empty:
        return 0.0

    try:

        # ----------------------------------------------------
        # SON İŞLEM GÜNÜ
        # ----------------------------------------------------

        if isinstance(
            data.index,
            pd.DatetimeIndex,
        ):

            index = data.index

            if index.tz is not None:

                try:

                    local_index = index.tz_convert(
                        "America/New_York"
                    )

                    session_date = (
                        local_index[-1].date()
                    )

                    mask = (
                        local_index.date
                        == session_date
                    )

                    data = data.loc[mask]

                except Exception:

                    session_date = index[-1].date()

                    data = data[
                        index.date
                        == session_date
                    ]

            else:

                session_date = index[-1].date()

                data = data[
                    index.date
                    == session_date
                ]

        if data.empty:
            return 0.0

        # ----------------------------------------------------
        # NUMERIC
        # ----------------------------------------------------

        high = pd.to_numeric(
            data["High"],
            errors="coerce",
        )

        low = pd.to_numeric(
            data["Low"],
            errors="coerce",
        )

        close = pd.to_numeric(
            data["Close"],
            errors="coerce",
        )

        volume = pd.to_numeric(
            data["Volume"],
            errors="coerce",
        ).fillna(0)

        typical_price = (
            high
            + low
            + close
        ) / 3.0

        valid = (
            typical_price.notna()
            & volume.notna()
        )

        typical_price = typical_price[valid]
        volume = volume[valid]

        if typical_price.empty:
            return 0.0

        total_volume = volume.sum()

        if total_volume <= 0:
            return 0.0

        vwap = (
            (
                typical_price
                * volume
            ).sum()
            / total_volume
        )

        return safe_float(
            vwap,
            0.0,
        )

    except Exception:
        return 0.0


# ============================================================
# ATR CALCULATOR
# ============================================================

def calculate_atr(df):
    """
    ATR(14) hesaplar.
    """

    data = prepare_dataframe(df)

    if data.empty:
        return 0.0

    try:

        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        previous_close = close.shift(1)

        high_low = (
            high - low
        ).abs()

        high_close = (
            high - previous_close
        ).abs()

        low_close = (
            low - previous_close
        ).abs()

        true_range = pd.concat(
            [
                high_low,
                high_close,
                low_close,
            ],
            axis=1,
        ).max(axis=1)

        atr = (
            true_range
            .rolling(
                ATR_PERIOD,
                min_periods=ATR_PERIOD,
            )
            .mean()
        )

        valid_atr = atr.dropna()

        if valid_atr.empty:
            return 0.0

        return safe_float(
            valid_atr.iloc[-1],
            0.0,
        )

    except Exception:
        return 0.0


# ============================================================
# EMA ALIGNMENT
# ============================================================

def get_ema_alignment(
    ema9,
    ema21,
    ema50,
):
    """
    EMA 9 / 21 / 50 ana yön hizalaması.
    """

    ema9 = safe_float(ema9)
    ema21 = safe_float(ema21)
    ema50 = safe_float(ema50)

    if min(
        ema9,
        ema21,
        ema50,
    ) <= 0:

        return "MIXED"

    if (
        ema9 > ema21
        and ema21 > ema50
    ):

        return "BULLISH"

    if (
        ema9 < ema21
        and ema21 < ema50
    ):

        return "BEARISH"

    return "MIXED"


# ============================================================
# TREND LABEL
# ============================================================

def get_trend_label(score):
    """
    Normalize edilmiş trend etiketi.
    """

    score = safe_float(
        score,
        50,
    )

    if score >= 90:
        return "ÇOK GÜÇLÜ YÜKSELİŞ"

    if score >= 75:
        return "GÜÇLÜ YÜKSELİŞ"

    if score >= 60:
        return "YÜKSELİŞ"

    if score <= 10:
        return "ÇOK GÜÇLÜ DÜŞÜŞ"

    if score <= 25:
        return "GÜÇLÜ DÜŞÜŞ"

    if score <= 40:
        return "DÜŞÜŞ"

    return "YATAY / KARARSIZ"


# ============================================================
# BIAS FROM SCORE
# ============================================================

def get_bias(score):
    """
    Score -> trend bias.
    """

    score = safe_float(
        score,
        50,
    )

    if score >= BULLISH_THRESHOLD:
        return "BULLISH"

    if score <= BEARISH_THRESHOLD:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# SIGNAL FROM SCORE
# ============================================================

def get_directional_signal(score):
    """
    Bu işlem emri değildir.

    Sadece yön bilgisidir.
    """

    score = safe_float(
        score,
        50,
    )

    if score >= BULLISH_THRESHOLD:
        return "CALL"

    if score <= BEARISH_THRESHOLD:
        return "PUT"

    return "BEKLE"


# ============================================================
# TIMEFRAME SCORE
# ============================================================

def calculate_timeframe_score(
    close,
    open_price,
    ema9,
    ema21,
    ema50,
    ema200,
    vwap,
):
    """
    Tek timeframe için normalize trend skoru.

    Her komponent 50 merkezlidir.

    Böylece tek bir gösterge skorun tamamını domine edemez.
    """

    close = safe_float(close)
    open_price = safe_float(open_price)

    ema9 = safe_float(ema9)
    ema21 = safe_float(ema21)
    ema50 = safe_float(ema50)
    ema200 = safe_float(ema200)

    vwap = safe_float(vwap)

    components = []

    # --------------------------------------------------------
    # PRICE / EMA9
    # --------------------------------------------------------

    if ema9 > 0:

        if close > ema9:
            components.append(55)

        elif close < ema9:
            components.append(45)

        else:
            components.append(50)

    # --------------------------------------------------------
    # PRICE / EMA21
    # --------------------------------------------------------

    if ema21 > 0:

        if close > ema21:
            components.append(60)

        elif close < ema21:
            components.append(40)

        else:
            components.append(50)

    # --------------------------------------------------------
    # PRICE / EMA50
    # --------------------------------------------------------

    if ema50 > 0:

        if close > ema50:
            components.append(65)

        elif close < ema50:
            components.append(35)

        else:
            components.append(50)

    # --------------------------------------------------------
    # PRICE / EMA200
    # --------------------------------------------------------

    if ema200 > 0:

        if close > ema200:
            components.append(70)

        elif close < ema200:
            components.append(30)

        else:
            components.append(50)

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------

    if vwap > 0:

        if close > vwap:
            components.append(65)

        elif close < vwap:
            components.append(35)

        else:
            components.append(50)

    # --------------------------------------------------------
    # CURRENT CANDLE
    # --------------------------------------------------------

    if close > open_price:
        components.append(55)

    elif close < open_price:
        components.append(45)

    else:
        components.append(50)

    # --------------------------------------------------------
    # EMA ALIGNMENT
    # --------------------------------------------------------

    alignment = get_ema_alignment(
        ema9,
        ema21,
        ema50,
    )

    if alignment == "BULLISH":
        components.append(70)

    elif alignment == "BEARISH":
        components.append(30)

    else:
        components.append(50)

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    if not components:
        return 50

    score = (
        sum(components)
        / len(components)
    )

    return int(
        max(
            0,
            min(
                round(score),
                100,
            ),
        )
    )


# ============================================================
# SINGLE TIMEFRAME ANALYSIS
# ============================================================

def analyze_dataframe(df):
    """
    Tek timeframe analizi.

    1m / 5m / 15m aynı motoru kullanır.
    """

    if not validate_dataframe(df):
        return empty_timeframe_result()

    data = calculate_emas(df)

    if data.empty:
        return empty_timeframe_result()

    try:

        last = data.iloc[-1]

        close = safe_float(
            last["Close"]
        )

        open_price = safe_float(
            last["Open"]
        )

        ema9 = safe_float(
            last["EMA9"]
        )

        ema21 = safe_float(
            last["EMA21"]
        )

        ema50 = safe_float(
            last["EMA50"]
        )

        ema200 = safe_float(
            last["EMA200"]
        )

        vwap = calculate_vwap(
            data
        )

        atr = calculate_atr(
            data
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = calculate_timeframe_score(
            close,
            open_price,
            ema9,
            ema21,
            ema50,
            ema200,
            vwap,
        )

        # ----------------------------------------------------
        # ALIGNMENT
        # ----------------------------------------------------

        ema_alignment = get_ema_alignment(
            ema9,
            ema21,
            ema50,
        )

        # ----------------------------------------------------
        # VWAP
        # ----------------------------------------------------

        if vwap <= 0:

            vwap_bias = "NEUTRAL"

        elif close > vwap:

            vwap_bias = "BULLISH"

        elif close < vwap:

            vwap_bias = "BEARISH"

        else:

            vwap_bias = "NEUTRAL"

        # ----------------------------------------------------
        # BULL / BEAR
        # ----------------------------------------------------

        bullish = (
            score >= BULLISH_THRESHOLD
            and (
                ema_alignment == "BULLISH"
                or vwap_bias == "BULLISH"
            )
        )

        bearish = (
            score <= BEARISH_THRESHOLD
            and (
                ema_alignment == "BEARISH"
                or vwap_bias == "BEARISH"
            )
        )

        # ----------------------------------------------------
        # SIGNAL
        # ----------------------------------------------------

        signal = get_directional_signal(
            score
        )

        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        trend = get_trend_label(
            score
        )

        return {

            "score": score,
            "signal": signal,
            "trend": trend,

            "price": close,
            "close": close,
            "open": open_price,

            "ema9": ema9,
            "ema21": ema21,
            "ema50": ema50,
            "ema200": ema200,

            "vwap": vwap,
            "atr": atr,

            "bullish": bullish,
            "bearish": bearish,

            "ema_alignment": ema_alignment,
            "vwap_bias": vwap_bias,

            "valid": True,
        }

    except Exception:
        return empty_timeframe_result()


# ============================================================
# MULTI TIMEFRAME ALIGNMENT
# ============================================================

def evaluate_timeframe_alignment(
    tf_data,
):
    """
    1m / 5m / 15m yön uyumunu değerlendirir.
    """

    scores = {
        "1m": safe_float(
            tf_data.get("1m", {}).get(
                "score",
                50,
            ),
            50,
        ),

        "5m": safe_float(
            tf_data.get("5m", {}).get(
                "score",
                50,
            ),
            50,
        ),

        "15m": safe_float(
            tf_data.get("15m", {}).get(
                "score",
                50,
            ),
            50,
        ),
    }

    bullish_count = sum(
        score >= BULLISH_THRESHOLD
        for score in scores.values()
    )

    bearish_count = sum(
        score <= BEARISH_THRESHOLD
        for score in scores.values()
    )

    if bullish_count >= 2:
        return "BULLISH"

    if bearish_count >= 2:
        return "BEARISH"

    return "MIXED"


# ============================================================
# MASTER EMA ALIGNMENT
# ============================================================

def evaluate_master_ema_alignment(
    tf_data,
):
    """
    Özellikle 5m + 15m ana trend EMA hizasını kontrol eder.
    """

    tf5 = tf_data.get(
        "5m",
        empty_timeframe_result(),
    )

    tf15 = tf_data.get(
        "15m",
        empty_timeframe_result(),
    )

    ema5 = tf5.get(
        "ema_alignment",
        "MIXED",
    )

    ema15 = tf15.get(
        "ema_alignment",
        "MIXED",
    )

    if (
        ema5 == "BULLISH"
        and ema15 == "BULLISH"
    ):

        return "BULLISH"

    if (
        ema5 == "BEARISH"
        and ema15 == "BEARISH"
    ):

        return "BEARISH"

    return "MIXED"


# ============================================================
# ENTRY ALIGNMENT
# ============================================================

def evaluate_entry_alignment(
    tf_data,
    trend_bias,
):
    """
    1m giriş yönünü 5m ana trend ile karşılaştırır.
    """

    tf1 = tf_data.get(
        "1m",
        empty_timeframe_result(),
    )

    tf5 = tf_data.get(
        "5m",
        empty_timeframe_result(),
    )

    price_1m = safe_float(
        tf1.get("price"),
        0,
    )

    vwap_1m = safe_float(
        tf1.get("vwap"),
        0,
    )

    ema9_5 = safe_float(
        tf5.get("ema9"),
        0,
    )

    ema21_5 = safe_float(
        tf5.get("ema21"),
        0,
    )

    if trend_bias == "BULLISH":

        return (
            ema9_5 > ema21_5
            and (
                vwap_1m <= 0
                or price_1m > vwap_1m
            )
        )

    if trend_bias == "BEARISH":

        return (
            ema9_5 < ema21_5
            and (
                vwap_1m <= 0
                or price_1m < vwap_1m
            )
        )

    return False


# ============================================================
# CONFIDENCE ENGINE
# ============================================================

def calculate_confidence(
    trend_score,
    trend_bias,
    ema_alignment,
    timeframe_alignment,
    entry_alignment,
    trend_confirmation,
):
    """
    CONFIDENCE zinciri.

    Confidence trend score'un kendisi değildir.

    Ölçülen faktörler:

        1. Trend strength
        2. 5m + 15m EMA alignment
        3. Multi timeframe alignment
        4. 1m entry alignment
        5. Final trend confirmation

    Böylece:
        61 score -> otomatik 90 confidence olmaz.
    """

    trend_score = safe_float(
        trend_score,
        50,
    )

    # --------------------------------------------------------
    # BASE CONFIDENCE
    #
    # Trend score merkezden uzaklaştıkça artar.
    # --------------------------------------------------------

    direction_strength = abs(
        trend_score - 50
    )

    confidence = (
        50
        + direction_strength * 0.90
    )

    # --------------------------------------------------------
    # EMA CONFIRMATION
    # --------------------------------------------------------

    if (
        trend_bias == "BULLISH"
        and ema_alignment == "BULLISH"
    ):

        confidence += 8

    elif (
        trend_bias == "BEARISH"
        and ema_alignment == "BEARISH"
    ):

        confidence += 8

    # --------------------------------------------------------
    # MULTI TIMEFRAME CONFIRMATION
    # --------------------------------------------------------

    if (
        trend_bias == "BULLISH"
        and timeframe_alignment == "BULLISH"
    ):

        confidence += 10

    elif (
        trend_bias == "BEARISH"
        and timeframe_alignment == "BEARISH"
    ):

        confidence += 10

    # --------------------------------------------------------
    # ENTRY ALIGNMENT
    # --------------------------------------------------------

    if entry_alignment:
        confidence += 5

    # --------------------------------------------------------
    # FINAL CONFIRMATION
    # --------------------------------------------------------

    if trend_confirmation:
        confidence += 5

    # --------------------------------------------------------
    # NEUTRAL PENALTY
    # --------------------------------------------------------

    if trend_bias == "NEUTRAL":
        confidence = min(
            confidence,
            60,
        )

    # --------------------------------------------------------
    # SCORE BASED CEILINGS
    #
    # Confidence'in trend skorundan kopmasını engeller.
    # --------------------------------------------------------

    if trend_score < 45:

        confidence = min(
            confidence,
            70,
        )

    elif trend_score < 55:

        confidence = min(
            confidence,
            65,
        )

    elif trend_score < 60:

        confidence = min(
            confidence,
            70,
        )

    elif trend_score < 70:

        confidence = min(
            confidence,
            78,
        )

    elif trend_score < 80:

        confidence = min(
            confidence,
            86,
        )

    elif trend_score < 90:

        confidence = min(
            confidence,
            93,
        )

    else:

        confidence = min(
            confidence,
            98,
        )

    confidence = int(
        max(
            MIN_CONFIDENCE,
            min(
                round(confidence),
                MAX_CONFIDENCE,
            ),
        )
    )

    return confidence


# ============================================================
# TREND CONFIRMATION
# ============================================================

def calculate_trend_confirmation(
    trend_bias,
    timeframe_alignment,
    entry_alignment,
    ema_alignment,
):
    """
    Nihai trend teyidi.
    """

    if trend_bias == "BULLISH":

        return (
            timeframe_alignment == "BULLISH"
            and ema_alignment == "BULLISH"
            and entry_alignment
        )

    if trend_bias == "BEARISH":

        return (
            timeframe_alignment == "BEARISH"
            and ema_alignment == "BEARISH"
            and entry_alignment
        )

    return False


# ============================================================
# FINAL SCORE ENGINE
# ============================================================

def calculate_final_score(
    trend_score,
    confidence,
    trend_bias,
    timeframe_alignment,
    ema_alignment,
    entry_alignment,
):
    """
    FINAL SCORE.

    ÖNEMLİ:

    trend_score = yönün ham gücü

    confidence = teyit kalitesi

    final_score = bu iki yapının kontrollü birleşimi.

    Confidence doğrudan yön oluşturmaz.
    """

    trend_score = safe_float(
        trend_score,
        50,
    )

    confidence = safe_float(
        confidence,
        0,
    )

    # --------------------------------------------------------
    # BASE
    # --------------------------------------------------------

    final_score = (
        trend_score * 0.80
        + confidence * 0.20
    )

    # --------------------------------------------------------
    # ALIGNMENT ADJUSTMENT
    #
    # Teyit varsa küçük destek.
    # Çelişki varsa küçük ceza.
    # --------------------------------------------------------

    if (
        trend_bias == "BULLISH"
        and timeframe_alignment == "BULLISH"
        and ema_alignment == "BULLISH"
        and entry_alignment
    ):

        final_score += 2

    elif (
        trend_bias == "BEARISH"
        and timeframe_alignment == "BEARISH"
        and ema_alignment == "BEARISH"
        and entry_alignment
    ):

        final_score -= 2

    # --------------------------------------------------------
    # FINAL RANGE
    # --------------------------------------------------------

    final_score = int(
        max(
            0,
            min(
                round(final_score),
                100,
            ),
        )
    )

    return final_score


# ============================================================
# DATA QUALITY
# ============================================================

def calculate_data_quality(
    tf_data,
):
    """
    Geçerli timeframe yüzdesi.
    """

    total = 3

    valid = sum(
        bool(
            tf_data.get(
                timeframe,
                {},
            ).get(
                "valid",
                False,
            )
        )
        for timeframe in [
            "1m",
            "5m",
            "15m",
        ]
    )

    return int(
        round(
            valid
            / total
            * 100
        )
    )


# ============================================================
# MAIN TREND ENGINE
# ============================================================

def trend_engine(market_data):
    """
    ANA TREND ENGINE.

    Çıktı Decision Engine 5.4 sözleşmesine uyumludur.

    Bu motor işlem emri üretmez.
    """

    # ========================================================
    # INVALID INPUT
    # ========================================================

    if not isinstance(
        market_data,
        dict,
    ):

        return empty_engine_result()

    # ========================================================
    # CURRENT PRICE
    # ========================================================

    price = safe_float(
        market_data.get(
            "price",
            market_data.get(
                "live_price",
                0,
            ),
        ),
        0,
    )

    # ========================================================
    # TIMEFRAME ANALYSIS
    # ========================================================

    tf_data = {

        "1m": analyze_dataframe(
            market_data.get(
                "df_1m"
            )
        ),

        "5m": analyze_dataframe(
            market_data.get(
                "df_5m"
            )
        ),

        "15m": analyze_dataframe(
            market_data.get(
                "df_15m"
            )
        ),
    }

    # ========================================================
    # PRICE FALLBACK
    # ========================================================

    if price <= 0:

        price = safe_float(
            tf_data["1m"].get(
                "price",
                0,
            ),
            0,
        )

    if price <= 0:

        price = safe_float(
            tf_data["5m"].get(
                "price",
                0,
            ),
            0,
        )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    valid_timeframes = [
        timeframe
        for timeframe, result
        in tf_data.items()
        if result.get(
            "valid",
            False,
        )
    ]

    data_quality = calculate_data_quality(
        tf_data
    )

    # ========================================================
    # NO VALID DATA
    # ========================================================

    if not valid_timeframes:

        result = empty_engine_result(
            price
        )

        result["timeframes"] = tf_data
        result["valid_timeframes"] = []
        result["data_quality"] = 0

        return result

    # ========================================================
    # TIMEFRAME SCORES
    # ========================================================

    score1 = safe_float(
        tf_data["1m"].get(
            "score",
            50,
        ),
        50,
    )

    score5 = safe_float(
        tf_data["5m"].get(
            "score",
            50,
        ),
        50,
    )

    score15 = safe_float(
        tf_data["15m"].get(
            "score",
            50,
        ),
        50,
    )

    # ========================================================
    # MULTI TIMEFRAME TREND SCORE
    # ========================================================

    trend_score = (
        score1
        * TIMEFRAME_WEIGHTS["1m"]
        +
        score5
        * TIMEFRAME_WEIGHTS["5m"]
        +
        score15
        * TIMEFRAME_WEIGHTS["15m"]
    )

    trend_score = int(
        max(
            0,
            min(
                round(trend_score),
                100,
            ),
        )
    )

    # ========================================================
    # TREND BIAS
    # ========================================================

    trend_bias = get_bias(
        trend_score
    )

    # ========================================================
    # EMA ALIGNMENT
    # ========================================================

    ema_alignment = (
        evaluate_master_ema_alignment(
            tf_data
        )
    )

    # ========================================================
    # TIMEFRAME ALIGNMENT
    # ========================================================

    timeframe_alignment = (
        evaluate_timeframe_alignment(
            tf_data
        )
    )

    # ========================================================
    # ENTRY ALIGNMENT
    # ========================================================

    entry_alignment = (
        evaluate_entry_alignment(
            tf_data,
            trend_bias,
        )
    )

    # ========================================================
    # TREND CONFIRMATION
    # ========================================================

    trend_confirmation = (
        calculate_trend_confirmation(
            trend_bias,
            timeframe_alignment,
            entry_alignment,
            ema_alignment,
        )
    )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = calculate_confidence(
        trend_score=trend_score,
        trend_bias=trend_bias,
        ema_alignment=ema_alignment,
        timeframe_alignment=timeframe_alignment,
        entry_alignment=entry_alignment,
        trend_confirmation=trend_confirmation,
    )

    # ========================================================
    # FINAL SCORE
    # ========================================================

    final_score = calculate_final_score(
        trend_score=trend_score,
        confidence=confidence,
        trend_bias=trend_bias,
        timeframe_alignment=timeframe_alignment,
        ema_alignment=ema_alignment,
        entry_alignment=entry_alignment,
    )

    # ========================================================
    # FINAL TREND LABEL
    # ========================================================

    trend_label = get_trend_label(
        final_score
    )

    # ========================================================
    # DIRECTIONAL SIGNAL
    #
    # SADECE YÖN.
    #
    # İşlem emri değildir.
    # ========================================================

    directional_signal = (
        get_directional_signal(
            final_score
        )
    )

    # ========================================================
    # MASTER VWAP
    #
    # 5m ana intraday timeframe.
    # ========================================================

    vwap = safe_float(
        tf_data["5m"].get(
            "vwap",
            0,
        ),
        0,
    )

    if vwap <= 0:

        vwap = safe_float(
            tf_data["1m"].get(
                "vwap",
                0,
            ),
            0,
        )

    # ========================================================
    # MASTER ATR
    # ========================================================

    atr = safe_float(
        tf_data["5m"].get(
            "atr",
            0,
        ),
        0,
    )

    if atr <= 0:

        atr = safe_float(
            tf_data["15m"].get(
                "atr",
                0,
            ),
            0,
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {

        # ====================================================
        # ENGINE
        # ====================================================

        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,

        # ====================================================
        # SCORE CONTRACT
        # ====================================================

        "score": final_score,
        "final_score": final_score,
        "trend_score": trend_score,

        # ====================================================
        # SIGNAL CONTRACT
        # ====================================================

        "signal": directional_signal,
        "final_signal": directional_signal,

        # ====================================================
        # TREND
        # ====================================================

        "trend_bias": trend_bias,
        "trend": trend_label,

        # ====================================================
        # CONFIDENCE
        # ====================================================

        "confidence": confidence,

        # ====================================================
        # PRICE
        # ====================================================

        "price": price,
        "live_price": price,

        # ====================================================
        # INDICATORS
        # ====================================================

        "vwap": vwap,
        "atr": atr,

        # ====================================================
        # TIMEFRAMES
        # ====================================================

        "timeframes": tf_data,

        # ====================================================
        # ALIGNMENT
        # ====================================================

        "ema_alignment": ema_alignment,
        "timeframe_alignment": timeframe_alignment,

        "entry_alignment": entry_alignment,
        "trend_confirmation": trend_confirmation,

        # ====================================================
        # DATA STATUS
        # ====================================================

        "valid": True,
        "valid_timeframes": valid_timeframes,
        "data_quality": data_quality,
    }


# ============================================================
# CONTRACT VALIDATION
# ============================================================

def validate_trend_contract(result):
    """
    Trend Engine çıktısının Decision Engine 5.4
    sözleşmesine uyup uymadığını test eder.
    """

    required_fields = {

        "score",
        "final_score",
        "trend_score",

        "signal",
        "final_signal",

        "trend_bias",
        "trend",

        "confidence",

        "price",
        "live_price",

        "vwap",
        "atr",

        "timeframes",

        "ema_alignment",
        "timeframe_alignment",

        "entry_alignment",
        "trend_confirmation",
    }

    missing = [
        field
        for field in required_fields
        if field not in result
    ]

    if missing:
        return False, missing

    return True, []


# ============================================================
# INTERNAL TEST DATA
# ============================================================

def _create_test_dataframe(
    direction="BULLISH",
    rows=250,
):
    """
    Gerçek piyasa verisine dokunmadan
    Trend Engine matematiğini test etmek için
    sentetik OHLCV üretir.
    """

    try:

        index = pd.date_range(
            end=pd.Timestamp.now(),
            periods=rows,
            freq="min",
        )

        if direction == "BULLISH":

            base = np.linspace(
                700,
                730,
                rows,
            )

        elif direction == "BEARISH":

            base = np.linspace(
                730,
                700,
                rows,
            )

        else:

            base = np.full(
                rows,
                715.0,
            )

        noise = np.sin(
            np.linspace(
                0,
                20,
                rows,
            )
        ) * 0.20

        close = (
            base
            + noise
        )

        open_price = (
            close
            - 0.10
            if direction == "BULLISH"
            else close + 0.10
            if direction == "BEARISH"
            else close
        )

        high = (
            np.maximum(
                open_price,
                close,
            )
            + 0.20
        )

        low = (
            np.minimum(
                open_price,
                close,
            )
            - 0.20
        )

        volume = np.full(
            rows,
            100000,
            dtype=float,
        )

        return pd.DataFrame(
            {
                "Open": open_price,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            },
            index=index,
        )

    except Exception:

        return pd.DataFrame()


# ============================================================
# ENGINE VALIDATION
# ============================================================

def validate_trend_engine():
    """
    Trend Engine 5.4 kapsamlı test.

    Testler:

        1. Empty input
        2. Valid input
        3. Contract
        4. Timeframes
        5. Score range
        6. Confidence range
        7. Bullish scenario
        8. Bearish scenario
        9. Neutral scenario
        10. Real output chain format
    """

    tests = {}

    # ========================================================
    # 1 - EMPTY INPUT
    # ========================================================

    try:

        result = trend_engine({})

        tests["EMPTY_INPUT"] = (
            isinstance(
                result,
                dict,
            )
        )

    except Exception:

        tests["EMPTY_INPUT"] = False

    # ========================================================
    # 2 - BULLISH INPUT
    # ========================================================

    try:

        market_data = {

            "price": 730.0,

            "df_1m": _create_test_dataframe(
                "BULLISH"
            ),

            "df_5m": _create_test_dataframe(
                "BULLISH"
            ),

            "df_15m": _create_test_dataframe(
                "BULLISH"
            ),
        }

        bullish_result = trend_engine(
            market_data
        )

        tests["BULLISH_EXECUTION"] = (
            isinstance(
                bullish_result,
                dict,
            )
            and bullish_result.get(
                "valid",
                False,
            )
        )

    except Exception:

        bullish_result = {}
        tests["BULLISH_EXECUTION"] = False

    # ========================================================
    # 3 - BEARISH INPUT
    # ========================================================

    try:

        market_data = {

            "price": 700.0,

            "df_1m": _create_test_dataframe(
                "BEARISH"
            ),

            "df_5m": _create_test_dataframe(
                "BEARISH"
            ),

            "df_15m": _create_test_dataframe(
                "BEARISH"
            ),
        }

        bearish_result = trend_engine(
            market_data
        )

        tests["BEARISH_EXECUTION"] = (
            isinstance(
                bearish_result,
                dict,
            )
            and bearish_result.get(
                "valid",
                False,
            )
        )

    except Exception:

        bearish_result = {}
        tests["BEARISH_EXECUTION"] = False

    # ========================================================
    # 4 - CONTRACT
    # ========================================================

    try:

        contract_ok, missing = (
            validate_trend_contract(
                bullish_result
            )
        )

        tests["DECISION_CONTRACT"] = (
            contract_ok
            and not missing
        )

    except Exception:

        tests["DECISION_CONTRACT"] = False

    # ========================================================
    # 5 - TIMEFRAMES
    # ========================================================

    try:

        timeframes = bullish_result.get(
            "timeframes",
            {},
        )

        tests["TIMEFRAME_1M"] = (
            "1m" in timeframes
        )

        tests["TIMEFRAME_5M"] = (
            "5m" in timeframes
        )

        tests["TIMEFRAME_15M"] = (
            "15m" in timeframes
        )

    except Exception:

        tests["TIMEFRAME_1M"] = False
        tests["TIMEFRAME_5M"] = False
        tests["TIMEFRAME_15M"] = False

    # ========================================================
    # 6 - SCORE RANGE
    # ========================================================

    try:

        score = safe_float(
            bullish_result.get(
                "score",
                -1,
            ),
            -1,
        )

        final_score = safe_float(
            bullish_result.get(
                "final_score",
                -1,
            ),
            -1,
        )

        trend_score = safe_float(
            bullish_result.get(
                "trend_score",
                -1,
            ),
            -1,
        )

        tests["SCORE_RANGE"] = (
            0 <= score <= 100
            and 0 <= final_score <= 100
            and 0 <= trend_score <= 100
        )

    except Exception:

        tests["SCORE_RANGE"] = False

    # ========================================================
    # 7 - CONFIDENCE RANGE
    # ========================================================

    try:

        confidence = safe_float(
            bullish_result.get(
                "confidence",
                -1,
            ),
            -1,
        )

        tests["CONFIDENCE_RANGE"] = (
            0 <= confidence <= 98
        )

    except Exception:

        tests["CONFIDENCE_RANGE"] = False

    # ========================================================
    # 8 - BULLISH DIRECTION
    # ========================================================

    try:

        tests["BULLISH_DIRECTION"] = (
            bullish_result.get(
                "trend_bias"
            )
            == "BULLISH"
        )

    except Exception:

        tests["BULLISH_DIRECTION"] = False

    # ========================================================
    # 9 - BEARISH DIRECTION
    # ========================================================

    try:

        tests["BEARISH_DIRECTION"] = (
            bearish_result.get(
                "trend_bias"
            )
            == "BEARISH"
        )

    except Exception:

        tests["BEARISH_DIRECTION"] = False

    # ========================================================
    # 10 - OUTPUT TYPES
    # ========================================================

    try:

        tests["OUTPUT_TYPES"] = (
            isinstance(
                bullish_result.get(
                    "score"
                ),
                (int, np.integer),
            )
            and isinstance(
                bullish_result.get(
                    "confidence"
                ),
                (int, np.integer),
            )
            and isinstance(
                bullish_result.get(
                    "trend_bias"
                ),
                str,
            )
            and isinstance(
                bullish_result.get(
                    "timeframes"
                ),
                dict,
            )
        )

    except Exception:

        tests["OUTPUT_TYPES"] = False

    # ========================================================
    # SUMMARY
    # ========================================================

    passed = sum(
        bool(value)
        for value in tests.values()
    )

    total = len(tests)

    failed = (
        total
        - passed
    )

    return {

        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,

        "status": (
            "PASS"
            if failed == 0
            else "FAIL"
        ),

        "total_tests": total,
        "passed": passed,
        "failed": failed,

        "tests": tests,
    }


# ============================================================
# PRINT VALIDATION
# ============================================================

def print_validation_report():
    """
    Terminal test raporu.
    """

    report = validate_trend_engine()

    print()
    print("=" * 80)
    print(
        "QQQ PRO TREND ENGINE 5.4 VALIDATION"
    )
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

    for name, passed in report[
        "tests"
    ].items():

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

    print_validation_report()