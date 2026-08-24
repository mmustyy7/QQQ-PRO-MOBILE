# ============================================================
# QQQ PRO
# market_confirmation_engine.py
#
# MARKET / MACRO CONFIRMATION ENGINE
#
# Görev:
# QQQ ana sinyalini piyasa geneli ve makro koşullarla doğrulamak.
#
# ÇIKTILAR:
# BULLISH_CONFIRM
# BEARISH_CONFIRM
# NEUTRAL
# RISK_OFF
# BLOCK
#
# NOT:
# Bu motor emir göndermez.
# CALL / PUT işlemi açmaz.
# Decision Engine'e karar desteği sağlar.
# ============================================================

from typing import Any, Dict, Optional


ENGINE_NAME = "QQQ PRO Market Confirmation Engine"
ENGINE_VERSION = "1.0"


# ============================================================
# CONSTANTS
# ============================================================

SIGNAL_CALL = "CALL"
SIGNAL_PUT = "PUT"
SIGNAL_NEUTRAL = "NEUTRAL"

CONFIRM_BULLISH = "BULLISH_CONFIRM"
CONFIRM_BEARISH = "BEARISH_CONFIRM"
CONFIRM_NEUTRAL = "NEUTRAL"
CONFIRM_RISK_OFF = "RISK_OFF"
CONFIRM_BLOCK = "BLOCK"


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

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:

        if value is None:
            return default

        return int(float(value))

    except (
        TypeError,
        ValueError,
    ):

        return default


def normalize_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    return str(value).strip().upper()


def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# ============================================================
# INPUT NORMALIZATION
# ============================================================

def normalize_market_data(
    data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    if not isinstance(data, dict):
        return {}

    return data


# ============================================================
# COMPONENT EXTRACTION
# ============================================================

def extract_market_direction(
    data: Dict[str, Any],
) -> str:

    market = data.get(
        "market",
        {},
    )

    if not isinstance(market, dict):
        market = {}

    direction = market.get(
        "direction",
        market.get(
            "bias",
            market.get(
                "signal",
                SIGNAL_NEUTRAL,
            ),
        ),
    )

    direction = normalize_text(
        direction
    )

    if direction in (
        "BULLISH",
        "BULL",
        "UP",
        "POSITIVE",
        "RISK_ON",
    ):

        return "BULLISH"

    if direction in (
        "BEARISH",
        "BEAR",
        "DOWN",
        "NEGATIVE",
        "RISK_OFF",
    ):

        return "BEARISH"

    return SIGNAL_NEUTRAL


def extract_spy_direction(
    data: Dict[str, Any],
) -> str:

    spy = data.get(
        "spy",
        {},
    )

    if not isinstance(spy, dict):
        spy = {}

    direction = normalize_text(
        spy.get(
            "direction",
            spy.get(
                "signal",
                SIGNAL_NEUTRAL,
            ),
        )
    )

    if direction in (
        "BULLISH",
        "BULL",
        "UP",
        "CALL",
    ):

        return "BULLISH"

    if direction in (
        "BEARISH",
        "BEAR",
        "DOWN",
        "PUT",
    ):

        return "BEARISH"

    return SIGNAL_NEUTRAL


def extract_ndx_direction(
    data: Dict[str, Any],
) -> str:

    ndx = data.get(
        "ndx",
        data.get(
            "nasdaq",
            {},
        ),
    )

    if not isinstance(ndx, dict):
        ndx = {}

    direction = normalize_text(
        ndx.get(
            "direction",
            ndx.get(
                "signal",
                SIGNAL_NEUTRAL,
            ),
        )
    )

    if direction in (
        "BULLISH",
        "BULL",
        "UP",
        "CALL",
    ):

        return "BULLISH"

    if direction in (
        "BEARISH",
        "BEAR",
        "DOWN",
        "PUT",
    ):

        return "BEARISH"

    return SIGNAL_NEUTRAL


def extract_vix(
    data: Dict[str, Any],
) -> float:

    vix = data.get(
        "vix",
        {},
    )

    if isinstance(vix, dict):

        return safe_float(
            vix.get(
                "value",
                vix.get(
                    "price",
                    vix.get(
                        "last",
                        0.0,
                    ),
                ),
            ),
            0.0,
        )

    return safe_float(
        vix,
        0.0,
    )


def extract_dxy_direction(
    data: Dict[str, Any],
) -> str:

    dxy = data.get(
        "dxy",
        {},
    )

    if not isinstance(dxy, dict):
        dxy = {}

    direction = normalize_text(
        dxy.get(
            "direction",
            dxy.get(
                "signal",
                SIGNAL_NEUTRAL,
            ),
        )
    )

    if direction in (
        "BULLISH",
        "UP",
        "RISING",
    ):

        return "BULLISH"

    if direction in (
        "BEARISH",
        "DOWN",
        "FALLING",
    ):

        return "BEARISH"

    return SIGNAL_NEUTRAL


def extract_treasury_direction(
    data: Dict[str, Any],
) -> str:

    treasury = data.get(
        "us10y",
        data.get(
            "treasury",
            {},
        ),
    )

    if not isinstance(treasury, dict):
        treasury = {}

    direction = normalize_text(
        treasury.get(
            "direction",
            treasury.get(
                "signal",
                SIGNAL_NEUTRAL,
            ),
        )
    )

    if direction in (
        "RISING",
        "UP",
        "BULLISH",
    ):

        return "RISING"

    if direction in (
        "FALLING",
        "DOWN",
        "BEARISH",
    ):

        return "FALLING"

    return SIGNAL_NEUTRAL


def extract_news_bias(
    data: Dict[str, Any],
) -> str:

    news = data.get(
        "news",
        {},
    )

    if not isinstance(news, dict):
        news = {}

    bias = normalize_text(
        news.get(
            "bias",
            news.get(
                "direction",
                news.get(
                    "signal",
                    SIGNAL_NEUTRAL,
                ),
            ),
        )
    )

    if bias in (
        "BULLISH",
        "POSITIVE",
        "RISK_ON",
    ):

        return "BULLISH"

    if bias in (
        "BEARISH",
        "NEGATIVE",
        "RISK_OFF",
    ):

        return "BEARISH"

    return SIGNAL_NEUTRAL


def extract_macro_risk(
    data: Dict[str, Any],
) -> str:

    macro = data.get(
        "macro",
        {},
    )

    if not isinstance(macro, dict):
        macro = {}

    risk = normalize_text(
        macro.get(
            "risk",
            macro.get(
                "risk_level",
                macro.get(
                    "status",
                    "NORMAL",
                ),
            ),
        )
    )

    if risk in (
        "BLOCK",
        "EXTREME",
    ):

        return "BLOCK"

    if risk in (
        "HIGH",
        "RISK_OFF",
        "ELEVATED",
    ):

        return "HIGH"

    return "NORMAL"


# ============================================================
# VIX ANALYSIS
# ============================================================

def analyze_vix(
    vix: float,
) -> Dict[str, Any]:

    vix = safe_float(
        vix,
        0.0,
    )

    if vix <= 0:

        return {
            "status": "UNKNOWN",
            "score": 0,
            "risk": "UNKNOWN",
        }

    if vix < 15:

        return {
            "status": "LOW",
            "score": 20,
            "risk": "LOW",
        }

    if vix < 20:

        return {
            "status": "NORMAL",
            "score": 10,
            "risk": "NORMAL",
        }

    if vix < 25:

        return {
            "status": "ELEVATED",
            "score": -10,
            "risk": "ELEVATED",
        }

    if vix < 30:

        return {
            "status": "HIGH",
            "score": -25,
            "risk": "HIGH",
        }

    return {
        "status": "EXTREME",
        "score": -40,
        "risk": "EXTREME",
    }


# ============================================================
# MARKET CONFIRMATION
# ============================================================

def calculate_market_score(
    market_direction: str,
    spy_direction: str,
    ndx_direction: str,
    dxy_direction: str,
    treasury_direction: str,
    news_bias: str,
) -> int:

    score = 0

    if market_direction == "BULLISH":
        score += 25

    elif market_direction == "BEARISH":
        score -= 25

    if spy_direction == "BULLISH":
        score += 15

    elif spy_direction == "BEARISH":
        score -= 15

    if ndx_direction == "BULLISH":
        score += 20

    elif ndx_direction == "BEARISH":
        score -= 20

    # Strong DXY can pressure growth/technology stocks.
    if dxy_direction == "BULLISH":
        score -= 10

    elif dxy_direction == "BEARISH":
        score += 10

    # Rising US10Y can pressure technology valuations.
    if treasury_direction == "RISING":
        score -= 10

    elif treasury_direction == "FALLING":
        score += 10

    if news_bias == "BULLISH":
        score += 10

    elif news_bias == "BEARISH":
        score -= 10

    return max(
        -100,
        min(
            100,
            score,
        ),
    )


# ============================================================
# SIGNAL CONFIRMATION
# ============================================================

def determine_confirmation(
    market_score: int,
    vix_analysis: Dict[str, Any],
    macro_risk: str,
) -> str:

    vix_risk = normalize_text(
        vix_analysis.get(
            "risk",
            "UNKNOWN",
        )
    )

    if macro_risk == "BLOCK":
        return CONFIRM_BLOCK

    if vix_risk == "EXTREME":
        return CONFIRM_RISK_OFF

    if market_score >= 40:
        return CONFIRM_BULLISH

    if market_score <= -40:
        return CONFIRM_BEARISH

    if vix_risk == "HIGH":
        return CONFIRM_RISK_OFF

    return CONFIRM_NEUTRAL


# ============================================================
# MAIN ENGINE
# ============================================================

def market_confirmation_engine(
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    data = normalize_market_data(
        data
    )

    market_direction = extract_market_direction(
        data
    )

    spy_direction = extract_spy_direction(
        data
    )

    ndx_direction = extract_ndx_direction(
        data
    )

    vix = extract_vix(
        data
    )

    dxy_direction = extract_dxy_direction(
        data
    )

    treasury_direction = extract_treasury_direction(
        data
    )

    news_bias = extract_news_bias(
        data
    )

    macro_risk = extract_macro_risk(
        data
    )

    vix_analysis = analyze_vix(
        vix
    )

    market_score = calculate_market_score(
        market_direction=market_direction,
        spy_direction=spy_direction,
        ndx_direction=ndx_direction,
        dxy_direction=dxy_direction,
        treasury_direction=treasury_direction,
        news_bias=news_bias,
    )

    confirmation = determine_confirmation(
        market_score=market_score,
        vix_analysis=vix_analysis,
        macro_risk=macro_risk,
    )

    confidence = clamp(
        abs(
            float(
                market_score
            )
        ),
        0.0,
        100.0,
    )

    reasons = []

    if market_direction != SIGNAL_NEUTRAL:
        reasons.append(
            "Ana piyasa yönü: "
            + market_direction
        )

    if spy_direction != SIGNAL_NEUTRAL:
        reasons.append(
            "SPY yönü: "
            + spy_direction
        )

    if ndx_direction != SIGNAL_NEUTRAL:
        reasons.append(
            "Nasdaq yönü: "
            + ndx_direction
        )

    if vix > 0:
        reasons.append(
            "VIX: "
            + str(
                round(
                    vix,
                    2,
                )
            )
        )

    if dxy_direction != SIGNAL_NEUTRAL:
        reasons.append(
            "DXY yönü: "
            + dxy_direction
        )

    if treasury_direction != SIGNAL_NEUTRAL:
        reasons.append(
            "US10Y yönü: "
            + treasury_direction
        )

    if news_bias != SIGNAL_NEUTRAL:
        reasons.append(
            "Haber biası: "
            + news_bias
        )

    if macro_risk != "NORMAL":
        reasons.append(
            "Makro risk: "
            + macro_risk
        )

    if not reasons:
        reasons.append(
            "Yeterli market confirmation verisi yok"
        )

    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,

        "confirmation": confirmation,

        "market_confirmation": confirmation,

        "market_score": market_score,

        "confidence": round(
            confidence,
            2,
        ),

        "market_direction": market_direction,

        "spy_direction": spy_direction,

        "ndx_direction": ndx_direction,

        "vix": vix,

        "vix_status": vix_analysis.get(
            "status",
            "UNKNOWN",
        ),

        "vix_risk": vix_analysis.get(
            "risk",
            "UNKNOWN",
        ),

        "dxy_direction": dxy_direction,

        "treasury_direction": treasury_direction,

        "news_bias": news_bias,

        "macro_risk": macro_risk,

        "risk_off": confirmation in (
            CONFIRM_RISK_OFF,
            CONFIRM_BLOCK,
        ),

        "blocked": confirmation == CONFIRM_BLOCK,

        "reasons": reasons,

        "status": "READY",
    }


# ============================================================
# ALIASES
# ============================================================

analyze_market_confirmation = market_confirmation_engine


def default_market_confirmation() -> Dict[str, Any]:

    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "confirmation": CONFIRM_NEUTRAL,
        "market_confirmation": CONFIRM_NEUTRAL,
        "market_score": 0,
        "confidence": 0,
        "market_direction": SIGNAL_NEUTRAL,
        "spy_direction": SIGNAL_NEUTRAL,
        "ndx_direction": SIGNAL_NEUTRAL,
        "vix": 0.0,
        "vix_status": "UNKNOWN",
        "vix_risk": "UNKNOWN",
        "dxy_direction": SIGNAL_NEUTRAL,
        "treasury_direction": SIGNAL_NEUTRAL,
        "news_bias": SIGNAL_NEUTRAL,
        "macro_risk": "NORMAL",
        "risk_off": False,
        "blocked": False,
        "reasons": [
            "Market confirmation verisi yok"
        ],
        "status": "READY",
    }