from __future__ import annotations

from typing import Any, Dict, Optional


# ============================================================
# QQQ PRO v5.6
# decision_engine.py
#
# FINAL DECISION ENGINE
#
# PIPELINE:
# MARKET DATA
#     ↓
# TREND
#     ↓
# SIGNAL
#     ↓
# GAP
#     ↓
# SUPPORT / RESISTANCE
#     ↓
# PATTERN
#     ↓
# SCORE + CONFIRMATION
#     ↓
# OPTIONS RISK GATE
#     ↓
# FINAL DECISION
#
# ÇIKIŞLAR:
# CALL AL
# PUT AL
# BEKLE
# CALL KORU
# PUT KORU
# CALL KAPAT
# PUT KAPAT
#
# v5.3 DEĞİŞİKLİKLERİ:
# - ENGINE_VERSION gerçek olarak tanımlandı.
# - Entry eşiği 60 -> 55 olarak güncellendi.
# - S/R güçlü dönüş olayları giriş kararında korunuyor.
# - Mevcut CALL pozisyonunda SUPPORT_BREAK güçlü çıkış filtresi.
# - Mevcut PUT pozisyonunda RESISTANCE_BREAK güçlü çıkış filtresi.
# - Zıt yönlü skor 55+ olduğunda pozisyon çıkışı mümkün.
# - Options Risk Gate korunmuştur.
# - Kontrollü SUPPORT_BOUNCE reversal CALL yolu eklendi.
# - Kontrollü SUPPORT_BREAK early PUT yolu eklendi.
# - RESISTANCE_BREAK CALL için genel gevşetme yapılmadı.
# - Big Move Warning CALL Veto Gate eklendi.
# - Big Move Warning doğrudan PUT AL üretmez.
# - Reversal Confirmation Engine input gate eklendi.
# - Yalnız FIRST_SIGNAL + strong PUT candidate yeni PUT AL üretebilir.
# - SAME_EVENT_CONFIRMATION yeni giriş üretmez.
# - HARD_CALL_PROTECTION yanlış PUT reversal girişini engeller.
# - v5.8: Açık PUT + teyitli bullish SUPPORT_BOUNCE -> PUT KAPAT.
# - v5.8: Aynı bar içinde otomatik PUT->CALL flip yapılmaz.
# - v5.8.2: Reversal v1.2 LATE_PUT_BLOCKED, normal PUT AL dahil yeni PUT girişini veto eder.
# - v5.8.4: Kontrollü simetrik reversal position-exit gate eklendi.
# - v5.8.5: Zayıf INSIDE_RANGE + DOUBLE_TOP PUT giriş filtresi eklendi.
# - v5.8.6: Açık pozisyon branch'inde weak_range gate diagnostic değişkeni tanımsız kalma hatası düzeltildi.
# - v5.8.7: SUPPORT_BOUNCE structural CALL için bearish Trend/Signal veto.
# - v5.8.8: Kontrollü INSIDE_RANGE CALL recovery yolu.
# - v5.8.9: TÜM yeni CALL AL yolları için ortak final CALL safety gate.
# - v5.8.10: Controlled CALL Recovery yalnız 10:30 sonrası aktif; opening false-recovery kapatıldı.
# - v5.8.11: HIGH Big-Move Warning altında recovery CALL mutlaka ceza sonrası minimum giriş kalitesini korur.
# - v5.8.12: Açık pozisyon branch'inde recovery/final CALL gate diagnostic değişkenleri varsayılan tanımlandı.
# - v5.8.3: SUPPORT_BOUNCE CALL yolu dengelendi; bearish pattern yalnız güçlü CALL çoğunluğunda aşılabilir.
# - v5.8.3: Doğrulanmış structural CALL ile aynı-bar PUT reversal çatışmasında güvenli BEKLE.
# ============================================================


# ============================================================
# ENGINE INFO
# ============================================================

ENGINE_NAME = "QQQ PRO Decision Engine"
ENGINE_VERSION = "5.8.13"


# ============================================================
# ACTION CONSTANTS
# ============================================================

ACTION_CALL_BUY = "CALL AL"
ACTION_PUT_BUY = "PUT AL"
ACTION_WAIT = "BEKLE"

ACTION_CALL_HOLD = "CALL KORU"
ACTION_PUT_HOLD = "PUT KORU"

ACTION_CALL_CLOSE = "CALL KAPAT"
ACTION_PUT_CLOSE = "PUT KAPAT"


# ============================================================
# SIGNAL CONSTANTS
# ============================================================

SIGNAL_CALL = "CALL"
SIGNAL_PUT = "PUT"
SIGNAL_NEUTRAL = "NEUTRAL"


# ============================================================
# TREND CONSTANTS
# ============================================================

TREND_BULLISH = "BULLISH"
TREND_BEARISH = "BEARISH"
TREND_NEUTRAL = "NEUTRAL"


# ============================================================
# DECISION SETTINGS
# ============================================================

MIN_ENTRY_SCORE = 55.0
MIN_ENTRY_CONFIDENCE = 70.0
MIN_CONFIRMATIONS = 2
MIN_SCORE_EDGE = 10.0

MIN_EXIT_SCORE = 55.0
MIN_EXIT_CONFIRMATIONS = 2

# v5.8.4 - controlled multi-factor reversal exit
REVERSAL_EXIT_MIN_CONFIRMATIONS = 3
REVERSAL_EXIT_MAX_OPPOSING_CONFIRMATIONS = 0
REVERSAL_EXIT_MIN_SCORE_EDGE = 15.0

# Controlled structural-entry exceptions
REVERSAL_MIN_CONFIDENCE = 80.0
REVERSAL_MIN_CONFIRMATION_EDGE = 2
REVERSAL_MIN_CALL_CONFIRMATIONS = 3
REVERSAL_MIN_SCORE_EDGE = 15.0

# v5.8.3 - Balanced SUPPORT_BOUNCE CALL recovery path.
# Normal CALL kuralları gevşetilmez; yalnız gerçek SUPPORT_BOUNCE
# yapısında, birbiriyle uyumlu CALL kanıtlarının bearish pattern
# gecikmesini aşabilmesine izin verilir.
SUPPORT_BOUNCE_CALL_MIN_CONFIDENCE = 70.0
SUPPORT_BOUNCE_CALL_MIN_CONFIRMATIONS = 2
SUPPORT_BOUNCE_CALL_MIN_CONFIRMATION_EDGE = 1
SUPPORT_BOUNCE_CALL_MIN_SCORE_EDGE = 5.0
SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_CONFIRMATIONS = 3
SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_CONFIRMATION_EDGE = 2
SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_SCORE_EDGE = 10.0
SUPPORT_BOUNCE_MIN_BULLISH_PATTERN_SCORE = 55.0

RECOVERY_CALL_MIN_SIGNAL_SCORE = 65.0
RECOVERY_CALL_MIN_TREND_SCORE = 53.0
RECOVERY_CALL_MIN_CONFIRMATIONS = 2
RECOVERY_CALL_MAX_PUT_CONFIRMATIONS = 1
RECOVERY_CALL_MIN_SCORE_EDGE = 2.0
RECOVERY_CALL_ALLOWED_SR_EVENTS = {"INSIDE_RANGE", "RANGE", "NO_EVENT"}
RECOVERY_CALL_SESSION_START = "10:30"

EARLY_BREAK_MIN_PUT_CONFIRMATIONS = 2
EARLY_BREAK_MIN_CONFIDENCE = 65.0
EARLY_BREAK_MAX_CALL_SCORE = 35.0

# Big Move Warning controlled CALL-risk settings
BIG_MOVE_HIGH_SCORE_PENALTY = 5.0
BIG_MOVE_HIGH_CONFIDENCE_PENALTY = 5.0
BIG_MOVE_CRITICAL_SCORE_PENALTY = 10.0
BIG_MOVE_CRITICAL_CONFIDENCE_PENALTY = 10.0
BIG_MOVE_HIGH_BEARISH_CONFIRMATIONS_REQUIRED = 2
BIG_MOVE_CRITICAL_BEARISH_CONFIRMATIONS_REQUIRED = 1

MAX_SCORE = 100.0


# ============================================================
# MOTOR WEIGHTS
#
# Trend        25
# Signal       25
# Gap          10
# S/R          20
# Pattern      20
#
# TOPLAM = 100
# ============================================================

WEIGHT_TREND = 25.0
WEIGHT_SIGNAL = 25.0
WEIGHT_GAP = 10.0
WEIGHT_SR = 20.0
WEIGHT_PATTERN = 20.0

TOTAL_WEIGHT = (
    WEIGHT_TREND
    + WEIGHT_SIGNAL
    + WEIGHT_GAP
    + WEIGHT_SR
    + WEIGHT_PATTERN
)


# ============================================================
# S/R ENTRY EVENTS
# ============================================================

CALL_SR_EVENTS = {
    "BREAKOUT_UP",
    "BREAKOUT_R1",
    "BREAKOUT_R2",
    "RESISTANCE_BREAK",
    "SUPPORT_BOUNCE",
    "BOUNCE_SUPPORT",
}

PUT_SR_EVENTS = {
    "BREAKOUT_DOWN",
    "BREAKDOWN",
    "BREAKDOWN_S1",
    "BREAKDOWN_S2",
    "SUPPORT_BREAK",
    "RESISTANCE_REJECTION",
    "REJECT_RESISTANCE",
}


# ============================================================
# S/R EXIT EVENTS
# ============================================================

CALL_EXIT_SR_EVENTS = {
    "SUPPORT_BREAK",
    "BREAKOUT_DOWN",
    "BREAKDOWN",
    "BREAKDOWN_S1",
    "BREAKDOWN_S2",
}

PUT_EXIT_SR_EVENTS = {
    "RESISTANCE_BREAK",
    "BREAKOUT_UP",
    "BREAKOUT_R1",
    "BREAKOUT_R2",
}


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

        if isinstance(value, bool):
            return float(value)

        if hasattr(value, "iloc"):

            try:
                if len(value) == 0:
                    return default

                value = value.iloc[-1]

            except Exception:
                return default

        result = float(value)

        if result != result:
            return default

        return result

    except Exception:
        return default


def safe_dict(
    value: Any,
) -> Dict[str, Any]:

    if isinstance(value, dict):
        return value

    return {}


def normalize_text(
    value: Any,
    default: str = "",
) -> str:

    if value is None:
        return default

    text = str(value).strip().upper()

    return text if text else default


def clamp_score(
    value: Any,
) -> float:

    value = safe_float(
        value,
        0.0,
    )

    if value < 0:
        return 0.0

    if value > MAX_SCORE:
        return MAX_SCORE

    return value


def first_value(
    data: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:

    for key in keys:

        if key in data and data[key] is not None:
            return data[key]

    return default


# ============================================================
# S/R NORMALIZATION
# ============================================================

def normalize_sr(
    value: Any,
) -> Dict[str, Any]:

    sr = safe_dict(value)

    return {

        "pivot": safe_float(
            first_value(
                sr,
                "pivot",
                "daily_pivot",
                "PIVOT",
                default=0.0,
            ),
            0.0,
        ),

        "support_1": safe_float(
            first_value(
                sr,
                "support_1",
                "s1",
                "S1",
                "support",
                default=0.0,
            ),
            0.0,
        ),

        "support_2": safe_float(
            first_value(
                sr,
                "support_2",
                "s2",
                "S2",
                default=0.0,
            ),
            0.0,
        ),

        "resistance_1": safe_float(
            first_value(
                sr,
                "resistance_1",
                "r1",
                "R1",
                "resistance",
                default=0.0,
            ),
            0.0,
        ),

        "resistance_2": safe_float(
            first_value(
                sr,
                "resistance_2",
                "r2",
                "R2",
                default=0.0,
            ),
            0.0,
        ),

        "event": normalize_text(
            first_value(
                sr,
                "event",
                "sr_event",
                "signal_event",
                "behavior",
                default="NONE",
            )
        ),

        "signal": normalize_text(
            first_value(
                sr,
                "signal",
                default="",
            )
        ),

        "behavior": normalize_text(
            first_value(
                sr,
                "behavior",
                default="",
            )
        ),
    }


def detect_sr_event(
    sr: Dict[str, Any],
) -> str:

    event = normalize_text(
        first_value(
            safe_dict(sr),
            "event",
            "sr_event",
            "signal_event",
            "behavior",
            "signal",
            default="NONE",
        )
    )

    mapping = {

        "BREAKOUT_UP": "RESISTANCE_BREAK",
        "BREAKOUT_R1": "RESISTANCE_BREAK",
        "BREAKOUT_R2": "RESISTANCE_BREAK",

        "BREAKOUT_DOWN": "SUPPORT_BREAK",
        "BREAKDOWN": "SUPPORT_BREAK",
        "BREAKDOWN_S1": "SUPPORT_BREAK",
        "BREAKDOWN_S2": "SUPPORT_BREAK",

        "REJECT_SUPPORT": "SUPPORT_BOUNCE",
        "BOUNCE_SUPPORT": "SUPPORT_BOUNCE",

        "REJECT_RESISTANCE": "RESISTANCE_REJECTION",
    }

    return mapping.get(
        event,
        event,
    )


# ============================================================
# SIGNAL NORMALIZATION
# ============================================================

def normalize_signal(
    value: Any,
) -> str:

    text = normalize_text(value)

    if not text:
        return SIGNAL_NEUTRAL

    if any(
        token in text
        for token in (
            "PUT",
            "SHORT",
            "SELL PUT",
            "BEARISH",
            "BEAR",
            "DOWN",
            "AŞAĞI",
            "LOWER",
            "PUT_BIAS",
        )
    ):
        return SIGNAL_PUT

    if any(
        token in text
        for token in (
            "CALL",
            "LONG",
            "BUY CALL",
            "BULLISH",
            "BULL",
            "UP",
            "YUKARI",
            "CALL_BIAS",
        )
    ):
        return SIGNAL_CALL

    return SIGNAL_NEUTRAL


# ============================================================
# TREND NORMALIZATION
# ============================================================

def normalize_trend(
    value: Any,
) -> str:

    text = normalize_text(value)

    if any(
        token in text
        for token in (
            "BEARISH",
            "BEAR",
            "DOWNTREND",
            "SHORT",
            "PUT",
            "AŞAĞI",
        )
    ):
        return TREND_BEARISH

    if any(
        token in text
        for token in (
            "BULLISH",
            "BULL",
            "UPTREND",
            "LONG",
            "CALL",
            "YUKARI",
        )
    ):
        return TREND_BULLISH

    return TREND_NEUTRAL


# ============================================================
# MOTOR DATA EXTRACTION
# ============================================================

def get_trend_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "trend",
            "trend_data",
            default={},
        )
    )


def get_signal_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "signal",
            "signal_data",
            default={},
        )
    )


def get_gap_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "gap",
            "gap_data",
            default={},
        )
    )


def get_sr_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "support_resistance",
            "sr",
            "sr_data",
            default={},
        )
    )


def get_pattern_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "pattern",
            "pattern_data",
            default={},
        )
    )


def get_big_move_warning_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "big_move_warning",
            "big_move_warning_data",
            "big_move",
            default={},
        )
    )


def get_reversal_confirmation_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return safe_dict(
        first_value(
            inputs,
            "reversal_confirmation",
            "reversal_confirmation_data",
            "reversal",
            default={},
        )
    )


# ============================================================
# POSITION DATA
# ============================================================

def get_position_data(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    value = inputs.get(
        "position"
    )

    if isinstance(value, dict):
        return value

    if value is None:
        return {}

    return {
        "position": value
    }


# ============================================================
# GENERIC SCORE / CONFIDENCE
# ============================================================

def extract_engine_score(
    data: Dict[str, Any],
    default: float = 50.0,
) -> float:

    candidates = (
        "final_score",
        "score",
        "strength",
        "signal_strength",
        "confidence",
    )

    for key in candidates:

        if key not in data:
            continue

        value = safe_float(
            data.get(key),
            default,
        )

        return clamp_score(
            value
        )

    return clamp_score(
        default
    )


def extract_confidence(
    data: Dict[str, Any],
) -> float:

    for key in (
        "confidence",
        "final_confidence",
        "signal_confidence",
        "trend_confidence",
    ):

        if key in data:

            return clamp_score(
                data.get(key)
            )

    return 0.0


# ============================================================
# SIGNAL EXTRACTION
# ============================================================

def extract_signal(
    data: Dict[str, Any],
) -> str:

    direct = first_value(
        data,
        "final_signal",
        "signal",
        "direction",
        "bias",
        default=None,
    )

    result = normalize_signal(
        direct
    )

    if result != SIGNAL_NEUTRAL:
        return result

    return SIGNAL_NEUTRAL


# ============================================================
# TREND EXTRACTION
# ============================================================

def extract_trend(
    data: Dict[str, Any],
) -> str:

    direct = first_value(
        data,
        "trend_bias",
        "trend",
        "direction",
        "bias",
        default=None,
    )

    if isinstance(
        direct,
        dict,
    ):

        direct = first_value(
            direct,
            "trend_bias",
            "trend",
            "direction",
            "bias",
            "signal",
            default=None,
        )

    return normalize_trend(
        direct
    )


# ============================================================
# POSITION
# ============================================================

def normalize_position(
    value: Any,
) -> str:

    text = normalize_text(
        value
    )

    if "CALL" in text:
        return SIGNAL_CALL

    if "PUT" in text:
        return SIGNAL_PUT

    return SIGNAL_NEUTRAL


def extract_position(
    inputs: Dict[str, Any],
) -> str:

    position = get_position_data(
        inputs
    )

    if not position:
        return SIGNAL_NEUTRAL

    value = first_value(
        position,
        "type",
        "position",
        "side",
        "option_type",
        default=None,
    )

    return normalize_position(
        value
    )


# ============================================================
# PRICE
# ============================================================

def extract_price(
    inputs: Dict[str, Any],
) -> float:

    return safe_float(
        first_value(
            inputs,
            "price",
            default=0.0,
        ),
        0.0,
    )


# ============================================================
# GAP
# ============================================================

def extract_gap_direction(
    gap: Dict[str, Any],
) -> str:

    value = first_value(
        gap,
        "gap_direction",
        "direction",
        "gap_bias",
        "final_signal",
        "signal",
        default=None,
    )

    text = normalize_text(
        value
    )

    if (
        "GAP_DOWN" in text
        or text == "DOWN"
        or "PUT" in text
        or "BEAR" in text
    ):
        return SIGNAL_PUT

    if (
        "GAP_UP" in text
        or text == "UP"
        or "CALL" in text
        or "BULL" in text
    ):
        return SIGNAL_CALL

    return SIGNAL_NEUTRAL


def calculate_gap_component(
    gap_data: Dict[str, Any],
) -> Dict[str, Any]:

    direction = extract_gap_direction(
        gap_data
    )

    score = extract_engine_score(
        gap_data,
        0.0,
    )

    confidence = extract_confidence(
        gap_data
    )

    gap_fill = bool(
        gap_data.get(
            "gap_fill",
            False,
        )
    )

    if gap_fill:
        score = min(
            score,
            50.0,
        )

    return {
        "direction": direction,
        "score": clamp_score(score),
        "confidence": confidence,
        "weight": WEIGHT_GAP,
        "contribution": directional_score(
            direction,
            score,
            WEIGHT_GAP,
            centered=True,
        ),
        "gap_fill": gap_fill,
        "gap_percent": safe_float(
            gap_data.get(
                "gap_percent",
                0.0,
            ),
            0.0,
        ),
    }


# ============================================================
# S/R
# ============================================================

def extract_sr_event(
    sr: Dict[str, Any],
) -> str:

    value = first_value(
        sr,
        "signal_event",
        "sr_event",
        "event",
        "behavior",
        "signal",
        "action",
        default="NONE",
    )

    return normalize_text(
        value
    )


def sr_direction(
    event: str,
) -> str:

    text = normalize_text(
        event
    )

    if any(
        token in text
        for token in (
            "BREAKOUT_UP",
            "BREAKOUT_R1",
            "BREAKOUT_R2",
            "RESISTANCE_BREAK",
            "SUPPORT_BOUNCE",
            "BOUNCE_SUPPORT",
            "BULL",
            "CALL",
            "YUKARI",
        )
    ):
        return SIGNAL_CALL

    if any(
        token in text
        for token in (
            "BREAKOUT_DOWN",
            "BREAKDOWN",
            "BREAKDOWN_S1",
            "BREAKDOWN_S2",
            "SUPPORT_BREAK",
            "RESISTANCE_REJECTION",
            "REJECT_RESISTANCE",
            "BEAR",
            "PUT",
            "AŞAĞI",
        )
    ):
        return SIGNAL_PUT

    return SIGNAL_NEUTRAL


def extract_level(
    sr: Dict[str, Any],
    *keys: str,
) -> float:

    return safe_float(
        first_value(
            sr,
            *keys,
            default=0.0,
        ),
        0.0,
    )


def analyze_price_location(
    price: float,
    sr: Dict[str, Any],
) -> Dict[str, Any]:

    if price <= 0:

        return {
            "direction": SIGNAL_NEUTRAL,
            "event": "NONE",
            "strength": 0.0,
        }

    r1 = extract_level(
        sr,
        "resistance_1",
        "r1",
        "R1",
    )

    r2 = extract_level(
        sr,
        "resistance_2",
        "r2",
        "R2",
    )

    s1 = extract_level(
        sr,
        "support_1",
        "s1",
        "S1",
        "support",
    )

    s2 = extract_level(
        sr,
        "support_2",
        "s2",
        "S2",
    )

    pivot = extract_level(
        sr,
        "pivot",
        "daily_pivot",
        "PIVOT",
    )

    if r2 > 0 and price > r2:

        return {
            "direction": SIGNAL_CALL,
            "event": "BREAKOUT_R2",
            "strength": 100.0,
        }

    if r1 > 0 and price > r1:

        return {
            "direction": SIGNAL_CALL,
            "event": "BREAKOUT_R1",
            "strength": 85.0,
        }

    if s2 > 0 and price < s2:

        return {
            "direction": SIGNAL_PUT,
            "event": "BREAKDOWN_S2",
            "strength": 100.0,
        }

    if s1 > 0 and price < s1:

        return {
            "direction": SIGNAL_PUT,
            "event": "BREAKDOWN_S1",
            "strength": 85.0,
        }

    if pivot > 0:

        if price > pivot:

            return {
                "direction": SIGNAL_CALL,
                "event": "ABOVE_PIVOT",
                "strength": 55.0,
            }

        if price < pivot:

            return {
                "direction": SIGNAL_PUT,
                "event": "BELOW_PIVOT",
                "strength": 55.0,
            }

    return {
        "direction": SIGNAL_NEUTRAL,
        "event": "INSIDE_RANGE",
        "strength": 0.0,
    }


def calculate_sr_component(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    raw_sr = get_sr_data(
        inputs
    )

    sr = normalize_sr(
        raw_sr
    )

    raw_event = extract_sr_event(
        raw_sr
    )

    if raw_event:

        event = detect_sr_event(
            raw_sr
        )

    else:

        event = "NONE"

    explicit_direction = sr_direction(
        event
    )

    price = extract_price(
        inputs
    )

    if (
        raw_event
        and raw_event not in (
            "",
            "NONE",
        )
    ):

        direction = explicit_direction

        if event in (
            "INSIDE_RANGE",
            "RANGE",
            "NO_EVENT",
        ):
            direction = SIGNAL_NEUTRAL

        strength = extract_engine_score(
            raw_sr,
            0.0,
        )

        if direction != SIGNAL_NEUTRAL:
            strength = max(
                strength,
                85.0,
            )

    else:

        location = analyze_price_location(
            price,
            sr,
        )

        direction = location[
            "direction"
        ]

        event = location[
            "event"
        ]

        strength = location[
            "strength"
        ]

    return {
        "direction": direction,
        "event": event,
        "score": clamp_score(strength),
        "confidence": clamp_score(strength),
        "weight": WEIGHT_SR,
        "contribution": directional_score(
            direction,
            strength,
            WEIGHT_SR,
            centered=False,
        ),
    }


# ============================================================
# PATTERN
# ============================================================

def extract_pattern_direction(
    pattern: Dict[str, Any],
) -> str:

    bias = first_value(
        pattern,
        "bias",
        "pattern_bias",
        default=None,
    )

    direction = normalize_signal(
        bias
    )

    if direction != SIGNAL_NEUTRAL:
        return direction

    signal = first_value(
        pattern,
        "final_signal",
        "signal",
        default=None,
    )

    return normalize_signal(
        signal
    )


def calculate_pattern_component(
    pattern_data: Dict[str, Any],
) -> Dict[str, Any]:

    direction = extract_pattern_direction(
        pattern_data
    )

    score = extract_engine_score(
        pattern_data,
        0.0,
    )

    confidence = extract_confidence(
        pattern_data
    )

    pattern_name = normalize_text(
        first_value(
            pattern_data,
            "pattern",
            "actual_pattern",
            default="NONE",
        )
    )

    return {
        "direction": direction,
        "pattern": pattern_name,
        "score": clamp_score(score),
        "confidence": confidence,
        "weight": WEIGHT_PATTERN,
        "contribution": directional_score(
            direction,
            score,
            WEIGHT_PATTERN,
            centered=True,
        ),
    }


# ============================================================
# TREND
# ============================================================

def calculate_trend_component(
    trend_data: Dict[str, Any],
) -> Dict[str, Any]:

    trend = extract_trend(
        trend_data
    )

    if trend == TREND_BULLISH:

        direction = SIGNAL_CALL

    elif trend == TREND_BEARISH:

        direction = SIGNAL_PUT

    else:

        direction = SIGNAL_NEUTRAL

    score = extract_engine_score(
        trend_data,
        0.0,
    )

    confidence = extract_confidence(
        trend_data
    )

    if "trend_score" in trend_data:

        score = clamp_score(
            trend_data.get(
                "trend_score"
            )
        )

    return {
        "direction": direction,
        "trend": trend,
        "score": clamp_score(score),
        "confidence": confidence,
        "weight": WEIGHT_TREND,
        "contribution": directional_score(
            direction,
            score,
            WEIGHT_TREND,
            centered=True,
        ),
    }


# ============================================================
# SIGNAL
# ============================================================

def calculate_signal_component(
    signal_data: Dict[str, Any],
) -> Dict[str, Any]:

    direction = extract_signal(
        signal_data
    )

    score = extract_engine_score(
        signal_data,
        0.0,
    )

    confidence = extract_confidence(
        signal_data
    )

    score = clamp_score(
        score
    )

    if direction == SIGNAL_NEUTRAL:

        if score <= 35.0:

            direction = SIGNAL_PUT

        elif score >= 65.0:

            direction = SIGNAL_CALL

    return {
        "direction": direction,
        "score": score,
        "confidence": confidence,
        "weight": WEIGHT_SIGNAL,
        "contribution": directional_score(
            direction,
            score,
            WEIGHT_SIGNAL,
            centered=True,
        ),
    }


# ============================================================
# DIRECTIONAL SCORE
# ============================================================

def directional_score(
    direction: str,
    score: float,
    weight: float,
    centered: bool = True,
) -> float:

    if direction == SIGNAL_NEUTRAL:
        return 0.0

    score = clamp_score(
        score
    )

    if centered:

        if direction == SIGNAL_PUT:

            score = 100.0 - score

        elif direction != SIGNAL_CALL:

            return 0.0

    return round(
        weight
        * (
            score
            / 100.0
        ),
        4,
    )


# ============================================================
# COMPONENTS
# ============================================================

def get_components(
    inputs: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:

    return {

        "trend": calculate_trend_component(
            get_trend_data(inputs)
        ),

        "signal": calculate_signal_component(
            get_signal_data(inputs)
        ),

        "gap": calculate_gap_component(
            get_gap_data(inputs)
        ),

        "support_resistance": calculate_sr_component(
            inputs
        ),

        "pattern": calculate_pattern_component(
            get_pattern_data(inputs)
        ),
    }


# ============================================================
# SCORE ENGINE
# ============================================================

def calculate_scores(
    components: Dict[str, Dict[str, Any]],
) -> Dict[str, float]:

    call_score = 0.0
    put_score = 0.0

    active_call_weight = 0.0
    active_put_weight = 0.0

    for component in components.values():

        direction = component.get(
            "direction",
            SIGNAL_NEUTRAL,
        )

        contribution = safe_float(
            component.get(
                "contribution",
                0.0,
            ),
            0.0,
        )

        weight = safe_float(
            component.get(
                "weight",
                0.0,
            ),
            0.0,
        )

        if weight <= 0:
            continue

        if direction == SIGNAL_CALL:

            call_score += contribution
            active_call_weight += weight

        elif direction == SIGNAL_PUT:

            put_score += contribution
            active_put_weight += weight

    normalized_call = (
        call_score
        / TOTAL_WEIGHT
        * 100.0
    )

    normalized_put = (
        put_score
        / TOTAL_WEIGHT
        * 100.0
    )

    return {

        "call": round(
            clamp_score(
                normalized_call
            ),
            2,
        ),

        "put": round(
            clamp_score(
                normalized_put
            ),
            2,
        ),

        "call_active_weight": round(
            active_call_weight,
            2,
        ),

        "put_active_weight": round(
            active_put_weight,
            2,
        ),
    }


# ============================================================
# CONFIRMATIONS
# ============================================================

def calculate_confirmations(
    components: Dict[str, Dict[str, Any]],
) -> Dict[str, int]:

    call_confirmations = 0
    put_confirmations = 0

    for component in components.values():

        direction = component.get(
            "direction",
            SIGNAL_NEUTRAL,
        )

        weight = safe_float(
            component.get(
                "weight",
                0.0,
            ),
            0.0,
        )

        score = safe_float(
            component.get(
                "score",
                0.0,
            ),
            0.0,
        )

        if (
            weight <= 0
            or direction == SIGNAL_NEUTRAL
        ):
            continue

        if direction == SIGNAL_CALL:

            directional_strength = score

        elif direction == SIGNAL_PUT:

            directional_strength = (
                100.0
                - score
            )

        else:

            directional_strength = 0.0

        if directional_strength < 50.0:
            continue

        if direction == SIGNAL_CALL:

            call_confirmations += 1

        elif direction == SIGNAL_PUT:

            put_confirmations += 1

    return {
        "call": call_confirmations,
        "put": put_confirmations,
    }


# ============================================================
# DOMINANT DIRECTION
# ============================================================

def determine_dominant_direction(
    call_score: float,
    put_score: float,
) -> str:

    call_score = safe_float(
        call_score,
        0.0,
    )

    put_score = safe_float(
        put_score,
        0.0,
    )

    difference = abs(
        call_score
        - put_score
    )

    if difference < MIN_SCORE_EDGE:
        return SIGNAL_NEUTRAL

    if call_score > put_score:
        return SIGNAL_CALL

    if put_score > call_score:
        return SIGNAL_PUT

    return SIGNAL_NEUTRAL


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_final_score(
    dominant_direction: str,
    call_score: float,
    put_score: float,
) -> float:

    if dominant_direction == SIGNAL_CALL:

        return round(
            clamp_score(
                call_score
            ),
            2,
        )

    if dominant_direction == SIGNAL_PUT:

        return round(
            clamp_score(
                put_score
            ),
            2,
        )

    return 50.0


# ============================================================
# SOURCE CONFIDENCE
# ============================================================

def calculate_directional_source_confidence(
    components: Dict[str, Dict[str, Any]],
    dominant_direction: str,
) -> float:

    values = []

    for component in components.values():

        if component.get(
            "direction"
        ) != dominant_direction:
            continue

        confidence = safe_float(
            component.get(
                "confidence"
            ),
            -1.0,
        )

        if confidence >= 0:

            values.append(
                clamp_score(
                    confidence
                )
            )

    if not values:
        return 0.0

    return round(
        sum(values)
        / len(values),
        2,
    )


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    dominant_direction: str,
    final_score: float,
    confirmations: int,
    source_confidence: Optional[float] = None,
) -> float:

    if dominant_direction == SIGNAL_NEUTRAL:
        return 0.0

    if source_confidence is None:

        score_component = clamp_score(
            final_score
        )

    else:

        score_component = clamp_score(
            source_confidence
        )

    confirmation_bonus = min(
        confirmations * 5.0,
        15.0,
    )

    confidence = (
        score_component
        + confirmation_bonus
    )

    return round(
        min(
            confidence,
            100.0,
        ),
        2,
    )


# ============================================================
# ENTRY DECISION
# ============================================================

def entry_decision(
    dominant_direction: str,
    final_score: float,
    confirmations: int,
    call_score: float,
    put_score: float,
    confidence: float = 0.0,
) -> str:

    if dominant_direction == SIGNAL_NEUTRAL:
        return ACTION_WAIT

    if confirmations < MIN_CONFIRMATIONS:
        return ACTION_WAIT

    if final_score < MIN_ENTRY_SCORE:
        return ACTION_WAIT

    if confidence < MIN_ENTRY_CONFIDENCE:
        return ACTION_WAIT

    if dominant_direction == SIGNAL_CALL:

        if call_score <= put_score:
            return ACTION_WAIT

        return ACTION_CALL_BUY

    if dominant_direction == SIGNAL_PUT:

        if put_score <= call_score:
            return ACTION_WAIT

        return ACTION_PUT_BUY

    return ACTION_WAIT


# ============================================================
# POSITION EXIT / HOLD
#
# v5.3:
#
# CALL pozisyonu:
#   - PUT yönü 55+ ve 2 confirmation -> CALL KAPAT
#   - SUPPORT_BREAK -> CALL KAPAT
#   - BREAKDOWN -> CALL KAPAT
#
# PUT pozisyonu:
#   - CALL yönü 55+ ve 2 confirmation -> PUT KAPAT
#   - RESISTANCE_BREAK -> PUT KAPAT
#   - BREAKOUT_UP -> PUT KAPAT
# ============================================================

def position_exit_decision(
    position: str,
    dominant_direction: str,
    opposite_score: float,
    own_score: float,
    confirmations: int,
    final_score: float,
    sr_event: str = "NONE",
) -> Optional[str]:

    if position == SIGNAL_NEUTRAL:
        return None

    opposite_score = safe_float(
        opposite_score,
        0.0,
    )

    own_score = safe_float(
        own_score,
        0.0,
    )

    confirmations = int(
        safe_float(
            confirmations,
            0.0,
        )
    )

    final_score = safe_float(
        final_score,
        0.0,
    )

    event = normalize_text(
        sr_event
    )

    # --------------------------------------------------------
    # CALL POZİSYONU
    # --------------------------------------------------------

    if position == SIGNAL_CALL:

        # Güçlü S/R bozulması doğrudan çıkış sinyalidir.
        if event in CALL_EXIT_SR_EVENTS:

            return ACTION_CALL_CLOSE

        # Zıt yön güçlü ise çık.
        if (
            dominant_direction == SIGNAL_PUT
            and opposite_score >= MIN_EXIT_SCORE
            and confirmations >= MIN_EXIT_CONFIRMATIONS
        ):

            return ACTION_CALL_CLOSE

        # Çok güçlü zıt skor.
        if (
            dominant_direction == SIGNAL_PUT
            and opposite_score >= 75.0
            and final_score >= 75.0
        ):

            return ACTION_CALL_CLOSE

        return ACTION_CALL_HOLD

    # --------------------------------------------------------
    # PUT POZİSYONU
    # --------------------------------------------------------

    if position == SIGNAL_PUT:

        # Güçlü S/R bozulması doğrudan çıkış sinyalidir.
        if event in PUT_EXIT_SR_EVENTS:

            return ACTION_PUT_CLOSE

        # Zıt yön güçlü ise çık.
        if (
            dominant_direction == SIGNAL_CALL
            and opposite_score >= MIN_EXIT_SCORE
            and confirmations >= MIN_EXIT_CONFIRMATIONS
        ):

            return ACTION_PUT_CLOSE

        # Çok güçlü zıt skor.
        if (
            dominant_direction == SIGNAL_CALL
            and opposite_score >= 75.0
            and final_score >= 75.0
        ):

            return ACTION_PUT_CLOSE

        return ACTION_PUT_HOLD

    return None



# ============================================================
# CONTROLLED STRUCTURAL ENTRY EXCEPTIONS
# ============================================================

def evaluate_support_bounce_reversal_call(
    sr_event: str,
    pattern_component: Dict[str, Any],
    call_score: float,
    put_score: float,
    call_confirmations: int,
    put_confirmations: int,
    confidence: float,
    gap_component: Dict[str, Any],
    trend_component: Optional[Dict[str, Any]] = None,
    signal_component: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    v5.8.3 controlled SUPPORT_BOUNCE CALL path.

    Amaç:
      - Normal CALL pipeline'ını genel olarak gevşetmemek.
      - Gerçek SUPPORT_BOUNCE yapısında CALL kanıtları yeterliyse
        geciken / tek başına ters pattern etiketinin CALL'ı tamamen
        öldürmesini engellemek.
      - Açık PUT gap yönünü veto olarak korumak.

    Bearish pattern varsa daha güçlü CALL teyidi gerekir.
    """

    event = normalize_text(sr_event)

    if event not in (
        "SUPPORT_BOUNCE",
        "BOUNCE_SUPPORT",
        "REJECT_SUPPORT",
    ):
        return False

    call_score = safe_float(call_score, 0.0)
    put_score = safe_float(put_score, 0.0)
    call_confirmations = int(safe_float(call_confirmations, 0.0))
    put_confirmations = int(safe_float(put_confirmations, 0.0))
    confidence = safe_float(confidence, 0.0)

    confirmation_edge = call_confirmations - put_confirmations
    score_edge = call_score - put_score

    # Support bounce CALL için taban teknik kalite.
    if call_confirmations < SUPPORT_BOUNCE_CALL_MIN_CONFIRMATIONS:
        return False

    if confirmation_edge < SUPPORT_BOUNCE_CALL_MIN_CONFIRMATION_EDGE:
        return False

    if score_edge < SUPPORT_BOUNCE_CALL_MIN_SCORE_EDGE:
        return False

    if confidence < SUPPORT_BOUNCE_CALL_MIN_CONFIDENCE:
        return False

    # Explicit PUT gap direction remains a hard veto.
    gap_direction = gap_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    if gap_direction == SIGNAL_PUT:
        return False

    trend_component = safe_dict(trend_component)
    signal_component = safe_dict(signal_component)

    if trend_component.get("direction", SIGNAL_NEUTRAL) == SIGNAL_PUT:
        return False

    if signal_component.get("direction", SIGNAL_NEUTRAL) == SIGNAL_PUT:
        return False

    pattern_direction = pattern_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    pattern_score = safe_float(
        pattern_component.get(
            "score",
            0.0,
        ),
        0.0,
    )

    # Bullish pattern: normal controlled bounce yolu.
    if pattern_direction == SIGNAL_CALL:
        return pattern_score >= SUPPORT_BOUNCE_MIN_BULLISH_PATTERN_SCORE

    # Neutral pattern: S/R + diğer CALL teyitleri yeterliyse kabul.
    if pattern_direction == SIGNAL_NEUTRAL:
        return True

    # Bearish pattern tek başına CALL'ı veto etmez; fakat ancak
    # güçlü çoğunluk CALL kanıtı varsa geciken pattern kabul edilir.
    if pattern_direction == SIGNAL_PUT:
        return bool(
            call_confirmations
            >= SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_CONFIRMATIONS
            and confirmation_edge
            >= SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_CONFIRMATION_EDGE
            and score_edge
            >= SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_SCORE_EDGE
        )

    return False

def evaluate_support_break_early_put(
    sr_event: str,
    pattern_component: Dict[str, Any],
    call_score: float,
    put_score: float,
    call_confirmations: int,
    put_confirmations: int,
    confidence: float,
    signal_component: Dict[str, Any],
) -> bool:
    """
    Controlled early PUT path for a structural SUPPORT_BREAK.

    This path is intentionally conservative:
    - SUPPORT_BREAK must already exist.
    - PUT confirmations must be meaningful.
    - CALL score may not dominate.
    - Explicit bullish pattern is a veto unless PUT structure
      has enough confirmation.
    """

    event = normalize_text(
        sr_event
    )

    if event not in (
        "SUPPORT_BREAK",
        "BREAKOUT_DOWN",
        "BREAKDOWN",
        "BREAKDOWN_S1",
        "BREAKDOWN_S2",
    ):
        return False

    if put_confirmations < EARLY_BREAK_MIN_PUT_CONFIRMATIONS:
        return False

    call_score = safe_float(
        call_score,
        0.0,
    )

    put_score = safe_float(
        put_score,
        0.0,
    )

    if call_score > EARLY_BREAK_MAX_CALL_SCORE:
        return False

    # Require at least a small PUT scoring advantage OR
    # a weak/neutral signal environment.
    signal_direction = signal_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    if (
        put_score <= call_score
        and signal_direction == SIGNAL_CALL
    ):
        return False

    pattern_direction = pattern_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    if pattern_direction == SIGNAL_CALL:
        # Bullish pattern is allowed only when structural PUT
        # confirmations clearly dominate.
        if (
            put_confirmations
            - call_confirmations
            < 1
        ):
            return False

    # If the normal confidence calculation collapsed to zero
    # because dominant direction became neutral, use the
    # structural component confidences conservatively.
    if confidence < EARLY_BREAK_MIN_CONFIDENCE:

        sr_conf = 0.0

        try:
            sr_conf = 85.0
        except Exception:
            sr_conf = 0.0

        signal_conf = safe_float(
            signal_component.get(
                "confidence",
                0.0,
            ),
            0.0,
        )

        structural_confidence = max(
            sr_conf,
            signal_conf,
        )

        if structural_confidence < EARLY_BREAK_MIN_CONFIDENCE:
            return False

    return True




def extract_decision_timestamp(
    inputs: Dict[str, Any],
) -> Optional[Any]:
    """
    Decision payload içindeki gerçek piyasa zamanını bulur.
    Replay ve live pipeline ile uyumludur.
    """

    data = safe_dict(inputs)

    market = safe_dict(
        first_value(
            data,
            "market_data",
            "market",
            default={},
        )
    )

    value = first_value(
        market,
        "timestamp",
        "last_update",
        default=None,
    )

    if value is None:
        value = first_value(
            data,
            "timestamp",
            default=None,
        )

    return value


def session_hhmm(
    timestamp_value: Any,
) -> str:
    """
    Timestamp'i HH:MM'e çevirir.
    Tanımsız/geçersiz ise boş döner.
    """

    try:
        if timestamp_value is None:
            return ""

        # ISO-like strings: "2026-08-21 11:00:00-04:00"
        if hasattr(timestamp_value, "strftime"):
            return timestamp_value.strftime("%H:%M")

        text_value = str(timestamp_value).strip()

        if "T" in text_value:
            time_part = text_value.split("T", 1)[1]
        elif " " in text_value:
            time_part = text_value.split(" ", 1)[1]
        else:
            time_part = text_value

        if len(time_part) >= 5 and time_part[2] == ":":
            return time_part[:5]

        return ""

    except Exception:
        return ""


def evaluate_controlled_call_recovery(
    sr_event: str,
    trend_component: Dict[str, Any],
    signal_component: Dict[str, Any],
    gap_component: Dict[str, Any],
    pattern_component: Dict[str, Any],
    call_score: float,
    put_score: float,
    call_confirmations: int,
    put_confirmations: int,
    current_hhmm: str = "",
) -> bool:
    """Controlled neutral-trend bullish recovery; normal CALL thresholds are untouched."""
    event = normalize_text(sr_event)
    if event not in RECOVERY_CALL_ALLOWED_SR_EVENTS:
        return False

    # v5.8.10:
    # Controlled recovery is a POST-OPENING mechanism.
    # Before 10:30, opening volatility can briefly mimic a recovery
    # even while the larger move is still strongly bearish.
    current_hhmm = normalize_text(
        current_hhmm,
        "",
    )

    if (
        not current_hhmm
        or current_hhmm < RECOVERY_CALL_SESSION_START
    ):
        return False

    trend_component = safe_dict(trend_component)
    signal_component = safe_dict(signal_component)
    gap_component = safe_dict(gap_component)

    if trend_component.get("direction", SIGNAL_NEUTRAL) != SIGNAL_NEUTRAL:
        return False
    if signal_component.get("direction", SIGNAL_NEUTRAL) != SIGNAL_CALL:
        return False
    if gap_component.get("direction", SIGNAL_NEUTRAL) != SIGNAL_CALL:
        return False

    if safe_float(trend_component.get("score", 0.0), 0.0) < RECOVERY_CALL_MIN_TREND_SCORE:
        return False
    if safe_float(signal_component.get("score", 0.0), 0.0) < RECOVERY_CALL_MIN_SIGNAL_SCORE:
        return False
    if int(safe_float(call_confirmations, 0.0)) < RECOVERY_CALL_MIN_CONFIRMATIONS:
        return False
    if int(safe_float(put_confirmations, 0.0)) > RECOVERY_CALL_MAX_PUT_CONFIRMATIONS:
        return False
    if safe_float(call_score, 0.0) - safe_float(put_score, 0.0) < RECOVERY_CALL_MIN_SCORE_EDGE:
        return False

    return True


def apply_controlled_structural_entry(
    current_action: str,
    sr_event: str,
    pattern_component: Dict[str, Any],
    gap_component: Dict[str, Any],
    signal_component: Dict[str, Any],
    trend_component: Optional[Dict[str, Any]],
    current_hhmm: str,
    call_score: float,
    put_score: float,
    call_confirmations: int,
    put_confirmations: int,
    confidence: float,
) -> str:
    """
    Apply only when normal pipeline ended in BEKLE.

    Priority:
      1) SUPPORT_BOUNCE -> controlled CALL reversal
      2) SUPPORT_BREAK  -> controlled early PUT
    """

    if current_action != ACTION_WAIT:
        return current_action

    if evaluate_support_bounce_reversal_call(
        sr_event=sr_event,
        pattern_component=pattern_component,
        call_score=call_score,
        put_score=put_score,
        call_confirmations=call_confirmations,
        put_confirmations=put_confirmations,
        confidence=confidence,
        gap_component=gap_component,
        trend_component=trend_component,
        signal_component=signal_component,
    ):
        return ACTION_CALL_BUY

    if evaluate_controlled_call_recovery(
        sr_event=sr_event,
        trend_component=trend_component,
        signal_component=signal_component,
        gap_component=gap_component,
        pattern_component=pattern_component,
        call_score=call_score,
        put_score=put_score,
        call_confirmations=call_confirmations,
        put_confirmations=put_confirmations,
        current_hhmm=current_hhmm,
    ):
        return ACTION_CALL_BUY

    if evaluate_support_break_early_put(
        sr_event=sr_event,
        pattern_component=pattern_component,
        call_score=call_score,
        put_score=put_score,
        call_confirmations=call_confirmations,
        put_confirmations=put_confirmations,
        confidence=confidence,
        signal_component=signal_component,
    ):
        return ACTION_PUT_BUY

    return ACTION_WAIT


# ============================================================
# BIG MOVE WARNING GATE
# ============================================================

def extract_big_move_warning(
    data: Dict[str, Any],
) -> Dict[str, Any]:

    warning = get_big_move_warning_data(
        data
    )

    if not warning:

        return {
            "present": False,
            "warning": False,
            "warning_type": "NONE",
            "warning_score": 0.0,
            "filtered_warning": False,
            "risk_level": "LOW",
            "call_veto": False,
            "put_entry_candidate": False,
            "status": "NO_WARNING_DATA",
        }

    warning_type = normalize_text(
        warning.get(
            "warning_type",
            "NONE",
        )
    )

    risk_level = normalize_text(
        warning.get(
            "risk_level",
            "LOW",
        )
    )

    filtered_warning = bool(
        warning.get(
            "filtered_warning",
            False,
        ) is True
        or normalize_text(
            warning.get(
                "filtered_warning",
                False,
            )
        ) in (
            "TRUE",
            "YES",
            "EVET",
            "1",
        )
    )

    call_veto = bool(
        warning.get(
            "call_veto",
            False,
        ) is True
        or normalize_text(
            warning.get(
                "call_veto",
                False,
            )
        ) in (
            "TRUE",
            "YES",
            "EVET",
            "1",
        )
    )

    return {
        "present": True,
        "warning": bool(
            warning.get(
                "warning",
                False,
            )
        ),
        "warning_type": warning_type,
        "warning_score": clamp_score(
            warning.get(
                "warning_score",
                0.0,
            )
        ),
        "filtered_warning": filtered_warning,
        "risk_level": risk_level,
        "call_veto": call_veto,
        "put_entry_candidate": bool(
            warning.get(
                "put_entry_candidate",
                False,
            )
        ),
        "status": normalize_text(
            warning.get(
                "status",
                "UNKNOWN",
            )
        ),
        "reason": warning.get(
            "reason",
            "",
        ),
        "filter_reason": warning.get(
            "filter_reason",
            "",
        ),
    }


def apply_big_move_call_risk_gate(
    action: str,
    big_move_warning: Dict[str, Any],
    sr_event: str,
    pattern_component: Dict[str, Any],
    signal_component: Dict[str, Any],
    trend: str,
    call_score: float,
    put_score: float,
    call_confirmations: int,
    put_confirmations: int,
    confidence: float,
    structural_call_candidate: bool = False,
) -> Dict[str, Any]:
    """
    Big Move Warning kontrollü CALL-risk katmanı.

    Tasarım:
      - Warning tek başına CALL AL'i veto etmez.
      - HIGH: kontrollü skor/güven cezası uygular.
      - CRITICAL: yalnız bearish teknik teyit varsa sert veto yapar.
      - SUPPORT_BOUNCE + bullish pattern gibi kontrollü reversal CALL
        yapıları warning yüzünden otomatik öldürülmez.
      - PUT tarafına dokunmaz ve doğrudan PUT AL üretmez.
    """

    result = {
        "action": action,
        "applied": False,
        "mode": "NONE",
        "hard_veto": False,
        "score_penalty": 0.0,
        "confidence_penalty": 0.0,
        "confirmation_penalty": 0,
        "adjusted_call_score": safe_float(call_score, 0.0),
        "adjusted_confidence": safe_float(confidence, 0.0),
        "adjusted_call_confirmations": int(
            safe_float(call_confirmations, 0.0)
        ),
        "bearish_confirmations": 0,
        "bullish_structural_override": False,
        "reason": "NO_CALL_ENTRY",
    }

    if action != ACTION_CALL_BUY:
        return result

    if not big_move_warning.get("present", False):
        result["reason"] = "NO_WARNING_DATA"
        return result

    if not big_move_warning.get("filtered_warning", False):
        result["reason"] = "WARNING_NOT_FILTERED"
        return result

    if not big_move_warning.get("call_veto", False):
        result["reason"] = "CALL_VETO_FLAG_FALSE"
        return result

    risk_level = normalize_text(
        big_move_warning.get("risk_level", "LOW")
    )

    if risk_level not in ("HIGH", "CRITICAL"):
        result["reason"] = "RISK_BELOW_HIGH"
        return result

    event = normalize_text(sr_event)
    pattern_direction = pattern_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )
    signal_direction = signal_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    bearish_confirmations = 0

    if event in PUT_SR_EVENTS or event in CALL_EXIT_SR_EVENTS:
        bearish_confirmations += 1

    if pattern_direction == SIGNAL_PUT:
        bearish_confirmations += 1

    if signal_direction == SIGNAL_PUT:
        bearish_confirmations += 1

    if normalize_trend(trend) == TREND_BEARISH:
        bearish_confirmations += 1

    bullish_structural_override = bool(
        structural_call_candidate
        or (
            event in (
                "SUPPORT_BOUNCE",
                "BOUNCE_SUPPORT",
                "REJECT_SUPPORT",
            )
            and pattern_direction == SIGNAL_CALL
        )
    )

    result["applied"] = True
    result["bearish_confirmations"] = bearish_confirmations
    result["bullish_structural_override"] = bullish_structural_override

    # --------------------------------------------------------
    # HIGH WARNING
    # --------------------------------------------------------
    if risk_level == "HIGH":
        result["mode"] = "HIGH_PENALTY"
        result["score_penalty"] = BIG_MOVE_HIGH_SCORE_PENALTY
        result["confidence_penalty"] = BIG_MOVE_HIGH_CONFIDENCE_PENALTY

        # Bullish structural reversal path is deliberately protected.
        if bullish_structural_override:
            result["mode"] = "HIGH_BULLISH_OVERRIDE"
            result["reason"] = "VALID_SUPPORT_BOUNCE_BULLISH_PATTERN"
            return result

        confirmation_penalty = 1 if bearish_confirmations >= 1 else 0
        result["confirmation_penalty"] = confirmation_penalty

        adjusted_score = max(
            0.0,
            safe_float(call_score, 0.0)
            - BIG_MOVE_HIGH_SCORE_PENALTY,
        )
        adjusted_confidence = max(
            0.0,
            safe_float(confidence, 0.0)
            - BIG_MOVE_HIGH_CONFIDENCE_PENALTY,
        )
        adjusted_confirmations = max(
            0,
            int(safe_float(call_confirmations, 0.0))
            - confirmation_penalty,
        )

        result["adjusted_call_score"] = round(adjusted_score, 2)
        result["adjusted_confidence"] = round(adjusted_confidence, 2)
        result["adjusted_call_confirmations"] = adjusted_confirmations

        # v5.8.11
        # HIGH warning gerçekten call_veto=True ise, non-structural CALL
        # ceza SONRASINDA da minimum giriş kalitesini taşımak zorundadır.
        #
        # Eski davranışta bearish_confirmations == 0 olduğunda ceza
        # hesaplanıyor fakat minimum skor/güven/teyit tekrar kontrol
        # edilmiyordu. Bu nedenle INSIDE_RANGE recovery CALL,
        # güçlü big-move warning altında zayıf skorla yine CALL AL
        # kalabiliyordu.
        #
        # Gerçek SUPPORT_BOUNCE bullish structural reversal yukarıdaki
        # bullish_structural_override ile zaten korunmaktadır.
        post_penalty_quality_ok = (
            adjusted_score >= MIN_ENTRY_SCORE
            and adjusted_confidence >= MIN_ENTRY_CONFIDENCE
            and adjusted_confirmations >= MIN_CONFIRMATIONS
        )

        if not post_penalty_quality_ok:
            result["action"] = ACTION_WAIT
            result["reason"] = "HIGH_WARNING_WEAK_CALL_AFTER_PENALTY"
            return result

        result["reason"] = "HIGH_WARNING_CALL_STILL_VALID"
        return result

    # --------------------------------------------------------
    # CRITICAL WARNING
    # --------------------------------------------------------
    result["mode"] = "CRITICAL_RISK"
    result["score_penalty"] = BIG_MOVE_CRITICAL_SCORE_PENALTY
    result["confidence_penalty"] = BIG_MOVE_CRITICAL_CONFIDENCE_PENALTY

    # A validated bullish support-bounce structure needs stronger
    # contradictory evidence before it can be vetoed.
    required_bearish = (
        2
        if bullish_structural_override
        else BIG_MOVE_CRITICAL_BEARISH_CONFIRMATIONS_REQUIRED
    )

    if bearish_confirmations >= required_bearish:
        result["action"] = ACTION_WAIT
        result["hard_veto"] = True
        result["mode"] = "CRITICAL_VETO"
        result["reason"] = "CRITICAL_WARNING_WITH_BEARISH_CONFIRMATION"
        return result

    confirmation_penalty = 1 if bearish_confirmations >= 1 else 0
    result["confirmation_penalty"] = confirmation_penalty

    adjusted_score = max(
        0.0,
        safe_float(call_score, 0.0)
        - BIG_MOVE_CRITICAL_SCORE_PENALTY,
    )
    adjusted_confidence = max(
        0.0,
        safe_float(confidence, 0.0)
        - BIG_MOVE_CRITICAL_CONFIDENCE_PENALTY,
    )
    adjusted_confirmations = max(
        0,
        int(safe_float(call_confirmations, 0.0))
        - confirmation_penalty,
    )

    result["adjusted_call_score"] = round(adjusted_score, 2)
    result["adjusted_confidence"] = round(adjusted_confidence, 2)
    result["adjusted_call_confirmations"] = adjusted_confirmations

    # Structural bullish reversal CALL does not use the normal score
    # threshold, therefore it is not invalidated by generic score penalty.
    if bullish_structural_override:
        result["mode"] = "CRITICAL_BULLISH_OVERRIDE"
        result["reason"] = "BULLISH_STRUCTURE_OUTWEIGHS_UNCONFIRMED_WARNING"
        return result

    if (
        adjusted_score < MIN_ENTRY_SCORE
        or adjusted_confidence < MIN_ENTRY_CONFIDENCE
        or adjusted_confirmations < MIN_CONFIRMATIONS
    ):
        result["action"] = ACTION_WAIT
        result["reason"] = "CRITICAL_WARNING_CALL_FAILS_ADJUSTED_GATE"
        return result

    result["reason"] = "CRITICAL_WARNING_CALL_STILL_VALID"
    return result



# ============================================================
# REVERSAL POSITION EXIT GATE
# ============================================================

def apply_reversal_position_exit_gate(
    position: str,
    action: str,
    sr_event: str,
    reversal: Dict[str, Any],
    signal_component: Dict[str, Any] | None = None,
    pattern_component: Dict[str, Any] | None = None,
    call_score: float = 0.0,
    put_score: float = 0.0,
    call_confirmations: int = 0,
    put_confirmations: int = 0,
) -> Dict[str, Any]:
    """
    Açık pozisyon için kontrollü reversal çıkış kapısı.

    v5.8.4 iki bağımsız güvenli çıkış yolu kullanır:

    1) Mevcut yapısal teyit:
       PUT + SUPPORT_BOUNCE + HARD_CALL_PROTECTION -> PUT KAPAT

    2) Çoklu teknik reversal teyidi (simetrik):
       Açık PUT:
         signal=CALL + pattern=CALL
         + CALL confirmation >= 3
         + PUT confirmation == 0
         + CALL score - PUT score >= 15
           -> PUT KAPAT

       Açık CALL için aynı kural ters yönde uygulanır.

    Bu gate aynı bar içinde karşı yöne yeni pozisyon açmaz; yalnız
    mevcut pozisyonu kapatır.
    """

    position = normalize_text(position) or SIGNAL_NEUTRAL
    action = normalize_text(action) or ACTION_WAIT
    event = normalize_text(sr_event) or "NONE"

    signal_component = safe_dict(signal_component)
    pattern_component = safe_dict(pattern_component)

    signal_direction = signal_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )
    pattern_direction = pattern_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    call_score = safe_float(call_score, 0.0)
    put_score = safe_float(put_score, 0.0)
    call_confirmations = int(safe_float(call_confirmations, 0.0))
    put_confirmations = int(safe_float(put_confirmations, 0.0))

    result = {
        "action": action,
        "applied": False,
        "forced_exit": False,
        "reason": "NO_REVERSAL_POSITION_EXIT",
    }

    if position == SIGNAL_NEUTRAL:
        result["reason"] = "NO_OPEN_POSITION"
        return result

    # --------------------------------------------------------
    # v5.8.4 - MULTI-FACTOR TECHNICAL REVERSAL EXIT
    # Reversal Confirmation Engine'in ayrı state'ine bağlı değildir.
    # Signal + Pattern + confirmation majority + score edge gerekir.
    # --------------------------------------------------------

    if position == SIGNAL_PUT:
        bullish_score_edge = call_score - put_score

        strong_bullish_reversal = bool(
            signal_direction == SIGNAL_CALL
            and pattern_direction == SIGNAL_CALL
            and call_confirmations >= REVERSAL_EXIT_MIN_CONFIRMATIONS
            and put_confirmations <= REVERSAL_EXIT_MAX_OPPOSING_CONFIRMATIONS
            and bullish_score_edge >= REVERSAL_EXIT_MIN_SCORE_EDGE
        )

        if strong_bullish_reversal:
            result.update(
                {
                    "action": ACTION_PUT_CLOSE,
                    "applied": True,
                    "forced_exit": True,
                    "reason": "PUT_INVALIDATED_BY_MULTI_FACTOR_BULLISH_REVERSAL",
                }
            )
            return result

    elif position == SIGNAL_CALL:
        bearish_score_edge = put_score - call_score

        strong_bearish_reversal = bool(
            signal_direction == SIGNAL_PUT
            and pattern_direction == SIGNAL_PUT
            and put_confirmations >= REVERSAL_EXIT_MIN_CONFIRMATIONS
            and call_confirmations <= REVERSAL_EXIT_MAX_OPPOSING_CONFIRMATIONS
            and bearish_score_edge >= REVERSAL_EXIT_MIN_SCORE_EDGE
        )

        if strong_bearish_reversal:
            result.update(
                {
                    "action": ACTION_CALL_CLOSE,
                    "applied": True,
                    "forced_exit": True,
                    "reason": "CALL_INVALIDATED_BY_MULTI_FACTOR_BEARISH_REVERSAL",
                }
            )
            return result

    # --------------------------------------------------------
    # Existing structural reversal-confirmation exit
    # --------------------------------------------------------

    if not isinstance(reversal, dict):
        result["reason"] = "NO_REVERSAL_DATA"
        return result

    if not reversal.get("present", False):
        result["reason"] = "NO_REVERSAL_DATA"
        return result

    if not reversal.get("valid", False):
        result["reason"] = "REVERSAL_DATA_INVALID"
        return result

    if position == SIGNAL_PUT:
        bullish_bounce = event in (
            "SUPPORT_BOUNCE",
            "BOUNCE_SUPPORT",
            "REJECT_SUPPORT",
        )

        hard_call_protection = bool(
            reversal.get("hard_call_protection", False)
        )

        if bullish_bounce and hard_call_protection:
            result.update(
                {
                    "action": ACTION_PUT_CLOSE,
                    "applied": True,
                    "forced_exit": True,
                    "reason": "PUT_INVALIDATED_BY_CONFIRMED_BULLISH_SUPPORT_BOUNCE",
                }
            )
            return result

    result["reason"] = "POSITION_REVERSAL_EXIT_NOT_CONFIRMED"
    return result


# ============================================================
# REVERSAL CONFIRMATION GATE
# ============================================================

def extract_reversal_confirmation(
    data: Dict[str, Any],
) -> Dict[str, Any]:

    reversal = get_reversal_confirmation_data(
        data
    )

    if not reversal:

        return {
            "present": False,
            "valid": False,
            "reversal_score": 0.0,
            "reversal_level": "NONE",
            "put_candidate": False,
            "strong_put_candidate": False,
            "put_entry_candidate": False,
            "put_hold_confirmation": False,
            "call_entry_risk": False,
            "hard_call_protection": False,
            "event_role": "NO_EVENT",
            "event_id": 0,
            "event_active": False,
            "event_reset": False,
            "event_reset_reason": "",
            "status": "NO_REVERSAL_DATA",
        }

    return {
        "present": True,
        "valid": bool(
            reversal.get(
                "valid",
                True,
            )
        ),
        "reversal_score": clamp_score(
            reversal.get(
                "reversal_score",
                0.0,
            )
        ),
        "reversal_level": normalize_text(
            reversal.get(
                "reversal_level",
                "NONE",
            )
        ),
        "put_candidate": bool(
            reversal.get(
                "put_candidate",
                False,
            )
        ),
        "strong_put_candidate": bool(
            reversal.get(
                "strong_put_candidate",
                False,
            )
        ),
        "put_entry_candidate": bool(
            reversal.get(
                "put_entry_candidate",
                False,
            )
        ),
        "put_hold_confirmation": bool(
            reversal.get(
                "put_hold_confirmation",
                False,
            )
        ),
        "call_entry_risk": bool(
            reversal.get(
                "call_entry_risk",
                False,
            )
        ),
        "hard_call_protection": bool(
            reversal.get(
                "hard_call_protection",
                False,
            )
        ),
        "late_put_blocked": bool(
            reversal.get(
                "late_put_blocked",
                False,
            )
        ),
        "late_put_reason": reversal.get(
            "late_put_reason",
            "",
        ),
        "late_put_drop_pct": safe_float(
            reversal.get(
                "late_put_drop_pct",
                0.0,
            ),
            0.0,
        ),
        "late_put_distance_from_low_pct": safe_float(
            reversal.get(
                "late_put_distance_from_low_pct",
                999.0,
            ),
            999.0,
        ),
        "event_role": normalize_text(
            reversal.get(
                "event_role",
                "NO_EVENT",
            )
        ),
        "event_id": int(
            safe_float(
                reversal.get(
                    "event_id",
                    0,
                ),
                0.0,
            )
        ),
        "event_active": bool(
            reversal.get(
                "event_active",
                False,
            )
        ),
        "event_reset": bool(
            reversal.get(
                "event_reset",
                False,
            )
        ),
        "event_reset_reason": reversal.get(
            "event_reset_reason",
            "",
        ),
        "status": normalize_text(
            reversal.get(
                "status",
                "UNKNOWN",
            )
        ),
        "positive_reasons": reversal.get(
            "positive_reasons",
            "",
        ),
        "negative_reasons": reversal.get(
            "negative_reasons",
            "",
        ),
    }


def apply_reversal_confirmation_gate(
    action: str,
    reversal: Dict[str, Any],
    protect_structural_call: bool = False,
) -> Dict[str, Any]:
    """
    Reversal Confirmation Engine entegrasyon kapısı.

    Kurallar:
      1) Reversal verisi yoksa mevcut Decision Engine davranışı aynen korunur.
      2) HARD_CALL_PROTECTION tek başına yeni işlem üretmez.
      3) FIRST_SIGNAL + STRONG PUT + PUT_ENTRY_CANDIDATE:
           - BEKLE -> PUT AL
           - CALL AL -> PUT AL
         Böylece doğrulanmış reversal eski bullish trend/signal gecikmesini aşabilir.
      4) SAME_EVENT_CONFIRMATION yeni PUT AL üretmez.
      5) Mevcut pozisyon yönetimine bu gate müdahale etmez.
      6) Oluşan PUT AL daha sonra Options Risk Gate'ten geçer.
    """

    result = {
        "action": action,
        "applied": False,
        "entry_override": False,
        "call_protected": False,
        "same_event_confirmation": False,
        "reason": "NO_REVERSAL_DATA",
    }

    if not reversal.get(
        "present",
        False,
    ):
        return result

    if not reversal.get(
        "valid",
        False,
    ):
        result["reason"] = "REVERSAL_DATA_INVALID"
        return result

    result["applied"] = True

    if reversal.get(
        "hard_call_protection",
        False,
    ):
        result["call_protected"] = True
        result["reason"] = "HARD_CALL_PROTECTION"
        return result

    # --------------------------------------------------------
    # LATE PUT VETO
    # --------------------------------------------------------
    #
    # Reversal Confirmation Engine v1.2:
    # late_put_blocked=True ise yeni PUT girişi engellenir.
    #
    # Kritik fark:
    # Bu veto yalnız reversal override'ını değil,
    # Decision Engine'in normal SUPPORT_BREAK / PUT yolundan
    # gelen PUT AL kararını da engeller.
    #
    # Mevcut açık PUT pozisyon yönetimine müdahale etmez;
    # bu gate yalnız position == NEUTRAL giriş branch'inde
    # çağrılır.
    # --------------------------------------------------------

    if reversal.get(
        "late_put_blocked",
        False,
    ):
        result["action"] = ACTION_WAIT
        result["applied"] = True
        result["entry_override"] = False
        result["reason"] = "LATE_PUT_ENTRY_VETO"
        return result

    event_role = normalize_text(
        reversal.get(
            "event_role",
            "NO_EVENT",
        )
    )

    if (
        event_role == "SAME_EVENT_CONFIRMATION"
        or reversal.get(
            "put_hold_confirmation",
            False,
        )
    ):
        result["same_event_confirmation"] = True
        result["reason"] = "SAME_EVENT_NO_NEW_ENTRY"
        return result

    valid_first_put = bool(
        event_role == "FIRST_SIGNAL"
        and reversal.get(
            "strong_put_candidate",
            False,
        )
        and reversal.get(
            "put_entry_candidate",
            False,
        )
        and not reversal.get(
            "hard_call_protection",
            False,
        )
    )

    if not valid_first_put:
        result["reason"] = "NO_STRONG_FIRST_PUT_SIGNAL"
        return result

    # v5.8.3: Doğrulanmış SUPPORT_BOUNCE CALL yapısı ile aynı barda
    # güçlü PUT reversal çakışırsa PUT'a zorla flip yapma.
    # Çelişkide güvenli sonuç BEKLE'dir.
    if (
        action == ACTION_CALL_BUY
        and protect_structural_call
    ):
        result["action"] = ACTION_WAIT
        result["entry_override"] = False
        result["call_protected"] = True
        result["reason"] = "STRUCTURAL_CALL_PUT_REVERSAL_CONFLICT_WAIT"
        return result

    # Sadece yeni giriş aşamasında BEKLE veya normal CALL girişini
    # doğrulanmış PUT reversal ile değiştir.
    if action in (
        ACTION_WAIT,
        ACTION_CALL_BUY,
    ):
        result["action"] = ACTION_PUT_BUY
        result["entry_override"] = True
        result["reason"] = "CONFIRMED_FIRST_PUT_REVERSAL"
        return result

    # Mevcut normal PUT AL kararına dokunma.
    if action == ACTION_PUT_BUY:
        result["reason"] = "PUT_ENTRY_ALREADY_VALID"
        return result

    result["reason"] = "ACTION_NOT_ENTRY_OVERRIDABLE"
    return result


# ============================================================
# OPTIONS RISK
# ============================================================

def extract_options_risk(
    data: Dict[str, Any],
) -> Dict[str, Any]:

    options_risk = data.get(
        "options_risk",
        None,
    )

    if not isinstance(
        options_risk,
        dict,
    ) or not options_risk:

        return {
            "present": False,
            "risk_level": "UNKNOWN",
            "risk_score": 0.0,
            "trade_allowed": True,
        }

    risk_level = normalize_text(
        options_risk.get(
            "risk_level",
            "UNKNOWN",
        )
    )

    risk_score = clamp_score(
        options_risk.get(
            "risk_score",
            0.0,
        )
    )

    trade_allowed_value = options_risk.get(
        "trade_allowed",
        False,
    )

    trade_allowed = (
        trade_allowed_value is True
        or normalize_text(
            trade_allowed_value
        ) in (
            "TRUE",
            "YES",
            "ALLOWED",
            "ALLOW",
        )
    )

    return {
        "present": True,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "trade_allowed": trade_allowed,
    }


# ============================================================
# OPTIONS RISK GATE
# ============================================================

def apply_options_risk_gate(
    action: str,
    options_risk: Dict[str, Any],
) -> str:

    if action not in (
        ACTION_CALL_BUY,
        ACTION_PUT_BUY,
    ):
        return action

    if not options_risk.get(
        "present",
        False,
    ):
        return action

    if not options_risk.get(
        "trade_allowed",
        True,
    ):
        return ACTION_WAIT

    risk_level = normalize_text(
        options_risk.get(
            "risk_level",
            "UNKNOWN",
        )
    )

    if risk_level in (
        "EXTREME",
        "CRITICAL",
        "BLOCK",
        "BLOCKED",
        "NO_TRADE",
        "FORBIDDEN",
    ):
        return ACTION_WAIT

    return action


# ============================================================
# S/R ENTRY GATE
# ============================================================

def apply_sr_entry_gate(
    action: str,
    dominant_direction: str,
    sr_event: str,
) -> str:

    if action not in (
        ACTION_CALL_BUY,
        ACTION_PUT_BUY,
    ):
        return action

    event = normalize_text(
        sr_event
    )

    if event in (
        "",
        "NONE",
        "INSIDE_RANGE",
        "RANGE",
        "NO_EVENT",
    ):
        return ACTION_WAIT

    if dominant_direction == SIGNAL_CALL:

        if event not in CALL_SR_EVENTS:
            return ACTION_WAIT

        return ACTION_CALL_BUY

    if dominant_direction == SIGNAL_PUT:

        if event not in PUT_SR_EVENTS:
            return ACTION_WAIT

        return ACTION_PUT_BUY

    return ACTION_WAIT


# ============================================================
# TREND + SIGNAL ALIGNMENT GATE
# ============================================================

def apply_direction_alignment_gate(
    action: str,
    trend: str,
    signal: str,
) -> str:

    if action not in (
        ACTION_CALL_BUY,
        ACTION_PUT_BUY,
    ):
        return action

    if action == ACTION_CALL_BUY:

        if trend != TREND_BULLISH:
            return ACTION_WAIT

        if signal != SIGNAL_CALL:
            return ACTION_WAIT

        return action

    if action == ACTION_PUT_BUY:

        if trend != TREND_BEARISH:
            return ACTION_WAIT

        if signal != SIGNAL_PUT:
            return ACTION_WAIT

        return action

    return ACTION_WAIT


# ============================================================
# FINAL DECISION
# ============================================================


def apply_final_call_entry_guard(
    action: str,
    trend_component: Dict[str, Any],
    signal_component: Dict[str, Any],
    gap_component: Dict[str, Any],
    sr_event: str,
    pattern_component: Dict[str, Any],
    call_score: float,
    put_score: float,
    call_confirmations: int,
    put_confirmations: int,
    structural_call_candidate: bool = False,
    recovery_call_candidate: bool = False,
) -> Dict[str, Any]:
    """
    v5.8.9 SINGLE FINAL CALL SAFETY GATE.

    Every NEW CALL AL candidate, regardless of which branch produced it,
    passes here once. Existing CALL KORU/KAPAT lifecycle is untouched.

    Hard veto:
      - Trend direction PUT
      - Signal direction PUT

    Bearish-pattern conflict protection:
      - a bearish pattern blocks a new CALL unless price has a confirmed
        RESISTANCE_BREAK.
      - RESISTANCE_BREAK is retained as the structural exception because
        the breakout can invalidate the earlier bearish pattern.
      - existing CALL lifecycle actions are not affected.
    """
    result = {
        "applied": action == ACTION_CALL_BUY,
        "blocked": False,
        "reason": "NOT_CALL_ENTRY",
        "action": action,
    }

    if action != ACTION_CALL_BUY:
        return result

    trend_component = safe_dict(trend_component)
    signal_component = safe_dict(signal_component)
    pattern_component = safe_dict(pattern_component)

    trend_direction = trend_component.get("direction", SIGNAL_NEUTRAL)
    signal_direction = signal_component.get("direction", SIGNAL_NEUTRAL)
    pattern_direction = pattern_component.get("direction", SIGNAL_NEUTRAL)
    event = normalize_text(sr_event)

    if trend_direction == SIGNAL_PUT:
        result.update(
            blocked=True,
            reason="FINAL_CALL_BLOCK_BEARISH_TREND",
            action=ACTION_WAIT,
        )
        return result

    if signal_direction == SIGNAL_PUT:
        result.update(
            blocked=True,
            reason="FINAL_CALL_BLOCK_PUT_SIGNAL",
            action=ACTION_WAIT,
        )
        return result

    bearish_pattern_conflict = (
        pattern_direction == SIGNAL_PUT
        and event != "RESISTANCE_BREAK"
    )

    if bearish_pattern_conflict:
        result.update(
            blocked=True,
            reason="FINAL_CALL_BLOCK_BEARISH_PATTERN_CONFLICT",
            action=ACTION_WAIT,
        )
        return result

    bearish_range = (
        event in {"INSIDE_RANGE", "RANGE", "NO_EVENT"}
        and pattern_direction == SIGNAL_PUT
    )

    if bearish_range and not (
        bool(structural_call_candidate)
        or bool(recovery_call_candidate)
    ):
        result.update(
            blocked=True,
            reason="FINAL_CALL_BLOCK_BEARISH_RANGE_WITHOUT_VALIDATED_RECOVERY",
            action=ACTION_WAIT,
        )
        return result

    result.update(
        blocked=False,
        reason="FINAL_CALL_ALLOWED",
        action=ACTION_CALL_BUY,
    )
    return result


def decide(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    data = safe_dict(
        inputs
    )

    price = extract_price(
        data
    )

    position = extract_position(
        data
    )

    components = get_components(
        data
    )

    scores = calculate_scores(
        components
    )

    call_score = scores[
        "call"
    ]

    put_score = scores[
        "put"
    ]

    confirmations_dict = calculate_confirmations(
        components
    )

    call_confirmations = confirmations_dict[
        "call"
    ]

    put_confirmations = confirmations_dict[
        "put"
    ]

    dominant_direction = determine_dominant_direction(
        call_score,
        put_score,
    )

    final_score = calculate_final_score(
        dominant_direction,
        call_score,
        put_score,
    )

    source_confidence = (
        calculate_directional_source_confidence(
            components,
            dominant_direction,
        )
    )

    if dominant_direction == SIGNAL_CALL:

        confirmations = call_confirmations

    elif dominant_direction == SIGNAL_PUT:

        confirmations = put_confirmations

    else:

        confirmations = max(
            call_confirmations,
            put_confirmations,
        )

    confidence = calculate_confidence(
        dominant_direction,
        final_score,
        confirmations,
        source_confidence,
    )

    # ========================================================
    # COMPONENT DATA
    # ========================================================

    trend_component = components.get(
        "trend",
        {},
    )

    signal_component = components.get(
        "signal",
        {},
    )

    gap_component = components.get(
        "gap",
        {},
    )

    sr_component = components.get(
        "support_resistance",
        {},
    )

    pattern_component = components.get(
        "pattern",
        {},
    )

    trend = trend_component.get(
        "trend",
        TREND_NEUTRAL,
    )

    signal = signal_component.get(
        "direction",
        SIGNAL_NEUTRAL,
    )

    sr_event = normalize_text(
        sr_component.get(
            "event",
            "NONE",
        )
    )

    pattern = pattern_component.get(
        "pattern",
        "NONE",
    )

    decision_timestamp = extract_decision_timestamp(
        data
    )
    decision_hhmm = session_hhmm(
        decision_timestamp
    )

    # ========================================================
    # POSITION MANAGEMENT
    # ========================================================

    if position == SIGNAL_CALL:

        own_score = call_score
        opposite_score = put_score
        opposite_confirmations = put_confirmations

    elif position == SIGNAL_PUT:

        own_score = put_score
        opposite_score = call_score
        opposite_confirmations = call_confirmations

    else:

        own_score = final_score
        opposite_score = 0.0
        opposite_confirmations = 0

    position_action = position_exit_decision(
        position=position,
        dominant_direction=dominant_direction,
        opposite_score=opposite_score,
        own_score=own_score,
        confirmations=opposite_confirmations,
        final_score=final_score,
        sr_event=sr_event,
    )

    # ========================================================
    # OPTIONS RISK
    # ========================================================

    big_move_warning = extract_big_move_warning(
        data
    )

    reversal_confirmation = extract_reversal_confirmation(
        data
    )

    options_risk = extract_options_risk(
        data
    )

    # ========================================================
    # FINAL ACTION
    # ========================================================

    big_move_gate = {
        "action": position_action if position != SIGNAL_NEUTRAL else ACTION_WAIT,
        "applied": False,
        "mode": "POSITION_MANAGEMENT" if position != SIGNAL_NEUTRAL else "NONE",
        "hard_veto": False,
        "score_penalty": 0.0,
        "confidence_penalty": 0.0,
        "confirmation_penalty": 0,
        "adjusted_call_score": call_score,
        "adjusted_confidence": confidence,
        "adjusted_call_confirmations": call_confirmations,
        "bearish_confirmations": 0,
        "bullish_structural_override": False,
        "reason": "NOT_EVALUATED",
    }

    reversal_gate = {
        "action": position_action if position != SIGNAL_NEUTRAL else ACTION_WAIT,
        "applied": False,
        "entry_override": False,
        "call_protected": False,
        "same_event_confirmation": False,
        "reason": (
            "POSITION_MANAGEMENT"
            if position != SIGNAL_NEUTRAL
            else "NOT_EVALUATED"
        ),
    }

    structural_call_candidate = False

    # v5.8.12
    # Bu değişkenler flat-entry branch'inde hesaplanıyor; ancak return
    # sözlüğünde açık pozisyon branch'inde de raporlanıyor. Bu nedenle
    # position management sırasında UnboundLocalError oluşmaması için
    # güvenli varsayılanlar burada tanımlanır.
    recovery_call_candidate = False

    final_call_entry_guard = {
        "applied": False,
        "blocked": False,
        "reason": (
            "POSITION_MANAGEMENT"
            if position != SIGNAL_NEUTRAL
            else "NOT_EVALUATED"
        ),
        "action": (
            position_action
            if position != SIGNAL_NEUTRAL
            else ACTION_WAIT
        ),
    }

    reversal_position_exit_gate = {
        "action": position_action if position != SIGNAL_NEUTRAL else ACTION_WAIT,
        "applied": False,
        "forced_exit": False,
        "reason": (
            "NOT_EVALUATED"
            if position != SIGNAL_NEUTRAL
            else "NO_OPEN_POSITION"
        ),
    }

    # v5.8.6
    # Bu gate yalnız yeni PUT girişlerinde değerlendirilir; ancak output
    # sözlüğünde her zaman raporlandığı için açık pozisyon branch'inde de
    # tanımlı olmak zorundadır. v5.8.5'te yalnız flat-entry branch'inde
    # tanımlandığından açık pozisyonda UnboundLocalError oluşuyordu.
    weak_range_double_top_gate = {
        "applied": False,
        "blocked": False,
        "reason": (
            "POSITION_MANAGEMENT"
            if position != SIGNAL_NEUTRAL
            else "NOT_APPLICABLE"
        ),
        "action_before": position_action if position != SIGNAL_NEUTRAL else ACTION_WAIT,
        "action_after": position_action if position != SIGNAL_NEUTRAL else ACTION_WAIT,
    }

    if position != SIGNAL_NEUTRAL:

        action = position_action

        reversal_position_exit_gate = (
            apply_reversal_position_exit_gate(
                position=position,
                action=action,
                sr_event=sr_event,
                reversal=reversal_confirmation,
                signal_component=signal_component,
                pattern_component=pattern_component,
                call_score=call_score,
                put_score=put_score,
                call_confirmations=call_confirmations,
                put_confirmations=put_confirmations,
            )
        )

        action = reversal_position_exit_gate.get(
            "action",
            action,
        )

    else:

        # ----------------------------------------------------
        # 1. BASIC ENTRY
        # ----------------------------------------------------

        action = entry_decision(
            dominant_direction=dominant_direction,
            final_score=final_score,
            confirmations=confirmations,
            call_score=call_score,
            put_score=put_score,
            confidence=confidence,
        )

        # ----------------------------------------------------
        # 2. TREND + SIGNAL
        # ----------------------------------------------------

        action = apply_direction_alignment_gate(
            action,
            trend,
            signal,
        )

        # ----------------------------------------------------
        # 3. S/R
        # ----------------------------------------------------

        action = apply_sr_entry_gate(
            action,
            dominant_direction,
            sr_event,
        )

        # ----------------------------------------------------
        # 4. CONTROLLED STRUCTURAL ENTRY
        #
        # Normal pipeline BEKLE'de kaldıysa yalnızca iki
        # yüksek-kaliteli yapısal istisna değerlendirilir:
        #   SUPPORT_BOUNCE -> reversal CALL
        #   SUPPORT_BREAK  -> early PUT
        #
        # RESISTANCE_BREAK CALL için bypass yoktur.
        # ----------------------------------------------------

        structural_call_candidate = evaluate_support_bounce_reversal_call(
            sr_event=sr_event,
            pattern_component=pattern_component,
            call_score=call_score,
            put_score=put_score,
            call_confirmations=call_confirmations,
            put_confirmations=put_confirmations,
            confidence=confidence,
            gap_component=gap_component,
            trend_component=trend_component,
            signal_component=signal_component,
        )

        recovery_call_candidate = evaluate_controlled_call_recovery(
            sr_event=sr_event,
            trend_component=trend_component,
            signal_component=signal_component,
            gap_component=gap_component,
            pattern_component=pattern_component,
            call_score=call_score,
            put_score=put_score,
            call_confirmations=call_confirmations,
            put_confirmations=put_confirmations,
            current_hhmm=decision_hhmm,
        )

        action = apply_controlled_structural_entry(
            current_action=action,
            sr_event=sr_event,
            pattern_component=pattern_component,
            gap_component=gap_component,
            signal_component=signal_component,
            trend_component=trend_component,
            current_hhmm=decision_hhmm,
            call_score=call_score,
            put_score=put_score,
            call_confirmations=call_confirmations,
            put_confirmations=put_confirmations,
            confidence=confidence,
        )

        # ----------------------------------------------------
        # 5. BIG MOVE WARNING - CONTROLLED CALL RISK
        # ----------------------------------------------------

        big_move_gate = apply_big_move_call_risk_gate(
            action=action,
            big_move_warning=big_move_warning,
            sr_event=sr_event,
            pattern_component=pattern_component,
            signal_component=signal_component,
            trend=trend,
            call_score=call_score,
            put_score=put_score,
            call_confirmations=call_confirmations,
            put_confirmations=put_confirmations,
            confidence=confidence,
            structural_call_candidate=structural_call_candidate,
        )

        action = big_move_gate.get(
            "action",
            action,
        )

        # ----------------------------------------------------
        # 6. REVERSAL CONFIRMATION
        #
        # Yalnız FIRST_SIGNAL + güçlü doğrulanmış reversal
        # yeni PUT AL üretebilir. SAME_EVENT_CONFIRMATION
        # yeni giriş açmaz. Yeni PUT kararı bir sonraki adımda
        # Options Risk Gate'ten geçer.
        # ----------------------------------------------------

        reversal_gate = apply_reversal_confirmation_gate(
            action=action,
            reversal=reversal_confirmation,
            protect_structural_call=structural_call_candidate,
        )

        action = reversal_gate.get(
            "action",
            action,
        )


        # ----------------------------------------------------
        # 6.5 WEAK INSIDE-RANGE DOUBLE-TOP PUT FILTER (v5.8.5)
        # ----------------------------------------------------
        #
        # Amaç:
        #   INSIDE_RANGE + DOUBLE_TOP tek başına yeni PUT açtırmasın.
        #   Özellikle trend NEUTRAL ve signal NEUTRAL/CALL iken,
        #   gap CALL yönünü destekliyorsa PUT girişini BEKLE'ye çevir.
        #
        # Korunan yapılar:
        #   - RESISTANCE_REJECTION + DOUBLE_TOP
        #   - SUPPORT_BREAK / BREAKDOWN + güçlü bearish yapı
        # ----------------------------------------------------

        weak_range_double_top_gate.update(
            {
                "applied": False,
                "blocked": False,
                "reason": "NOT_APPLICABLE",
                "action_before": action,
                "action_after": action,
            }
        )

        if action == ACTION_PUT_BUY:
            _event = normalize_text(sr_event)
            _pattern_name = normalize_text(
                pattern_component.get("pattern", "")
            )
            _pattern_dir = pattern_component.get(
                "direction",
                SIGNAL_NEUTRAL,
            )
            _trend_dir = normalize_trend(trend)
            _signal_dir = signal_component.get(
                "direction",
                SIGNAL_NEUTRAL,
            )
            _gap_dir = gap_component.get(
                "direction",
                SIGNAL_NEUTRAL,
            )

            _inside_range = _event in (
                "INSIDE_RANGE",
                "RANGE",
                "NO_EVENT",
                "",
                "NONE",
            )

            _double_top = "DOUBLE_TOP" in _pattern_name

            _weak_bearish_context = (
                _trend_dir == TREND_NEUTRAL
                and _signal_dir in (
                    SIGNAL_NEUTRAL,
                    SIGNAL_CALL,
                )
            )

            _bullish_gap_conflict = (
                _gap_dir == SIGNAL_CALL
            )

            if (
                _inside_range
                and _double_top
                and _weak_bearish_context
                and _bullish_gap_conflict
            ):
                weak_range_double_top_gate.update(
                    {
                        "applied": True,
                        "blocked": True,
                        "reason": (
                            "WEAK_INSIDE_RANGE_DOUBLE_TOP_PUT_BLOCKED_"
                            "NEUTRAL_TREND_SIGNAL_WITH_CALL_GAP"
                        ),
                        "action_after": ACTION_WAIT,
                    }
                )
                action = ACTION_WAIT

        # ----------------------------------------------------
        # 7. OPTIONS RISK
        # ----------------------------------------------------

        final_call_entry_guard = apply_final_call_entry_guard(
            action=action,
            trend_component=trend_component,
            signal_component=signal_component,
            gap_component=gap_component,
            sr_event=sr_event,
            pattern_component=pattern_component,
            call_score=call_score,
            put_score=put_score,
            call_confirmations=call_confirmations,
            put_confirmations=put_confirmations,
            structural_call_candidate=structural_call_candidate,
            recovery_call_candidate=recovery_call_candidate,
        )
        action = final_call_entry_guard.get(
            "action",
            action,
        )

        action = apply_options_risk_gate(
            action,
            options_risk,
        )

    # ========================================================
    # RISK STATUS
    # ========================================================

    risk_blocked = bool(
        options_risk.get(
            "present",
            False,
        )
        and not options_risk.get(
            "trade_allowed",
            True,
        )
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    return {

        "engine": ENGINE_NAME,

        "version": ENGINE_VERSION,

        "price": price,

        "action": action,

        "decision": action,

        "final_action": action,

        "signal": signal,

        "final_signal": dominant_direction,

        "trend": trend,

        "dominant_direction": dominant_direction,

        "call_score": round(
            call_score,
            2,
        ),

        "put_score": round(
            put_score,
            2,
        ),

        "final_score": round(
            final_score,
            2,
        ),

        "confidence": round(
            confidence,
            2,
        ),

        "source_confidence": round(
            source_confidence,
            2,
        ),

        "call_confirmations": call_confirmations,

        "put_confirmations": put_confirmations,

        "confirmations": confirmations,

        "position": position,

        "position_action": position_action,

        "trend_score": safe_float(
            trend_component.get(
                "score",
                0.0,
            ),
            0.0,
        ),

        "signal_score": safe_float(
            signal_component.get(
                "score",
                0.0,
            ),
            0.0,
        ),

        "gap_score": safe_float(
            gap_component.get(
                "score",
                0.0,
            ),
            0.0,
        ),

        "sr_score": safe_float(
            sr_component.get(
                "score",
                0.0,
            ),
            0.0,
        ),

        "pattern_score": safe_float(
            pattern_component.get(
                "score",
                0.0,
            ),
            0.0,
        ),

        "sr_event": sr_event,

        "pattern": pattern,

        "structural_entry_call_candidate": structural_call_candidate,
        "recovery_call_candidate": recovery_call_candidate,
        "decision_timestamp": decision_timestamp,
        "decision_hhmm": decision_hhmm,
        "recovery_session_start": RECOVERY_CALL_SESSION_START,
        "final_call_entry_guard": final_call_entry_guard,
        "final_call_entry_blocked": bool(
            final_call_entry_guard.get("blocked", False)
        ),
        "final_call_entry_reason": final_call_entry_guard.get(
            "reason",
            "UNKNOWN",
        ),

        "structural_entry_put_candidate":
            evaluate_support_break_early_put(
                sr_event=sr_event,
                pattern_component=pattern_component,
                call_score=call_score,
                put_score=put_score,
                call_confirmations=call_confirmations,
                put_confirmations=put_confirmations,
                confidence=confidence,
                signal_component=signal_component,
            ),

        "big_move_warning": {
            "present": big_move_warning.get(
                "present",
                False,
            ),
            "warning": big_move_warning.get(
                "warning",
                False,
            ),
            "warning_type": big_move_warning.get(
                "warning_type",
                "NONE",
            ),
            "warning_score": big_move_warning.get(
                "warning_score",
                0.0,
            ),
            "filtered_warning": big_move_warning.get(
                "filtered_warning",
                False,
            ),
            "risk_level": big_move_warning.get(
                "risk_level",
                "LOW",
            ),
            "call_veto": big_move_warning.get(
                "call_veto",
                False,
            ),
            "put_entry_candidate": big_move_warning.get(
                "put_entry_candidate",
                False,
            ),
            "status": big_move_warning.get(
                "status",
                "NO_WARNING_DATA",
            ),
        },

        "big_move_warning_present": big_move_warning.get(
            "present",
            False,
        ),

        "big_move_warning_score": big_move_warning.get(
            "warning_score",
            0.0,
        ),

        "big_move_warning_risk": big_move_warning.get(
            "risk_level",
            "LOW",
        ),

        "big_move_call_veto": big_move_warning.get(
            "call_veto",
            False,
        ),

        "big_move_gate_applied": big_move_gate.get(
            "applied",
            False,
        ),

        "big_move_gate_mode": big_move_gate.get(
            "mode",
            "NONE",
        ),

        "big_move_gate_hard_veto": big_move_gate.get(
            "hard_veto",
            False,
        ),

        "big_move_gate_bearish_confirmations": big_move_gate.get(
            "bearish_confirmations",
            0,
        ),

        "big_move_gate_bullish_override": big_move_gate.get(
            "bullish_structural_override",
            False,
        ),

        "big_move_gate_adjusted_call_score": big_move_gate.get(
            "adjusted_call_score",
            call_score,
        ),

        "big_move_gate_adjusted_confidence": big_move_gate.get(
            "adjusted_confidence",
            confidence,
        ),

        "big_move_gate_reason": big_move_gate.get(
            "reason",
            "",
        ),

        "reversal_position_exit_gate": {
            "applied": reversal_position_exit_gate.get(
                "applied",
                False,
            ),
            "forced_exit": reversal_position_exit_gate.get(
                "forced_exit",
                False,
            ),
            "reason": reversal_position_exit_gate.get(
                "reason",
                "",
            ),
            "action": reversal_position_exit_gate.get(
                "action",
                action,
            ),
        },

        "reversal_position_exit_applied": (
            reversal_position_exit_gate.get(
                "applied",
                False,
            )
        ),

        "reversal_position_exit_forced": (
            reversal_position_exit_gate.get(
                "forced_exit",
                False,
            )
        ),

        "reversal_position_exit_reason": (
            reversal_position_exit_gate.get(
                "reason",
                "",
            )
        ),

        "reversal_confirmation": {
            "present": reversal_confirmation.get(
                "present",
                False,
            ),
            "valid": reversal_confirmation.get(
                "valid",
                False,
            ),
            "reversal_score": reversal_confirmation.get(
                "reversal_score",
                0.0,
            ),
            "reversal_level": reversal_confirmation.get(
                "reversal_level",
                "NONE",
            ),
            "put_candidate": reversal_confirmation.get(
                "put_candidate",
                False,
            ),
            "strong_put_candidate": reversal_confirmation.get(
                "strong_put_candidate",
                False,
            ),
            "put_entry_candidate": reversal_confirmation.get(
                "put_entry_candidate",
                False,
            ),
            "put_hold_confirmation": reversal_confirmation.get(
                "put_hold_confirmation",
                False,
            ),
            "call_entry_risk": reversal_confirmation.get(
                "call_entry_risk",
                False,
            ),
            "hard_call_protection": reversal_confirmation.get(
                "hard_call_protection",
                False,
            ),
            "late_put_blocked": reversal_confirmation.get(
                "late_put_blocked",
                False,
            ),
            "late_put_reason": reversal_confirmation.get(
                "late_put_reason",
                "",
            ),
            "late_put_drop_pct": reversal_confirmation.get(
                "late_put_drop_pct",
                0.0,
            ),
            "late_put_distance_from_low_pct": reversal_confirmation.get(
                "late_put_distance_from_low_pct",
                999.0,
            ),
            "event_role": reversal_confirmation.get(
                "event_role",
                "NO_EVENT",
            ),
            "event_id": reversal_confirmation.get(
                "event_id",
                0,
            ),
            "event_active": reversal_confirmation.get(
                "event_active",
                False,
            ),
            "event_reset": reversal_confirmation.get(
                "event_reset",
                False,
            ),
            "event_reset_reason": reversal_confirmation.get(
                "event_reset_reason",
                "",
            ),
            "status": reversal_confirmation.get(
                "status",
                "NO_REVERSAL_DATA",
            ),
        },

        "reversal_score": reversal_confirmation.get(
            "reversal_score",
            0.0,
        ),

        "reversal_level": reversal_confirmation.get(
            "reversal_level",
            "NONE",
        ),

        "reversal_put_entry_candidate": reversal_confirmation.get(
            "put_entry_candidate",
            False,
        ),

        "reversal_put_hold_confirmation": reversal_confirmation.get(
            "put_hold_confirmation",
            False,
        ),

        "reversal_hard_call_protection": reversal_confirmation.get(
            "hard_call_protection",
            False,
        ),

        "reversal_event_role": reversal_confirmation.get(
            "event_role",
            "NO_EVENT",
        ),

        "reversal_event_id": reversal_confirmation.get(
            "event_id",
            0,
        ),

        "reversal_gate_applied": reversal_gate.get(
            "applied",
            False,
        ),

        "reversal_gate_entry_override": reversal_gate.get(
            "entry_override",
            False,
        ),

        "reversal_gate_same_event_confirmation": reversal_gate.get(
            "same_event_confirmation",
            False,
        ),

        "reversal_gate_call_protected": reversal_gate.get(
            "call_protected",
            False,
        ),

        "reversal_gate_reason": reversal_gate.get(
            "reason",
            "",
        ),

        "options_risk": {
            "present": options_risk.get(
                "present",
                False,
            ),
            "risk_level": options_risk.get(
                "risk_level",
                "UNKNOWN",
            ),
            "risk_score": options_risk.get(
                "risk_score",
                0.0,
            ),
            "trade_allowed": options_risk.get(
                "trade_allowed",
                True,
            ),
        },

        "risk_level": options_risk.get(
            "risk_level",
            "UNKNOWN",
        ),

        "risk_score": options_risk.get(
            "risk_score",
            0.0,
        ),

        "trade_allowed": options_risk.get(
            "trade_allowed",
            True,
        ),

        "options_risk_blocked": risk_blocked,
        "weak_range_double_top_gate": weak_range_double_top_gate,
        "weak_range_double_top_blocked": weak_range_double_top_gate.get("blocked", False),
        "weak_range_double_top_reason": weak_range_double_top_gate.get("reason", ""),


        "options_risk_status": (
            "BLOCKED"
            if risk_blocked
            else "ALLOWED"
        ),

        "components": components,

        "status": "READY",
    }


# ============================================================
# COMPATIBILITY ENTRY POINTS
# ============================================================

def decision_engine(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return decide(
        inputs
    )


def run_decision_engine(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return decide(
        inputs
    )


def final_decision(
    inputs: Dict[str, Any],
) -> Dict[str, Any]:

    return decide(
        inputs
    )


# ============================================================
# ACTION CLASSIFICATION
# ============================================================

def classify_action(
    action: str,
) -> str:

    mapping = {

        ACTION_CALL_BUY: "ENTRY",
        ACTION_PUT_BUY: "ENTRY",

        ACTION_CALL_CLOSE: "EXIT",
        ACTION_PUT_CLOSE: "EXIT",

        ACTION_CALL_HOLD: "HOLD",
        ACTION_PUT_HOLD: "HOLD",

        ACTION_WAIT: "WAIT",
    }

    return mapping.get(
        normalize_text(
            action
        ),
        "UNKNOWN",
    )


# ============================================================
# ENGINE HEALTH
# ============================================================

def decision_engine_health() -> Dict[str, Any]:

    return {

        "status": "READY",

        "engine": ENGINE_NAME,

        "version": ENGINE_VERSION,

        "commands": [

            ACTION_CALL_BUY,
            ACTION_PUT_BUY,
            ACTION_WAIT,

            ACTION_CALL_HOLD,
            ACTION_PUT_HOLD,

            ACTION_CALL_CLOSE,
            ACTION_PUT_CLOSE,
        ],

        "weights": {

            "trend": WEIGHT_TREND,

            "signal": WEIGHT_SIGNAL,

            "gap": WEIGHT_GAP,

            "support_resistance": WEIGHT_SR,

            "pattern": WEIGHT_PATTERN,

            "total": TOTAL_WEIGHT,
        },

        "thresholds": {

            "min_entry_score": MIN_ENTRY_SCORE,

            "min_entry_confidence": MIN_ENTRY_CONFIDENCE,

            "min_confirmations": MIN_CONFIRMATIONS,

            "min_score_edge": MIN_SCORE_EDGE,

            "min_exit_score": MIN_EXIT_SCORE,

            "min_exit_confirmations": MIN_EXIT_CONFIRMATIONS,
            "reversal_min_confidence": REVERSAL_MIN_CONFIDENCE,
            "reversal_min_call_confirmations": REVERSAL_MIN_CALL_CONFIRMATIONS,
            "reversal_min_confirmation_edge": REVERSAL_MIN_CONFIRMATION_EDGE,
            "reversal_min_score_edge": REVERSAL_MIN_SCORE_EDGE,
            "support_bounce_call_min_confidence": SUPPORT_BOUNCE_CALL_MIN_CONFIDENCE,
            "support_bounce_call_min_confirmations": SUPPORT_BOUNCE_CALL_MIN_CONFIRMATIONS,
            "support_bounce_call_min_confirmation_edge": SUPPORT_BOUNCE_CALL_MIN_CONFIRMATION_EDGE,
            "support_bounce_call_min_score_edge": SUPPORT_BOUNCE_CALL_MIN_SCORE_EDGE,
            "support_bounce_bearish_pattern_min_confirmations": SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_CONFIRMATIONS,
            "support_bounce_bearish_pattern_min_score_edge": SUPPORT_BOUNCE_BEARISH_PATTERN_MIN_SCORE_EDGE,
            "early_break_min_put_confirmations": EARLY_BREAK_MIN_PUT_CONFIRMATIONS,
            "early_break_min_confidence": EARLY_BREAK_MIN_CONFIDENCE,
            "early_break_max_call_score": EARLY_BREAK_MAX_CALL_SCORE,
        },

        "gates": {

            "trend_signal_alignment": True,

            "sr_entry_confirmation": True,

            "inside_range_block": True,

            "options_risk_gate": True,

            "big_move_controlled_call_risk_gate": True,

            "reversal_confirmation_gate": True,

            "late_put_entry_veto": True,

            "late_put_veto_normal_put_entry": True,

            "reversal_position_exit_gate": True,

            "put_exit_on_confirmed_support_bounce": True,

            "no_same_bar_position_flip": True,

            "reversal_first_signal_put_entry": True,

            "reversal_same_event_no_reentry": True,

            "reversal_hard_call_protection": True,

            "sr_position_exit_gate": True,
            "support_bounce_reversal_call": True,
            "support_break_early_put": True,
            "resistance_break_bypass": False,
        },
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    test_data = {

        "price": 720.0,

        "trend": {

            "trend_bias": "BULLISH",

            "trend_score": 72,

            "confidence": 75,
        },

        "signal": {

            "signal": "CALL",

            "score": 74,

            "confidence": 72,
        },

        "gap": {

            "gap_direction": "GAP_UP",

            "score": 65,

            "confidence": 60,

            "gap_fill": False,
        },

        "support_resistance": {

            "event": "SUPPORT_BOUNCE",

            "score": 88,

            "pivot": 718.0,

            "R1": 722.0,

            "R2": 726.0,

            "S1": 715.0,

            "S2": 711.0,
        },

        "pattern": {

            "bias": "CALL",

            "score": 70,

            "confidence": 65,

            "pattern": "TEST_PATTERN",
        },
    }

    result = decision_engine(
        test_data
    )

    print("=" * 70)

    print(
        "QQQ PRO DECISION ENGINE v5.6 TEST"
    )

    print("=" * 70)

    print(
        "ENGINE           :",
        result.get(
            "engine"
        ),
    )

    print(
        "VERSION          :",
        result.get(
            "version"
        ),
    )

    print(
        "ACTION           :",
        result.get(
            "action"
        ),
    )

    print(
        "DIRECTION        :",
        result.get(
            "dominant_direction"
        ),
    )

    print(
        "CALL SCORE       :",
        result.get(
            "call_score"
        ),
    )

    print(
        "PUT SCORE        :",
        result.get(
            "put_score"
        ),
    )

    print(
        "FINAL SCORE      :",
        result.get(
            "final_score"
        ),
    )

    print(
        "CONFIDENCE       :",
        result.get(
            "confidence"
        ),
    )

    print(
        "CONFIRMATIONS    :",
        result.get(
            "confirmations"
        ),
    )

    print(
        "TREND            :",
        result.get(
            "trend"
        ),
    )

    print(
        "SIGNAL           :",
        result.get(
            "signal"
        ),
    )

    print(
        "S/R EVENT        :",
        result.get(
            "sr_event"
        ),
    )

    print(
        "RISK LEVEL       :",
        result.get(
            "risk_level"
        ),
    )

    print(
        "STATUS           :",
        result.get(
            "status"
        ),
    )

    print("=" * 70)
