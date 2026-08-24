from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


# ============================================================
# QQQ PRO
# big_move_warning_engine.py
#
# BIG MOVE EARLY WARNING ENGINE
#
# Görev:
#
# QQQ 1m fiyat / hacim verisi üzerinden erken büyük hareket
# riskini analiz eder.
#
# Şu aşamada ana kullanım:
#
# PUT REVERSAL WARNING
#
# Bu motor:
# - PUT AL emri üretmez.
# - CALL AL emri üretmez.
# - Broker emri göndermez.
# - Decision Engine yerine karar vermez.
#
# Sadece:
#
# warning
# warning_type
# warning_score
# risk_level
# call_veto
# put_entry_candidate
#
# üretir.
#
# Replay audit sonucu kullanılan filtre:
#
# warning_score >= 80
# distance_from_peak <= %0.20
# vol15_ratio <= 0.95
# vol5_ratio <= 0.90
# prior_up_move >= $2.00
#
# Amaç:
#
# Güçlü yükseliş sonrası:
#
# - yeni tepe başarısızlığı
# - tepe yakınlığı
# - hacim zayıflaması
# - momentum kaybı
#
# oluştuğunda CALL giriş riskini erken tespit etmek.
#
# ============================================================


ENGINE_NAME = "QQQ PRO Big Move Warning Engine"
ENGINE_VERSION = "1.0"


# ============================================================
# CONSTANTS
# ============================================================


MIN_REQUIRED_BARS = 60

LOOKBACK_BARS = 60

PEAK_LOOKBACK_BARS = 30

LAST_15_BARS = 15

LAST_5_BARS = 5


# ------------------------------------------------------------
# BASE DETECTION SETTINGS
# ------------------------------------------------------------


MIN_PREVIOUS_UP_MOVE_DOLLARS = 1.50

BASE_PEAK_DISTANCE_MAX_PCT = 0.20

BASE_VOL15_MAX_RATIO = 0.95

BASE_VOL5_MAX_RATIO = 0.90


# ------------------------------------------------------------
# FINAL FILTER
#
# 8 günlük replay filtresi:
#
# SCORE >= 80
# PEAK <= 0.20%
# VOL15 <= 0.95
# VOL5 <= 0.90
# PRIOR UP >= $2.00
# ------------------------------------------------------------


FILTER_SCORE_MIN = 80

FILTER_PEAK_DISTANCE_MAX_PCT = 0.20

FILTER_VOL15_MAX_RATIO = 0.95

FILTER_VOL5_MAX_RATIO = 0.90

FILTER_PRIOR_UP_MOVE_MIN_DOLLARS = 2.00


# ------------------------------------------------------------
# RISK LEVELS
# ------------------------------------------------------------


RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"


WARNING_NONE = "NONE"

WARNING_PUT_REVERSAL = "PUT_REVERSAL_WARNING"


# ============================================================
# SAFE HELPERS
# ============================================================


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        if value is None:

            return default

        result = float(
            value
        )

        if np.isnan(
            result
        ):

            return default

        return result

    except Exception:

        return default


def safe_bool(
    value: Any,
    default: bool = False,
) -> bool:

    try:

        if isinstance(
            value,
            bool,
        ):

            return value

        if value is None:

            return default

        text = str(
            value
        ).strip().upper()

        if text in (
            "TRUE",
            "1",
            "YES",
            "EVET",
        ):

            return True

        if text in (
            "FALSE",
            "0",
            "NO",
            "HAYIR",
        ):

            return False

        return bool(
            value
        )

    except Exception:

        return default


def normalize_text(
    value: Any,
    default: str = "UNKNOWN",
) -> str:

    if value is None:

        return default

    try:

        if pd.isna(
            value
        ):

            return default

    except Exception:

        pass

    text = str(
        value
    ).strip().upper()

    return (
        text
        if text
        else default
    )


# ============================================================
# DATAFRAME VALIDATION
# ============================================================


def normalize_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if not isinstance(
        df,
        pd.DataFrame,
    ):

        return pd.DataFrame()

    if df.empty:

        return pd.DataFrame()

    data = df.copy()

    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        data.columns = [
            str(
                col[0]
            ).strip()
            for col in data.columns
        ]

    else:

        data.columns = [
            str(
                col
            )
            .replace(
                "\ufeff",
                "",
            )
            .strip()
            for col in data.columns
        ]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    if not set(
        required
    ).issubset(
        set(
            data.columns
        )
    ):

        return pd.DataFrame()

    data = data[
        required
    ].copy()

    for col in required:

        data[
            col
        ] = pd.to_numeric(
            data[col],
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

    data = data.sort_index()

    data = data[
        ~data.index.duplicated(
            keep="last"
        )
    ]

    return data


# ============================================================
# DEFAULT RESPONSE
# ============================================================


def default_warning_response(
    reason: str = "",
) -> Dict[str, Any]:

    return {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "valid":
            False,

        "warning":
            False,

        "warning_type":
            WARNING_NONE,

        "warning_score":
            0,

        "filtered_warning":
            False,

        "risk_level":
            RISK_LOW,

        "call_veto":
            False,

        "put_entry_candidate":
            False,

        "prior_up_move_$":
            0.0,

        "peak_price":
            0.0,

        "peak_time":
            None,

        "distance_from_peak_%":
            0.0,

        "vol60":
            0.0,

        "vol15":
            0.0,

        "vol5":
            0.0,

        "vol15_ratio":
            0.0,

        "vol5_ratio":
            0.0,

        "failed_new_high":
            False,

        "lower_close_pressure":
            False,

        "reason":
            reason,

        "filter_reason":
            "",

        "status":
            "NO_WARNING",

    }


# ============================================================
# SAME SESSION DATA
# ============================================================


def current_session_data(
    df: pd.DataFrame,
    bars: int = LOOKBACK_BARS,
) -> pd.DataFrame:

    if df.empty:

        return pd.DataFrame()

    current_ts = df.index[
        -1
    ]

    try:

        current_date = (
            current_ts.date()
        )

        session = df[
            pd.Index(
                df.index.date
            )
            == current_date
        ].copy()

    except Exception:

        session = df.copy()

    if session.empty:

        return pd.DataFrame()

    return session.tail(
        bars
    ).copy()


# ============================================================
# PRICE STRUCTURE
# ============================================================


def calculate_peak_structure(
    history: pd.DataFrame,
) -> Dict[str, Any]:

    result = {

        "peak_price": 0.0,

        "peak_time": None,

        "prior_low": 0.0,

        "prior_up_move_$": 0.0,

        "distance_from_peak_%": 0.0,

        "failed_new_high": False,

    }

    if history.empty:

        return result

    current_close = safe_float(
        history[
            "Close"
        ].iloc[
            -1
        ]
    )

    peak_window = history.tail(
        PEAK_LOOKBACK_BARS
    )

    if peak_window.empty:

        return result

    peak_price = safe_float(
        peak_window[
            "High"
        ].max()
    )

    try:

        peak_time = peak_window[
            "High"
        ].idxmax()

    except Exception:

        peak_time = None

    prior_low = safe_float(
        history[
            "Low"
        ].min()
    )

    prior_up_move = max(
        0.0,
        peak_price
        - prior_low,
    )

    if peak_price > 0:

        distance_from_peak_pct = (
            (
                peak_price
                - current_close
            )
            / peak_price
            * 100.0
        )

    else:

        distance_from_peak_pct = 999.0

    recent10 = history.tail(
        10
    )

    if not recent10.empty:

        recent_high = safe_float(
            recent10[
                "High"
            ].max()
        )

        failed_new_high = bool(
            recent_high
            <= peak_price
            * 1.0002
        )

    else:

        failed_new_high = False

    result.update(
        {

            "peak_price":
                round(
                    peak_price,
                    4,
                ),

            "peak_time":
                peak_time,

            "prior_low":
                round(
                    prior_low,
                    4,
                ),

            "prior_up_move_$":
                round(
                    prior_up_move,
                    4,
                ),

            "distance_from_peak_%":
                round(
                    max(
                        0.0,
                        distance_from_peak_pct,
                    ),
                    4,
                ),

            "failed_new_high":
                failed_new_high,

        }
    )

    return result


# ============================================================
# VOLUME STRUCTURE
# ============================================================


def calculate_volume_structure(
    history: pd.DataFrame,
) -> Dict[str, Any]:

    result = {

        "vol60": 0.0,

        "vol15": 0.0,

        "vol5": 0.0,

        "vol15_ratio": 0.0,

        "vol5_ratio": 0.0,

    }

    if history.empty:

        return result

    volume = pd.to_numeric(
        history[
            "Volume"
        ],
        errors="coerce",
    ).fillna(
        0.0
    )

    vol60 = safe_float(
        volume.mean()
    )

    vol15 = safe_float(
        volume.tail(
            LAST_15_BARS
        ).mean()
    )

    vol5 = safe_float(
        volume.tail(
            LAST_5_BARS
        ).mean()
    )

    vol15_ratio = (
        vol15
        / vol60
        if vol60 > 0
        else 0.0
    )

    vol5_ratio = (
        vol5
        / vol60
        if vol60 > 0
        else 0.0
    )

    result.update(
        {

            "vol60":
                round(
                    vol60,
                    2,
                ),

            "vol15":
                round(
                    vol15,
                    2,
                ),

            "vol5":
                round(
                    vol5,
                    2,
                ),

            "vol15_ratio":
                round(
                    vol15_ratio,
                    4,
                ),

            "vol5_ratio":
                round(
                    vol5_ratio,
                    4,
                ),

        }
    )

    return result


# ============================================================
# CLOSE PRESSURE
# ============================================================


def detect_lower_close_pressure(
    history: pd.DataFrame,
) -> bool:

    if len(
        history
    ) < 3:

        return False

    closes = pd.to_numeric(
        history[
            "Close"
        ].tail(
            3
        ),
        errors="coerce",
    ).tolist()

    if len(
        closes
    ) < 3:

        return False

    c1 = safe_float(
        closes[-3]
    )

    c2 = safe_float(
        closes[-2]
    )

    c3 = safe_float(
        closes[-1]
    )

    return bool(
        c3 <= c2
        or c2 <= c1
    )


# ============================================================
# BASE WARNING SCORE
# ============================================================


def calculate_warning_score(
    prior_up_move: float,
    distance_from_peak_pct: float,
    failed_new_high: bool,
    vol15_ratio: float,
    vol5_ratio: float,
    lower_close_pressure: bool,
) -> Dict[str, Any]:

    score = 0

    reasons: List[
        str
    ] = []

    if (
        prior_up_move
        >= MIN_PREVIOUS_UP_MOVE_DOLLARS
    ):

        score += 25

        reasons.append(
            "öncesinde güçlü yükseliş"
        )

    if (
        distance_from_peak_pct
        <= BASE_PEAK_DISTANCE_MAX_PCT
    ):

        score += 20

        reasons.append(
            "fiyat tepeye yakın"
        )

    if failed_new_high:

        score += 20

        reasons.append(
            "yeni tepe başarısız"
        )

    if (
        vol15_ratio
        <= BASE_VOL15_MAX_RATIO
    ):

        score += 15

        reasons.append(
            "15m hacim zayıflıyor"
        )

    if (
        vol5_ratio
        <= BASE_VOL5_MAX_RATIO
    ):

        score += 15

        reasons.append(
            "5m hacim zayıflıyor"
        )

    if lower_close_pressure:

        score += 5

        reasons.append(
            "kapanış baskısı"
        )

    return {

        "score":
            min(
                100,
                score,
            ),

        "reason":
            " | ".join(
                reasons
            ),

    }


# ============================================================
# FINAL FILTER
# ============================================================


def apply_reversal_filter(
    warning_score: float,
    distance_from_peak_pct: float,
    vol15_ratio: float,
    vol5_ratio: float,
    prior_up_move: float,
) -> Dict[str, Any]:

    checks = {

        "score_ok":
            warning_score
            >= FILTER_SCORE_MIN,

        "peak_ok":
            distance_from_peak_pct
            <= FILTER_PEAK_DISTANCE_MAX_PCT,

        "vol15_ok":
            vol15_ratio
            <= FILTER_VOL15_MAX_RATIO,

        "vol5_ok":
            vol5_ratio
            <= FILTER_VOL5_MAX_RATIO,

        "prior_up_ok":
            prior_up_move
            >= FILTER_PRIOR_UP_MOVE_MIN_DOLLARS,

    }

    filtered_warning = all(
        checks.values()
    )

    reasons: List[
        str
    ] = []

    if checks[
        "score_ok"
    ]:

        reasons.append(
            "score teyitli"
        )

    if checks[
        "peak_ok"
    ]:

        reasons.append(
            "tepe mesafesi uygun"
        )

    if checks[
        "vol15_ok"
    ]:

        reasons.append(
            "15m hacim filtresi uygun"
        )

    if checks[
        "vol5_ok"
    ]:

        reasons.append(
            "5m hacim filtresi uygun"
        )

    if checks[
        "prior_up_ok"
    ]:

        reasons.append(
            "ön yükseliş yeterli"
        )

    return {

        "filtered_warning":
            bool(
                filtered_warning
            ),

        "checks":
            checks,

        "filter_reason":
            " | ".join(
                reasons
            ),

    }


# ============================================================
# RISK CLASSIFICATION
# ============================================================


def classify_warning_risk(
    filtered_warning: bool,
    warning_score: float,
) -> str:

    if not filtered_warning:

        if warning_score >= 80:

            return RISK_MEDIUM

        return RISK_LOW

    if warning_score >= 100:

        return RISK_CRITICAL

    return RISK_HIGH


# ============================================================
# MAIN ANALYZER
# ============================================================


def analyze_big_move_warning(
    market: Dict[str, Any] | None = None,
    df: pd.DataFrame | None = None,
) -> Dict[str, Any]:

    try:

        if df is None:

            if isinstance(
                market,
                dict,
            ):

                df = market.get(
                    "df_1m"
                )

        if not isinstance(
            df,
            pd.DataFrame,
        ):

            return default_warning_response(
                "df_1m bulunamadı."
            )

        data = normalize_dataframe(
            df
        )

        if data.empty:

            return default_warning_response(
                "Geçerli OHLCV verisi yok."
            )

        if len(
            data
        ) < MIN_REQUIRED_BARS:

            return default_warning_response(
                (
                    f"Yetersiz 1m veri: "
                    f"{len(data)} bar."
                )
            )

        history = current_session_data(
            data,
            LOOKBACK_BARS,
        )

        if len(
            history
        ) < 20:

            return default_warning_response(
                "Mevcut seans geçmişi yetersiz."
            )

        price_structure = (
            calculate_peak_structure(
                history
            )
        )

        volume_structure = (
            calculate_volume_structure(
                history
            )
        )

        lower_close_pressure = (
            detect_lower_close_pressure(
                history
            )
        )

        prior_up_move = safe_float(
            price_structure.get(
                "prior_up_move_$"
            )
        )

        distance_from_peak = safe_float(
            price_structure.get(
                "distance_from_peak_%"
            )
        )

        failed_new_high = safe_bool(
            price_structure.get(
                "failed_new_high"
            )
        )

        vol15_ratio = safe_float(
            volume_structure.get(
                "vol15_ratio"
            )
        )

        vol5_ratio = safe_float(
            volume_structure.get(
                "vol5_ratio"
            )
        )

        base = calculate_warning_score(

            prior_up_move=
                prior_up_move,

            distance_from_peak_pct=
                distance_from_peak,

            failed_new_high=
                failed_new_high,

            vol15_ratio=
                vol15_ratio,

            vol5_ratio=
                vol5_ratio,

            lower_close_pressure=
                lower_close_pressure,

        )

        warning_score = safe_float(
            base.get(
                "score"
            )
        )

        # Base warning:
        # Henüz final filtre değil.
        base_warning = bool(
            warning_score >= 70
            and prior_up_move
            >= MIN_PREVIOUS_UP_MOVE_DOLLARS
            and failed_new_high
            and vol15_ratio
            <= BASE_VOL15_MAX_RATIO
        )

        filter_result = (
            apply_reversal_filter(

                warning_score=
                    warning_score,

                distance_from_peak_pct=
                    distance_from_peak,

                vol15_ratio=
                    vol15_ratio,

                vol5_ratio=
                    vol5_ratio,

                prior_up_move=
                    prior_up_move,

            )
        )

        filtered_warning = safe_bool(
            filter_result.get(
                "filtered_warning"
            )
        )

        risk_level = (
            classify_warning_risk(
                filtered_warning,
                warning_score,
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Bu motor doğrudan PUT AL üretmez.
        #
        # Filtrelenmiş PUT reversal warning yalnız CALL tarafını
        # veto/risk moduna alır.
        # ----------------------------------------------------

        call_veto = bool(
            filtered_warning
            and risk_level
            in (
                RISK_HIGH,
                RISK_CRITICAL,
            )
        )

        put_entry_candidate = False

        current_price = safe_float(
            history[
                "Close"
            ].iloc[
                -1
            ]
        )

        return {

            "engine":
                ENGINE_NAME,

            "version":
                ENGINE_VERSION,

            "valid":
                True,

            "price":
                round(
                    current_price,
                    4,
                ),

            "warning":
                bool(
                    base_warning
                ),

            "warning_type":
                (
                    WARNING_PUT_REVERSAL
                    if base_warning
                    else WARNING_NONE
                ),

            "warning_score":
                round(
                    warning_score,
                    2,
                ),

            "filtered_warning":
                filtered_warning,

            "risk_level":
                risk_level,

            "call_veto":
                call_veto,

            "put_entry_candidate":
                put_entry_candidate,

            "prior_up_move_$":
                prior_up_move,

            "peak_price":
                safe_float(
                    price_structure.get(
                        "peak_price"
                    )
                ),

            "peak_time":
                price_structure.get(
                    "peak_time"
                ),

            "distance_from_peak_%":
                distance_from_peak,

            "vol60":
                safe_float(
                    volume_structure.get(
                        "vol60"
                    )
                ),

            "vol15":
                safe_float(
                    volume_structure.get(
                        "vol15"
                    )
                ),

            "vol5":
                safe_float(
                    volume_structure.get(
                        "vol5"
                    )
                ),

            "vol15_ratio":
                vol15_ratio,

            "vol5_ratio":
                vol5_ratio,

            "failed_new_high":
                failed_new_high,

            "lower_close_pressure":
                lower_close_pressure,

            "reason":
                base.get(
                    "reason",
                    "",
                ),

            "filter_reason":
                filter_result.get(
                    "filter_reason",
                    "",
                ),

            "filter_checks":
                filter_result.get(
                    "checks",
                    {},
                ),

            "status":
                (
                    "PUT_REVERSAL_RISK"
                    if filtered_warning
                    else
                    "WARNING_ONLY"
                    if base_warning
                    else
                    "NO_WARNING"
                ),

        }

    except Exception as exc:

        return default_warning_response(
            f"Big Move Warning Engine hatası: {exc}"
        )


# ============================================================
# ALIAS
# ============================================================


def big_move_warning_engine(
    market: Dict[str, Any] | None = None,
    df: pd.DataFrame | None = None,
) -> Dict[str, Any]:

    return analyze_big_move_warning(
        market=market,
        df=df,
    )


# ============================================================
# ENGINE HEALTH
# ============================================================


def engine_health() -> Dict[str, Any]:

    return {

        "engine":
            ENGINE_NAME,

        "version":
            ENGINE_VERSION,

        "status":
            "OK",

        "mode":
            "RISK_WARNING_ONLY",

        "settings": {

            "min_required_bars":
                MIN_REQUIRED_BARS,

            "lookback_bars":
                LOOKBACK_BARS,

            "filter_score_min":
                FILTER_SCORE_MIN,

            "filter_peak_max":
                FILTER_PEAK_DISTANCE_MAX_PCT,

            "filter_vol15_max":
                FILTER_VOL15_MAX_RATIO,

            "filter_vol5_max":
                FILTER_VOL5_MAX_RATIO,

            "filter_prior_up_min":
                FILTER_PRIOR_UP_MOVE_MIN_DOLLARS,

        },

        "capabilities": [

            "PUT_REVERSAL_WARNING",

            "FILTERED_WARNING",

            "CALL_VETO",

            "RISK_LEVEL",

        ],

        "limitations": [

            "NO_DIRECT_PUT_ENTRY",

            "NO_BROKER_EXECUTION",

            "NO_OPTIONS_CHAIN_USAGE",

        ],

    }


# ============================================================
# DIRECT TEST
# ============================================================


if __name__ == "__main__":

    print(
        "=" * 80
    )

    print(
        "QQQ PRO - BIG MOVE WARNING ENGINE"
    )

    print(
        "=" * 80
    )

    print(
        engine_health()
    )

    print(
        "=" * 80
    )