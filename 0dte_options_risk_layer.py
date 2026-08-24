# ============================================================
# QQQ PRO
# 0dte_options_risk_layer.py
#
# 0DTE OPTIONS RISK LAYER
#
# GÖREV:
# Options Chain verisini kullanarak 0DTE işlem ortamının
# risk seviyesini değerlendirmek.
#
# BU MODÜL:
# - Kontrat seçmez
# - Emir göndermez
# - Broker'a bağlanmaz
# - Pozisyon açmaz
#
# ÇIKIŞ:
# LOW / MEDIUM / HIGH / BLOCK
# CALL / PUT / NEUTRAL / NONE
#
# ============================================================

import math


ENGINE_NAME = "QQQ PRO 0DTE Options Risk Layer"
ENGINE_VERSION = "1.0"


# ============================================================
# SETTINGS
# ============================================================

MIN_OPTION_SCORE = 60

MIN_STRENGTH = 55
STRONG_STRENGTH = 65

MIN_VOLUME = 100
MIN_OPEN_INTEREST = 100

MAX_SPREAD_PCT = 0.15
HIGH_SPREAD_PCT = 0.25

MAX_IV = 1.50
HIGH_IV = 1.00

WALL_DISTANCE_PCT = 0.003

LOW_RISK_SCORE = 70
MEDIUM_RISK_SCORE = 50
HIGH_RISK_SCORE = 30


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def clamp(value, minimum=0, maximum=100):
    value = safe_float(value, minimum)

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


def normalize_direction(direction):
    direction = str(
        direction or "NONE"
    ).upper().strip()

    if direction in ("CALL", "PUT"):
        return direction

    if direction in ("BUY CALL", "CALL BUY"):
        return "CALL"

    if direction in ("BUY PUT", "PUT BUY"):
        return "PUT"

    return "NONE"


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_option_data(option_data):
    result = {
        "valid": False,
        "score": 0,
        "reason": []
    }

    if not isinstance(option_data, dict):
        result["reason"].append(
            "Option verisi dict değil"
        )
        return result

    required_keys = [
        "score",
        "call_strength",
        "put_strength",
        "recommended_side"
    ]

    missing = [
        key
        for key in required_keys
        if key not in option_data
    ]

    if missing:
        result["reason"].append(
            "Eksik alan: " +
            ", ".join(missing)
        )
        return result

    score = safe_float(
        option_data.get("score"),
        0
    )

    call_strength = safe_float(
        option_data.get("call_strength"),
        0
    )

    put_strength = safe_float(
        option_data.get("put_strength"),
        0
    )

    if not 0 <= score <= 100:
        result["reason"].append(
            "Option score geçersiz"
        )
        return result

    if not 0 <= call_strength <= 100:
        result["reason"].append(
            "CALL strength geçersiz"
        )
        return result

    if not 0 <= put_strength <= 100:
        result["reason"].append(
            "PUT strength geçersiz"
        )
        return result

    result["valid"] = True
    result["score"] = 100

    result["reason"].append(
        "Option data geçerli"
    )

    return result


# ============================================================
# OPTION SIDE ANALYSIS
# ============================================================

def analyze_option_side(option_data):
    result = {
        "side": "NONE",
        "strength": 50,
        "opposite_strength": 50,
        "bias_strength": 0,
        "confidence": 0
    }

    if not isinstance(option_data, dict):
        return result

    call_strength = clamp(
        option_data.get(
            "call_strength",
            50
        )
    )

    put_strength = clamp(
        option_data.get(
            "put_strength",
            50
        )
    )

    recommended_side = normalize_direction(
        option_data.get(
            "recommended_side",
            "NONE"
        )
    )

    if recommended_side == "CALL":
        side = "CALL"

    elif recommended_side == "PUT":
        side = "PUT"

    elif call_strength > put_strength + 10:
        side = "CALL"

    elif put_strength > call_strength + 10:
        side = "PUT"

    else:
        side = "NONE"

    if side == "CALL":
        strength = call_strength
        opposite = put_strength

    elif side == "PUT":
        strength = put_strength
        opposite = call_strength

    else:
        strength = max(
            call_strength,
            put_strength
        )
        opposite = min(
            call_strength,
            put_strength
        )

    bias_strength = abs(
        call_strength -
        put_strength
    )

    confidence = clamp(
        50 +
        (
            strength -
            opposite
        ) * 1.5
    )

    result.update({
        "side": side,
        "strength": round(strength, 2),
        "opposite_strength": round(
            opposite,
            2
        ),
        "bias_strength": round(
            bias_strength,
            2
        ),
        "confidence": round(
            confidence,
            2
        )
    })

    return result


# ============================================================
# LIQUIDITY RISK
# ============================================================

def analyze_liquidity(option_data):
    result = {
        "risk": "UNKNOWN",
        "score": 50,
        "call_volume": 0,
        "put_volume": 0,
        "call_oi": 0,
        "put_oi": 0,
        "reason": []
    }

    if not isinstance(option_data, dict):
        result["reason"].append(
            "Option verisi yok"
        )
        return result

    call_volume = safe_float(
        option_data.get(
            "call_volume",
            0
        )
    )

    put_volume = safe_float(
        option_data.get(
            "put_volume",
            0
        )
    )

    call_oi = safe_float(
        option_data.get(
            "call_oi",
            0
        )
    )

    put_oi = safe_float(
        option_data.get(
            "put_oi",
            0
        )
    )

    total_volume = (
        call_volume +
        put_volume
    )

    total_oi = (
        call_oi +
        put_oi
    )

    score = 50

    if total_volume >= 5000:
        score += 25
        result["reason"].append(
            "Toplam opsiyon hacmi güçlü"
        )

    elif total_volume >= 1000:
        score += 15
        result["reason"].append(
            "Opsiyon hacmi yeterli"
        )

    elif total_volume < 200:
        score -= 25
        result["reason"].append(
            "Opsiyon hacmi çok düşük"
        )

    else:
        result["reason"].append(
            "Opsiyon hacmi orta"
        )

    if total_oi >= 5000:
        score += 25
        result["reason"].append(
            "Open Interest güçlü"
        )

    elif total_oi >= 1000:
        score += 15
        result["reason"].append(
            "Open Interest yeterli"
        )

    elif total_oi < 200:
        score -= 20
        result["reason"].append(
            "Open Interest düşük"
        )

    else:
        result["reason"].append(
            "Open Interest orta"
        )

    score = int(
        clamp(
            score
        )
    )

    if score >= 70:
        risk = "LOW"

    elif score >= 50:
        risk = "MEDIUM"

    elif score >= 30:
        risk = "HIGH"

    else:
        risk = "BLOCK"

    result.update({
        "risk": risk,
        "score": score,
        "call_volume": int(
            call_volume
        ),
        "put_volume": int(
            put_volume
        ),
        "call_oi": int(
            call_oi
        ),
        "put_oi": int(
            put_oi
        )
    })

    return result


# ============================================================
# PUT / CALL RATIO RISK
# ============================================================

def analyze_put_call_ratio(option_data):
    result = {
        "risk": "NORMAL",
        "score": 70,
        "pc_volume_ratio": 1.0,
        "pc_oi_ratio": 1.0,
        "reason": []
    }

    if not isinstance(option_data, dict):
        return result

    pc_volume = safe_float(
        option_data.get(
            "pc_volume_ratio",
            1.0
        ),
        1.0
    )

    pc_oi = safe_float(
        option_data.get(
            "pc_oi_ratio",
            1.0
        ),
        1.0
    )

    score = 70

    if pc_volume > 3.0 or pc_volume < 0.30:
        score -= 25
        result["reason"].append(
            "Put/Call hacim oranı aşırı"
        )

    elif pc_volume > 2.0 or pc_volume < 0.50:
        score -= 10
        result["reason"].append(
            "Put/Call hacim oranı yüksek oynaklık gösteriyor"
        )

    else:
        result["reason"].append(
            "Put/Call hacim oranı normal"
        )

    if pc_oi > 3.0 or pc_oi < 0.30:
        score -= 20
        result["reason"].append(
            "Put/Call OI oranı aşırı"
        )

    elif pc_oi > 2.0 or pc_oi < 0.50:
        score -= 10
        result["reason"].append(
            "Put/Call OI oranı dengesiz"
        )

    else:
        result["reason"].append(
            "Put/Call OI oranı normal"
        )

    score = int(
        clamp(
            score
        )
    )

    if score >= 60:
        risk = "NORMAL"

    elif score >= 40:
        risk = "ELEVATED"

    else:
        risk = "HIGH"

    result.update({
        "risk": risk,
        "score": score,
        "pc_volume_ratio": round(
            pc_volume,
            2
        ),
        "pc_oi_ratio": round(
            pc_oi,
            2
        )
    })

    return result


# ============================================================
# IV RISK
# ============================================================

def analyze_iv_risk(option_data):
    result = {
        "risk": "NORMAL",
        "score": 70,
        "iv_status": "NORMAL",
        "reason": []
    }

    if not isinstance(option_data, dict):
        return result

    iv_status = str(
        option_data.get(
            "iv_status",
            "NORMAL"
        )
    ).upper().strip()

    if iv_status in (
        "EXTREME",
        "HIGH"
    ):
        result["score"] = 35
        result["risk"] = "HIGH"
        result["iv_status"] = iv_status
        result["reason"].append(
            "IV riski yüksek"
        )

    elif iv_status in (
        "ELEVATED",
        "ABOVE_NORMAL"
    ):
        result["score"] = 55
        result["risk"] = "ELEVATED"
        result["iv_status"] = iv_status
        result["reason"].append(
            "IV normalin üzerinde"
        )

    else:
        result["score"] = 70
        result["risk"] = "NORMAL"
        result["iv_status"] = "NORMAL"
        result["reason"].append(
            "IV normal"
        )

    return result


# ============================================================
# WALL RISK
# ============================================================

def analyze_wall_risk(
    option_data,
    underlying_price=None
):
    result = {
        "risk": "NORMAL",
        "score": 70,
        "wall_bias": "BETWEEN_WALLS",
        "reason": []
    }

    if not isinstance(option_data, dict):
        return result

    wall_bias = str(
        option_data.get(
            "wall_bias",
            "BETWEEN_WALLS"
        )
    ).upper().strip()

    price = safe_float(
        underlying_price,
        0
    )

    gamma_wall = safe_float(
        option_data.get(
            "gamma_wall"
        ),
        0
    )

    put_wall = safe_float(
        option_data.get(
            "put_wall"
        ),
        0
    )

    score = 70

    if wall_bias == "BETWEEN_WALLS":
        score = 75
        result["reason"].append(
            "Fiyat iki ana wall arasında"
        )

    elif wall_bias == "PRICE_NEAR_CALL_WALL":
        score = 50
        result["reason"].append(
            "Fiyat CALL wall yakınında"
        )

    elif wall_bias == "PRICE_NEAR_PUT_WALL":
        score = 50
        result["reason"].append(
            "Fiyat PUT wall yakınında"
        )

    else:
        score = 60
        result["reason"].append(
            "Wall yapısı belirsiz"
        )

    if price > 0:
        if gamma_wall > 0:
            distance = abs(
                price -
                gamma_wall
            ) / price

            if distance < WALL_DISTANCE_PCT:
                score -= 10
                result["reason"].append(
                    "Fiyat gamma wall'a çok yakın"
                )

        if put_wall > 0:
            distance = abs(
                price -
                put_wall
            ) / price

            if distance < WALL_DISTANCE_PCT:
                score -= 10
                result["reason"].append(
                    "Fiyat put wall'a çok yakın"
                )

    score = int(
        clamp(
            score
        )
    )

    if score >= 65:
        risk = "NORMAL"

    elif score >= 45:
        risk = "ELEVATED"

    else:
        risk = "HIGH"

    result.update({
        "risk": risk,
        "score": score,
        "wall_bias": wall_bias
    })

    return result


# ============================================================
# OPTION SIGNAL ALIGNMENT
# ============================================================

def analyze_signal_alignment(
    market_signal,
    option_data
):
    result = {
        "aligned": False,
        "risk": "HIGH",
        "score": 30,
        "market_side": "NONE",
        "option_side": "NONE",
        "reason": []
    }

    market_side = normalize_direction(
        market_signal
    )

    option_analysis = analyze_option_side(
        option_data
    )

    option_side = option_analysis[
        "side"
    ]

    result["market_side"] = market_side
    result["option_side"] = option_side

    if market_side == "NONE":
        result["score"] = 40
        result["risk"] = "HIGH"
        result["reason"].append(
            "Ana piyasa yönü yok"
        )
        return result

    if option_side == "NONE":
        result["score"] = 35
        result["risk"] = "HIGH"
        result["reason"].append(
            "Option yönü belirsiz"
        )
        return result

    if market_side == option_side:
        result["aligned"] = True
        result["score"] = 90
        result["risk"] = "LOW"
        result["reason"].append(
            "Piyasa sinyali ile option bias aynı yönde"
        )

    else:
        result["aligned"] = False
        result["score"] = 10
        result["risk"] = "BLOCK"
        result["reason"].append(
            "Piyasa sinyali ile option bias çelişiyor"
        )

    return result


# ============================================================
# OPTION SCORE RISK
# ============================================================

def analyze_option_score(option_data):
    result = {
        "score": 50,
        "risk": "HIGH",
        "reason": []
    }

    if not isinstance(option_data, dict):
        result["reason"].append(
            "Option data yok"
        )
        return result

    score = clamp(
        option_data.get(
            "score",
            50
        )
    )

    if score >= 70:
        risk = "LOW"
        reason = "Option score güçlü"

    elif score >= MIN_OPTION_SCORE:
        risk = "MEDIUM"
        reason = "Option score yeterli"

    elif score >= 40:
        risk = "HIGH"
        reason = "Option score zayıf"

    else:
        risk = "BLOCK"
        reason = "Option score çok düşük"

    result.update({
        "score": int(score),
        "risk": risk,
        "reason": [reason]
    })

    return result


# ============================================================
# FINAL RISK SCORE
# ============================================================

def calculate_risk_score(
    validation,
    liquidity,
    put_call,
    iv,
    wall,
    alignment,
    option_score
):
    components = [
        safe_float(
            validation.get(
                "score",
                0
            )
        ),
        safe_float(
            liquidity.get(
                "score",
                0
            )
        ),
        safe_float(
            put_call.get(
                "score",
                0
            )
        ),
        safe_float(
            iv.get(
                "score",
                0
            )
        ),
        safe_float(
            wall.get(
                "score",
                0
            )
        ),
        safe_float(
            alignment.get(
                "score",
                0
            )
        ),
        safe_float(
            option_score.get(
                "score",
                0
            )
        )
    ]

    weights = [
        0.10,
        0.15,
        0.10,
        0.10,
        0.10,
        0.30,
        0.15
    ]

    score = sum(
        value * weight
        for value, weight in zip(
            components,
            weights
        )
    )

    return int(
        round(
            clamp(
                score
            )
        )
    )


# ============================================================
# FINAL RISK CLASSIFICATION
# ============================================================

def classify_risk(
    score,
    alignment,
    validation
):
    if not validation.get(
        "valid",
        False
    ):
        return "BLOCK"

    if alignment.get(
        "risk"
    ) == "BLOCK":
        return "BLOCK"

    if score >= LOW_RISK_SCORE:
        return "LOW"

    if score >= MEDIUM_RISK_SCORE:
        return "MEDIUM"

    if score >= HIGH_RISK_SCORE:
        return "HIGH"

    return "BLOCK"


# ============================================================
# MAIN RISK ENGINE
# ============================================================

def evaluate_0dte_risk(
    option_data,
    market_signal="NONE",
    underlying_price=None
):
    default = {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "risk_level": "BLOCK",
        "risk_score": 0,
        "trade_allowed": False,
        "side": "NONE",
        "option_bias": "NONE",
        "confidence": 0,
        "data_valid": False,
        "signal_aligned": False,
        "liquidity_risk": "UNKNOWN",
        "put_call_risk": "UNKNOWN",
        "iv_risk": "UNKNOWN",
        "wall_risk": "UNKNOWN",
        "option_score_risk": "UNKNOWN",
        "reasons": [
            "Option verisi yok"
        ],
        "status": "BLOCKED"
    }

    validation = validate_option_data(
        option_data
    )

    if not validation["valid"]:
        default["reasons"] = (
            validation["reason"]
        )
        return default

    side_analysis = analyze_option_side(
        option_data
    )

    liquidity = analyze_liquidity(
        option_data
    )

    put_call = analyze_put_call_ratio(
        option_data
    )

    iv = analyze_iv_risk(
        option_data
    )

    wall = analyze_wall_risk(
        option_data,
        underlying_price
    )

    alignment = analyze_signal_alignment(
        market_signal,
        option_data
    )

    option_score = analyze_option_score(
        option_data
    )

    risk_score = calculate_risk_score(
        validation,
        liquidity,
        put_call,
        iv,
        wall,
        alignment,
        option_score
    )

    risk_level = classify_risk(
        risk_score,
        alignment,
        validation
    )

    trade_allowed = (
        risk_level in (
            "LOW",
            "MEDIUM"
        )
        and
        side_analysis["side"] != "NONE"
        and
        alignment["aligned"]
    )

    reasons = []

    reasons.extend(
        validation["reason"]
    )

    reasons.extend(
        liquidity["reason"]
    )

    reasons.extend(
        put_call["reason"]
    )

    reasons.extend(
        iv["reason"]
    )

    reasons.extend(
        wall["reason"]
    )

    reasons.extend(
        alignment["reason"]
    )

    reasons.extend(
        option_score["reason"]
    )

    if trade_allowed:
        status = "READY"

    elif risk_level == "BLOCK":
        status = "BLOCKED"

    else:
        status = "CAUTION"

    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "trade_allowed": trade_allowed,
        "side": side_analysis["side"],
        "option_bias": side_analysis["side"],
        "confidence": side_analysis["confidence"],
        "data_valid": validation["valid"],
        "signal_aligned": alignment["aligned"],
        "liquidity_risk": liquidity["risk"],
        "put_call_risk": put_call["risk"],
        "iv_risk": iv["risk"],
        "wall_risk": wall["risk"],
        "option_score_risk": option_score["risk"],
        "liquidity_score": liquidity["score"],
        "put_call_score": put_call["score"],
        "iv_score": iv["score"],
        "wall_score": wall["score"],
        "alignment_score": alignment["score"],
        "option_score": option_score["score"],
        "wall_bias": wall["wall_bias"],
        "pc_volume_ratio": put_call[
            "pc_volume_ratio"
        ],
        "pc_oi_ratio": put_call[
            "pc_oi_ratio"
        ],
        "reasons": reasons,
        "status": status
    }


# ============================================================
# SIMPLE PUBLIC API
# ============================================================

def analyze_0dte_options_risk(
    option_data,
    market_signal="NONE",
    underlying_price=None
):
    return evaluate_0dte_risk(
        option_data=option_data,
        market_signal=market_signal,
        underlying_price=underlying_price
    )


# ============================================================
# DEFAULT RESPONSE
# ============================================================

def default_risk_response(
    reason="Veri yok"
):
    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "risk_level": "BLOCK",
        "risk_score": 0,
        "trade_allowed": False,
        "side": "NONE",
        "option_bias": "NONE",
        "confidence": 0,
        "data_valid": False,
        "signal_aligned": False,
        "liquidity_risk": "UNKNOWN",
        "put_call_risk": "UNKNOWN",
        "iv_risk": "UNKNOWN",
        "wall_risk": "UNKNOWN",
        "option_score_risk": "UNKNOWN",
        "reasons": [reason],
        "status": "BLOCKED"
    }


# ============================================================
# ARCHITECTURE GUARANTEE
# ============================================================
#
# Bu dosyada:
#
# place_order      YOK
# send_order       YOK
# buy_option       YOK
# sell_option      YOK
# execute_order    YOK
# submit_order     YOK
# broker bağlantısı YOK
#
# AMAÇ:
#
# OPTIONS CHAIN
#       ↓
# 0DTE RISK LAYER
#       ↓
# RISK LEVEL
#       ↓
# DECISION ENGINE
#
# ============================================================