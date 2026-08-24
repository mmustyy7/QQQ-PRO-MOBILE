# ============================================================
# QQQ PRO
# trade_manager.py
#
# TRADE MANAGER 6.3
#
# Görev:
# Decision Engine tarafından üretilen kararı
# açık pozisyon / yeni pozisyon yaşam döngüsüne uygulamak.
#
# KRİTİK KURAL:
# Trade Manager kendi başına CALL / PUT sinyali üretmez.
#
# Karar kaynağı:
#     decision_engine.py
#
# Destek verileri:
#     market_data
#     support_resistance
#     trend
#     signal
#
# Çıkışlar:
#     CALL AL
#     PUT AL
#     BEKLE
#     CALL KORU
#     PUT KORU
#     CALL KAPAT
#     PUT KAPAT
# ============================================================

import math
from datetime import datetime


# ============================================================
# ENGINE INFORMATION
# ============================================================

ENGINE_NAME = "QQQ PRO Trade Manager"
ENGINE_VERSION = "6.4"


# ============================================================
# RISK SETTINGS
# ============================================================

MIN_PRICE = 0.0

# S/R seviyesine çok yakınlık kontrolü
LEVEL_TOLERANCE_PCT = 0.15

# ------------------------------------------------------------
# POSITION PROFIT PROTECTION / EARLY INVALIDATION
# ------------------------------------------------------------
#
# Bu seviyeler QQQ underlying fiyat hareketi üzerinden çalışır.
# Opsiyon primi üzerinden değildir.
#
# Profit protection:
# - Pozisyon önce anlamlı şekilde lehimize gitmeli.
# - Sonra MFE'nin belirli kısmını geri vermeli.
# - Aynı anda karşı yön yapısı oluşmalı.
#
# Early invalidation:
# - Henüz anlamlı MFE oluşmamışken,
# - karşı yapı birkaç ardışık kontrolde devam etmeli,
# - pozisyon girişe göre anlamlı şekilde tersine dönmeli.
#
PROFIT_PROTECTION_MIN_MFE_DOLLARS = 0.80
PROFIT_PROTECTION_MIN_GIVEBACK_DOLLARS = 0.45
PROFIT_PROTECTION_MIN_GIVEBACK_RATIO = 0.35

EARLY_INVALIDATION_MAX_MFE_DOLLARS = 0.50
EARLY_INVALIDATION_MIN_ADVERSE_DOLLARS = 0.50
EARLY_INVALIDATION_MIN_CONFIRMATIONS = 2

# Acil zarar kesme: QQQ underlying girişe karşı bu kadar hareket ederse
# karşı-yapı teyidi beklenmez. 0DTE pozisyonlarda büyük zararın EOD'ye taşınmasını engeller.
HARD_ADVERSE_STOP_DOLLARS = 0.85


# ------------------------------------------------------------
# SAME-DIRECTION RE-ENTRY PROTECTION
# ------------------------------------------------------------
REENTRY_COOLDOWN_MINUTES = 45
REENTRY_REQUIRE_FRESH_EVENT = True

# Aynı directional sequence içinde, cooldown bittikten sonra
# yalnız 1 normal same-direction re-entry kabul edilir.
# Daha sonraki aynı-yön continuation girişleri yeni FIRST_SIGNAL
# reversal olayı olmadan engellenir.
MAX_SAME_DIRECTION_REENTRIES_PER_SESSION = 1

# İlk normal same-direction re-entry için yeni yapısal teyit gerekir.
PUT_REENTRY_FRESH_SR_EVENTS = {
    "SUPPORT_BREAK",
    "RESISTANCE_REJECTION",
}

CALL_REENTRY_FRESH_SR_EVENTS = {
    "RESISTANCE_BREAK",
    "SUPPORT_BOUNCE",
}


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        if isinstance(value, bool):
            return default

        if isinstance(value, (list, tuple)):
            if not value:
                return default
            value = value[-1]

        if hasattr(value, "iloc"):
            try:
                value = value.iloc[-1]
            except Exception:
                return default

        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except Exception:
        return default


def safe_string(value, default=""):
    try:
        if value is None:
            return default

        return str(value).strip()

    except Exception:
        return default


def safe_dict(value):
    if isinstance(value, dict):
        return value

    return {}


# ============================================================
# NORMALIZE POSITION
# ============================================================

def normalize_position(position):
    """
    Açık pozisyonu standart hale getirir.

    Çıkış:
        CALL
        PUT
        NONE
    """

    if isinstance(position, dict):

        raw = (
            position.get("side")
            or position.get("position")
            or position.get("type")
            or position.get("option_type")
            or position.get("signal")
            or ""
        )

    elif isinstance(position, str):

        raw = position

    else:

        return "NONE"

    raw = safe_string(raw).upper()

    if "CALL" in raw:
        return "CALL"

    if "PUT" in raw:
        return "PUT"

    return "NONE"


# ============================================================
# NORMALIZE ACTION
# ============================================================

def normalize_action(action):
    """
    Decision Engine kararını standart hale getirir.
    """

    raw = safe_string(action).upper()

    if raw in (
        "CALL AL",
        "CALL KORU",
        "CALL KAPAT",
        "PUT AL",
        "PUT KORU",
        "PUT KAPAT",
        "BEKLE",
    ):
        return raw

    return "BEKLE"



# ============================================================
# LIFECYCLE / RE-ENTRY HELPERS
# ============================================================

def safe_datetime(value):
    if value is None:
        return None

    try:
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()

        if isinstance(value, datetime):
            return value

        raw = str(value).strip()

        if not raw:
            return None

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        return datetime.fromisoformat(raw)

    except Exception:
        return None


def extract_current_timestamp(data):
    data = safe_dict(data)

    for key in ("timestamp", "current_time"):
        result = safe_datetime(
            data.get(key)
        )
        if result is not None:
            return result

    market = safe_dict(
        data.get("market_data")
    )

    for key in ("timestamp", "last_update"):
        result = safe_datetime(
            market.get(key)
        )
        if result is not None:
            return result

    return None


def extract_reversal_context(decision):
    decision = safe_dict(decision)

    reversal = safe_dict(
        decision.get("reversal_confirmation")
    )

    return {
        "event_role": safe_string(
            reversal.get("event_role", "NO_EVENT"),
            "NO_EVENT",
        ).upper(),
        "event_id": int(
            safe_float(
                reversal.get("event_id", 0),
                0.0,
            )
        ),
        "put_entry_candidate": bool(
            reversal.get(
                "put_entry_candidate",
                False,
            )
        ),
        "reversal_score": safe_float(
            reversal.get(
                "reversal_score",
                decision.get(
                    "reversal_score",
                    0.0,
                ),
            ),
            0.0,
        ),
    }


def normalize_lifecycle_state(value):
    state = safe_dict(value)

    return {
        "last_exit_side": normalize_position(
            state.get(
                "last_exit_side",
                "NONE",
            )
        ),
        "last_exit_time": state.get(
            "last_exit_time"
        ),
        "last_exit_price": safe_float(
            state.get(
                "last_exit_price",
                0.0,
            ),
            0.0,
        ),
        "last_exit_status": safe_string(
            state.get(
                "last_exit_status",
                "",
            ),
            "",
        ).upper(),
        "last_exit_reason": safe_string(
            state.get(
                "last_exit_reason",
                "",
            ),
            "",
        ),
        "last_exit_sr_event": safe_string(
            state.get(
                "last_exit_sr_event",
                "NONE",
            ),
            "NONE",
        ).upper(),
        "last_exit_reversal_event_id": int(
            safe_float(
                state.get(
                    "last_exit_reversal_event_id",
                    0,
                ),
                0.0,
            )
        ),
        "last_exit_reversal_event_role": safe_string(
            state.get(
                "last_exit_reversal_event_role",
                "NO_EVENT",
            ),
            "NO_EVENT",
        ).upper(),

        "same_direction_reentry_count": int(
            safe_float(
                state.get(
                    "same_direction_reentry_count",
                    0,
                ),
                0.0,
            )
        ),

        "last_entry_side": normalize_position(
            state.get(
                "last_entry_side",
                "NONE",
            )
        ),

        "last_entry_time": state.get(
            "last_entry_time"
        ),

        "last_entry_price": safe_float(
            state.get(
                "last_entry_price",
                0.0,
            ),
            0.0,
        ),
    }


def calculate_elapsed_minutes(start_time, end_time):
    start_dt = safe_datetime(start_time)
    end_dt = safe_datetime(end_time)

    if (
        start_dt is None
        or end_dt is None
    ):
        return None

    try:
        if (
            start_dt.tzinfo is None
            and end_dt.tzinfo is not None
        ):
            end_dt = end_dt.replace(
                tzinfo=None
            )

        elif (
            start_dt.tzinfo is not None
            and end_dt.tzinfo is None
        ):
            start_dt = start_dt.replace(
                tzinfo=None
            )

        return (
            end_dt - start_dt
        ).total_seconds() / 60.0

    except Exception:
        return None


def evaluate_same_direction_reentry(
    requested_action,
    current_price,
    current_timestamp,
    decision,
    lifecycle_state,
):
    """
    Trade Manager v6.3 aynı-yön yeniden giriş kapısı.

    Katman 1:
    - İlk 45 dakika: normal same-direction re-entry blok.
    - Yeni bağımsız FIRST_SIGNAL reversal olayı istisna.

    Katman 2:
    - 45 dakika geçtikten sonra ilk normal re-entry için
      yönle uyumlu yeni S/R yapısal olayı gerekir.
    - Aynı directional sequence içinde ikinci normal re-entry
      yeni FIRST_SIGNAL reversal olmadan bloklanır.

    Amaç:
    - Kısa süreli churn'ü kesmek.
    - Aynı gün aynı hareketi tekrar tekrar kovalamayı kesmek.
    - Gerçek yeni reversal olaylarını öldürmemek.
    """

    action = normalize_action(
        requested_action
    )

    side = (
        "CALL"
        if action == "CALL AL"
        else "PUT"
        if action == "PUT AL"
        else "NONE"
    )

    state = normalize_lifecycle_state(
        lifecycle_state
    )

    current_sr_event = safe_string(
        safe_dict(decision).get(
            "sr_event",
            "NONE",
        ),
        "NONE",
    ).upper()

    current_reentry_count = int(
        state.get(
            "same_direction_reentry_count",
            0,
        )
    )

    result = {
        "applied": False,
        "blocked": False,
        "side": side,
        "reason": "",
        "elapsed_minutes": None,
        "fresh_event": False,
        "fresh_structure": False,
        "same_direction_reentry_count":
            current_reentry_count,
        "last_exit_side": state.get(
            "last_exit_side",
            "NONE",
        ),
        "last_exit_status": state.get(
            "last_exit_status",
            "",
        ),
        "last_exit_price": state.get(
            "last_exit_price",
            0.0,
        ),
        "last_exit_sr_event": state.get(
            "last_exit_sr_event",
            "NONE",
        ),
        "current_sr_event": current_sr_event,
    }

    if side == "NONE":
        result["reason"] = "NOT_ENTRY_ACTION"
        return result

    last_side = state.get(
        "last_exit_side",
        "NONE",
    )

    if (
        last_side == "NONE"
        or last_side != side
    ):
        result["reason"] = (
            "NO_SAME_DIRECTION_EXIT_HISTORY"
        )
        return result

    last_exit_dt = safe_datetime(
        state.get("last_exit_time")
    )

    current_dt = safe_datetime(
        current_timestamp
    )

    if (
        last_exit_dt is None
        or current_dt is None
    ):
        result["reason"] = "TIMESTAMP_UNAVAILABLE"
        return result

    if (
        last_exit_dt.date()
        != current_dt.date()
    ):
        result["reason"] = "NEW_SESSION"
        return result

    elapsed = calculate_elapsed_minutes(
        last_exit_dt,
        current_dt,
    )

    result["elapsed_minutes"] = elapsed

    if (
        elapsed is None
        or elapsed < 0
    ):
        result["reason"] = (
            "ELAPSED_TIME_UNAVAILABLE"
        )
        return result

    reversal = extract_reversal_context(
        decision
    )

    previous_event_id = int(
        state.get(
            "last_exit_reversal_event_id",
            0,
        )
    )

    fresh_put_event = bool(
        side == "PUT"
        and reversal.get("event_role")
        == "FIRST_SIGNAL"
        and reversal.get(
            "put_entry_candidate"
        )
        and int(
            reversal.get("event_id", 0)
        ) > 0
        and int(
            reversal.get("event_id", 0)
        ) != previous_event_id
    )

    # CALL için mevcut reversal motoru doğrudan CALL candidate
    # üretmediğinden fresh-event istisnası yalnız PUT tarafında.
    fresh_reversal_event = fresh_put_event

    result["fresh_event"] = (
        fresh_reversal_event
    )

    if fresh_reversal_event:
        result["reason"] = (
            "FRESH_REVERSAL_EVENT"
        )
        return result

    # --------------------------------------------------------
    # LAYER 1 - SHORT COOLDOWN
    # --------------------------------------------------------
    if elapsed < REENTRY_COOLDOWN_MINUTES:
        result["applied"] = True
        result["blocked"] = True
        result["reason"] = (
            "SAME_DIRECTION_REENTRY_COOLDOWN"
        )
        return result

    # --------------------------------------------------------
    # LAYER 2A - STRUCTURE REQUIREMENT
    # --------------------------------------------------------
    if side == "PUT":
        fresh_structure = (
            current_sr_event
            in PUT_REENTRY_FRESH_SR_EVENTS
        )
    else:
        fresh_structure = (
            current_sr_event
            in CALL_REENTRY_FRESH_SR_EVENTS
        )

    result["fresh_structure"] = (
        fresh_structure
    )

    if not fresh_structure:
        result["applied"] = True
        result["blocked"] = True
        result["reason"] = (
            "SAME_DIRECTION_REENTRY_NO_FRESH_STRUCTURE"
        )
        return result

    # --------------------------------------------------------
    # LAYER 2B - CONTINUATION RE-ENTRY LIMIT
    # --------------------------------------------------------
    if (
        current_reentry_count
        >= MAX_SAME_DIRECTION_REENTRIES_PER_SESSION
    ):
        result["applied"] = True
        result["blocked"] = True
        result["reason"] = (
            "SAME_DIRECTION_CONTINUATION_REENTRY_LIMIT"
        )
        return result

    result["reason"] = (
        "FRESH_STRUCTURE_REENTRY_ALLOWED"
    )

    return result



def build_entry_lifecycle_state(
    previous_state,
    side,
    current_price,
    current_timestamp,
):
    """
    Gerçekleşen entry sonrası directional re-entry sayacını günceller.

    - İlk entry / yeni gün / karşı yön entry -> sayaç 0
    - Aynı gün, son çıkışla aynı yön entry -> sayaç +1
    """

    state = normalize_lifecycle_state(
        previous_state
    )

    side = normalize_position(
        side
    )

    if side not in ("CALL", "PUT"):
        return state

    current_dt = safe_datetime(
        current_timestamp
    )

    last_exit_dt = safe_datetime(
        state.get(
            "last_exit_time"
        )
    )

    last_exit_side = state.get(
        "last_exit_side",
        "NONE",
    )

    same_session = bool(
        current_dt is not None
        and last_exit_dt is not None
        and current_dt.date()
        == last_exit_dt.date()
    )

    if (
        same_session
        and last_exit_side == side
    ):
        new_count = int(
            state.get(
                "same_direction_reentry_count",
                0,
            )
        ) + 1
    else:
        new_count = 0

    state.update(
        {
            "same_direction_reentry_count":
                new_count,
            "last_entry_side": side,
            "last_entry_time": (
                current_timestamp.isoformat()
                if isinstance(
                    current_timestamp,
                    datetime,
                )
                else current_timestamp
            ),
            "last_entry_price": safe_float(
                current_price,
                0.0,
            ),
        }
    )

    return state


def build_exit_lifecycle_state(
    previous_state,
    side,
    current_price,
    current_timestamp,
    decision,
    lifecycle,
    protection,
):
    state = normalize_lifecycle_state(
        previous_state
    )

    side = normalize_position(
        side
    )

    if side not in ("CALL", "PUT"):
        return state

    reversal = extract_reversal_context(
        decision
    )

    status = safe_string(
        protection.get("status", "")
        if protection.get("applied")
        else lifecycle.get("status", ""),
        "",
    ).upper()

    reason = safe_string(
        protection.get("reason", "")
        if protection.get("applied")
        else lifecycle.get("advice", ""),
        "",
    )

    state.update(
        {
            "last_exit_side": side,
            "last_exit_time": (
                current_timestamp.isoformat()
                if isinstance(
                    current_timestamp,
                    datetime,
                )
                else current_timestamp
            ),
            "last_exit_price": safe_float(
                current_price,
                0.0,
            ),
            "last_exit_status": status,
            "last_exit_reason": reason,
            "last_exit_sr_event": safe_string(
                decision.get(
                    "sr_event",
                    "NONE",
                ),
                "NONE",
            ).upper(),
            "last_exit_reversal_event_id":
                reversal.get("event_id", 0),
            "last_exit_reversal_event_role":
                reversal.get(
                    "event_role",
                    "NO_EVENT",
                ),
        }
    )

    return state

# ============================================================
# NORMALIZE S/R
# ============================================================

def normalize_sr(sr):
    """
    Support / Resistance verilerini standart hale getirir.
    """

    sr = safe_dict(sr)

    support_1 = (
        sr.get("support_1")
        if sr.get("support_1") is not None
        else sr.get("support")
    )

    support_2 = sr.get("support_2")

    resistance_1 = (
        sr.get("resistance_1")
        if sr.get("resistance_1") is not None
        else sr.get("resistance")
    )

    resistance_2 = sr.get("resistance_2")

    pivot = sr.get("pivot")

    return {
        "pivot": safe_float(pivot, 0.0),
        "support_1": safe_float(support_1, 0.0),
        "support_2": safe_float(support_2, 0.0),
        "resistance_1": safe_float(resistance_1, 0.0),
        "resistance_2": safe_float(resistance_2, 0.0),
        "event": safe_string(
            sr.get("event", "")
        ).upper(),
        "signal": safe_string(
            sr.get("signal", "")
        ).upper(),
        "behavior": safe_string(
            sr.get("behavior", "")
        ).upper(),
    }


# ============================================================
# LEVEL DISTANCE
# ============================================================

def level_distance_percent(price, level):

    price = safe_float(price, 0.0)
    level = safe_float(level, 0.0)

    if price <= 0 or level <= 0:
        return None

    return abs(price - level) / price * 100.0


# ============================================================
# LEVEL STATUS
# ============================================================

def get_level_status(price, level):
    """
    Fiyatın seviyeye göre konumunu belirler.

    BELOW
    AT
    ABOVE
    UNKNOWN
    """

    price = safe_float(price, 0.0)
    level = safe_float(level, 0.0)

    if price <= 0 or level <= 0:
        return "UNKNOWN"

    distance = level_distance_percent(
        price,
        level
    )

    if (
        distance is not None
        and distance <= LEVEL_TOLERANCE_PCT
    ):
        return "AT"

    if price < level:
        return "BELOW"

    return "ABOVE"


# ============================================================
# POSITION LEVEL MONITOR
# ============================================================

def monitor_position_levels(
    current_price,
    position_type,
    support_1,
    resistance_1,
    support_2,
    resistance_2,
):
    """
    Açık pozisyonun S/R seviyelerine göre durumunu izler.

    Bu fonksiyon karar üretmez.
    Yalnızca mevcut durum hakkında bilgi verir.
    """

    price = safe_float(
        current_price,
        0.0
    )

    position = normalize_position(
        position_type
    )

    s1 = safe_float(
        support_1,
        0.0
    )

    s2 = safe_float(
        support_2,
        0.0
    )

    r1 = safe_float(
        resistance_1,
        0.0
    )

    r2 = safe_float(
        resistance_2,
        0.0
    )

    result = {
        "position": position,
        "price": price,
        "support_1": s1,
        "support_2": s2,
        "resistance_1": r1,
        "resistance_2": r2,
        "status": "UNKNOWN",
        "target_reached": False,
        "risk_level": "NORMAL",
    }

    if price <= MIN_PRICE:
        result["status"] = "INVALID_PRICE"
        result["risk_level"] = "HIGH"
        return result

    if position == "NONE":
        result["status"] = "NO_POSITION"
        return result

    # --------------------------------------------------------
    # CALL
    # --------------------------------------------------------

    if position == "CALL":

        if r2 > 0 and price >= r2:

            result["status"] = "CALL_TARGET_2"
            result["target_reached"] = True
            result["risk_level"] = "TARGET"

        elif r1 > 0 and price >= r1:

            result["status"] = "CALL_TARGET_1"
            result["target_reached"] = True
            result["risk_level"] = "PROFIT"

        elif s1 > 0 and price <= s1:

            result["status"] = "CALL_SUPPORT_RISK"
            result["risk_level"] = "HIGH"

        else:

            result["status"] = "CALL_ACTIVE"

    # --------------------------------------------------------
    # PUT
    # --------------------------------------------------------

    elif position == "PUT":

        if s2 > 0 and price <= s2:

            result["status"] = "PUT_TARGET_2"
            result["target_reached"] = True
            result["risk_level"] = "TARGET"

        elif s1 > 0 and price <= s1:

            result["status"] = "PUT_TARGET_1"
            result["target_reached"] = True
            result["risk_level"] = "PROFIT"

        elif r1 > 0 and price >= r1:

            result["status"] = "PUT_RESISTANCE_RISK"
            result["risk_level"] = "HIGH"

        else:

            result["status"] = "PUT_ACTIVE"

    return result


# ============================================================
# DECISION CONSISTENCY CHECK
# ============================================================

def validate_decision_for_position(
    action,
    position
):
    """
    Decision Engine kararı ile mevcut pozisyonun
    birbiriyle tutarlı olup olmadığını kontrol eder.

    Burada yeni karar üretilmez.
    """

    action = normalize_action(action)
    position = normalize_position(position)

    if position == "NONE":

        return {
            "valid": action not in (
                "CALL KORU",
                "PUT KORU",
                "CALL KAPAT",
                "PUT KAPAT",
            ),
            "reason": "Açık pozisyon bulunmuyor.",
        }

    if position == "CALL":

        if action in (
            "PUT AL",
            "PUT KORU",
            "CALL AL",
        ):
            return {
                "valid": False,
                "reason": (
                    "Mevcut CALL pozisyonu ile "
                    "Decision Engine kararı çelişiyor."
                ),
            }

        return {
            "valid": True,
            "reason": "CALL pozisyonu ile karar uyumlu.",
        }

    if position == "PUT":

        if action in (
            "CALL AL",
            "CALL KORU",
            "PUT AL",
        ):
            return {
                "valid": False,
                "reason": (
                    "Mevcut PUT pozisyonu ile "
                    "Decision Engine kararı çelişiyor."
                ),
            }

        return {
            "valid": True,
            "reason": "PUT pozisyonu ile karar uyumlu.",
        }

    return {
        "valid": False,
        "reason": "Pozisyon tipi tanınmadı.",
    }


# ============================================================
# POSITION PERFORMANCE / PROTECTION
# ============================================================

def extract_position_entry_price(position):
    """
    Pozisyon giriş fiyatını güvenli şekilde okur.

    Desteklenen alanlar:
        entry_price
        entry
        open_price
    """

    position = safe_dict(position)

    for key in (
        "entry_price",
        "entry",
        "open_price",
    ):
        value = safe_float(
            position.get(key),
            0.0,
        )

        if value > 0:
            return value

    return 0.0


def extract_pattern_context(data, decision):
    """
    Pattern bilgisini Decision payload veya doğrudan inputtan alır.
    """

    data = safe_dict(data)
    decision = safe_dict(decision)

    pattern_data = safe_dict(
        data.get("pattern")
    )

    if not pattern_data:
        pattern_data = safe_dict(
            decision.get("_pattern")
        )

    pattern_name = safe_string(
        decision.get(
            "pattern",
            pattern_data.get(
                "pattern",
                "NONE",
            ),
        ),
        "NONE",
    ).upper()

    pattern_bias = safe_string(
        decision.get(
            "pattern_bias",
            pattern_data.get(
                "pattern_bias",
                pattern_data.get(
                    "bias",
                    pattern_data.get(
                        "final_signal",
                        "NEUTRAL",
                    ),
                ),
            ),
        ),
        "NEUTRAL",
    ).upper()

    return {
        "pattern": pattern_name,
        "pattern_bias": pattern_bias,
    }


def calculate_position_performance(
    current_price,
    position,
):
    """
    Açık pozisyonun QQQ underlying fiyatı üzerinden
    MFE / açık kâr / giveback durumunu hesaplar.

    CALL:
        fiyat yükselirse kâr.

    PUT:
        fiyat düşerse kâr.

    Bu fonksiyon opsiyon primini kullanmaz.
    """

    price = safe_float(
        current_price,
        0.0,
    )

    position = safe_dict(
        position
    )

    side = normalize_position(
        position
    )

    entry_price = extract_position_entry_price(
        position
    )

    result = {
        "valid": False,
        "side": side,
        "entry_price": entry_price,
        "current_price": price,
        "best_price": 0.0,
        "mfe_dollars": 0.0,
        "current_profit_dollars": 0.0,
        "giveback_dollars": 0.0,
        "giveback_ratio": 0.0,
        "adverse_dollars": 0.0,
    }

    if (
        side == "NONE"
        or entry_price <= 0
        or price <= 0
    ):
        return result

    previous_best = safe_float(
        position.get("best_price"),
        0.0,
    )

    if side == "CALL":

        best_price = max(
            entry_price,
            previous_best,
            price,
        )

        mfe = max(
            0.0,
            best_price - entry_price,
        )

        current_profit = (
            price
            - entry_price
        )

    else:

        candidates = [
            value
            for value in (
                entry_price,
                previous_best,
                price,
            )
            if value > 0
        ]

        best_price = min(
            candidates
        )

        mfe = max(
            0.0,
            entry_price - best_price,
        )

        current_profit = (
            entry_price
            - price
        )

    giveback = max(
        0.0,
        mfe
        - max(
            current_profit,
            0.0,
        ),
    )

    giveback_ratio = (
        giveback / mfe
        if mfe > 0
        else 0.0
    )

    adverse = max(
        0.0,
        -current_profit,
    )

    result.update(
        {
            "valid": True,
            "best_price": round(
                best_price,
                6,
            ),
            "mfe_dollars": round(
                mfe,
                6,
            ),
            "current_profit_dollars": round(
                current_profit,
                6,
            ),
            "giveback_dollars": round(
                giveback,
                6,
            ),
            "giveback_ratio": round(
                giveback_ratio,
                6,
            ),
            "adverse_dollars": round(
                adverse,
                6,
            ),
        }
    )

    return result


def evaluate_opposite_structure(
    side,
    decision,
    pattern_context,
):
    """
    Açık pozisyonun karşı yön yapısını değerlendirir.

    Tek bir zayıf veri çıkış üretmez.
    Bu fonksiyon yalnız o bar için karşı yapı var/yok bilgisini verir.
    Ardışık teyit sayısı position state içinde tutulur.
    """

    side = normalize_position(
        side
    )

    decision = safe_dict(
        decision
    )

    pattern_context = safe_dict(
        pattern_context
    )

    trend_bias = safe_string(
        decision.get(
            "trend_bias",
            decision.get(
                "trend",
                "NEUTRAL",
            ),
        ),
        "NEUTRAL",
    ).upper()

    signal_direction = safe_string(
        decision.get(
            "signal_direction",
            decision.get(
                "signal",
                "NEUTRAL",
            ),
        ),
        "NEUTRAL",
    ).upper()

    sr_event = safe_string(
        decision.get(
            "sr_event",
            "NONE",
        ),
        "NONE",
    ).upper()

    pattern_name = safe_string(
        pattern_context.get(
            "pattern",
            "NONE",
        ),
        "NONE",
    ).upper()

    pattern_bias = safe_string(
        pattern_context.get(
            "pattern_bias",
            "NEUTRAL",
        ),
        "NEUTRAL",
    ).upper()

    reasons = []

    if side == "PUT":

        if sr_event in (
            "SUPPORT_BOUNCE",
            "BOUNCE_SUPPORT",
            "REJECT_SUPPORT",
        ):
            reasons.append(
                "SUPPORT_BOUNCE"
            )

        if (
            "BULL" in pattern_bias
            or pattern_name
            in (
                "DOUBLE_BOTTOM",
                "BULLISH_REJECTION",
                "BULLISH_ENGULFING",
            )
        ):
            reasons.append(
                "BULLISH_PATTERN"
            )

        if (
            "BULL" in trend_bias
            or trend_bias == "CALL"
        ):
            reasons.append(
                "BULLISH_TREND"
            )

        if (
            signal_direction == "CALL"
            or "BULL" in signal_direction
        ):
            reasons.append(
                "CALL_SIGNAL"
            )

    elif side == "CALL":

        if sr_event in (
            "RESISTANCE_REJECTION",
            "REJECT_RESISTANCE",
        ):
            reasons.append(
                "RESISTANCE_REJECTION"
            )

        if (
            "BEAR" in pattern_bias
            or pattern_name
            in (
                "DOUBLE_TOP",
                "BEARISH_REJECTION",
                "BEARISH_ENGULFING",
            )
        ):
            reasons.append(
                "BEARISH_PATTERN"
            )

        if (
            "BEAR" in trend_bias
            or trend_bias == "PUT"
        ):
            reasons.append(
                "BEARISH_TREND"
            )

        if (
            signal_direction == "PUT"
            or "BEAR" in signal_direction
        ):
            reasons.append(
                "PUT_SIGNAL"
            )

    return {
        "opposite_structure": bool(
            reasons
        ),
        "reasons": reasons,
        "trend_bias": trend_bias,
        "signal_direction": signal_direction,
        "sr_event": sr_event,
        "pattern": pattern_name,
        "pattern_bias": pattern_bias,
    }


def evaluate_position_protection(
    current_price,
    position,
    decision,
    data=None,
):
    """
    Profit Protection + Early Invalidation Gate.

    KRİTİK:
    - Yeni CALL/PUT girişi üretmez.
    - Yalnız açık pozisyon için KAPAT override üretebilir.
    - Decision Engine'in açık kapatma / reverse kararları korunur.
    """

    position = safe_dict(
        position
    )

    decision = safe_dict(
        decision
    )

    side = normalize_position(
        position
    )

    performance = calculate_position_performance(
        current_price=current_price,
        position=position,
    )

    pattern_context = extract_pattern_context(
        data or {},
        decision,
    )

    opposite = evaluate_opposite_structure(
        side=side,
        decision=decision,
        pattern_context=pattern_context,
    )

    previous_count = int(
        safe_float(
            position.get(
                "opposite_confirmation_count"
            ),
            0.0,
        )
    )

    if opposite.get(
        "opposite_structure"
    ):
        opposite_count = (
            previous_count
            + 1
        )
    else:
        opposite_count = 0

    state_update = dict(
        position
    )

    if performance.get(
        "valid"
    ):

        state_update[
            "best_price"
        ] = performance.get(
            "best_price"
        )

        state_update[
            "mfe_dollars"
        ] = performance.get(
            "mfe_dollars"
        )

        state_update[
            "current_profit_dollars"
        ] = performance.get(
            "current_profit_dollars"
        )

        state_update[
            "giveback_dollars"
        ] = performance.get(
            "giveback_dollars"
        )

        state_update[
            "giveback_ratio"
        ] = performance.get(
            "giveback_ratio"
        )

        state_update[
            "adverse_dollars"
        ] = performance.get(
            "adverse_dollars"
        )

    state_update[
        "opposite_confirmation_count"
    ] = opposite_count

    result = {
        "applied": False,
        "action": None,
        "status": "NO_PROTECTION_EXIT",
        "reason": "",
        "performance": performance,
        "opposite_structure": opposite,
        "opposite_confirmation_count": opposite_count,
        "position_state_update": state_update,
    }

    if (
        side == "NONE"
        or not performance.get(
            "valid"
        )
    ):
        result[
            "reason"
        ] = "POSITION_PERFORMANCE_UNAVAILABLE"
        return result

    mfe = safe_float(
        performance.get(
            "mfe_dollars"
        ),
        0.0,
    )

    giveback = safe_float(
        performance.get(
            "giveback_dollars"
        ),
        0.0,
    )

    giveback_ratio = safe_float(
        performance.get(
            "giveback_ratio"
        ),
        0.0,
    )

    adverse = safe_float(
        performance.get(
            "adverse_dollars"
        ),
        0.0,
    )

    opposite_active = bool(
        opposite.get(
            "opposite_structure"
        )
    )

    # --------------------------------------------------------
    # HARD ADVERSE STOP
    # --------------------------------------------------------
    # 0DTE için savunma katmanı. Decision Engine BEKLE/KORU üretmeye
    # devam etse bile underlying girişe karşı belirgin hareket ettiyse
    # pozisyon gün sonuna kadar taşınmaz.
    if adverse >= HARD_ADVERSE_STOP_DOLLARS:
        close_action = (
            "CALL KAPAT"
            if side == "CALL"
            else "PUT KAPAT"
        )
        result.update({
            "applied": True,
            "action": close_action,
            "status": "HARD_ADVERSE_STOP_EXIT",
            "reason": (
                f"Underlying girişe karşı {adverse:.2f}$ hareket etti; "
                "0DTE hard adverse stop tetiklendi."
            ),
        })
        return result

    # --------------------------------------------------------
    # PROFIT PROTECTION
    # --------------------------------------------------------

    profit_protection = (
        mfe
        >= PROFIT_PROTECTION_MIN_MFE_DOLLARS
        and giveback
        >= PROFIT_PROTECTION_MIN_GIVEBACK_DOLLARS
        and giveback_ratio
        >= PROFIT_PROTECTION_MIN_GIVEBACK_RATIO
        and opposite_active
    )

    if profit_protection:

        close_action = (
            "CALL KAPAT"
            if side == "CALL"
            else "PUT KAPAT"
        )

        result.update(
            {
                "applied": True,
                "action": close_action,
                "status": "PROFIT_PROTECTION_EXIT",
                "reason": (
                    "Anlamlı MFE sonrası kâr geri veriliyor "
                    "ve karşı yön yapısı oluştu."
                ),
            }
        )

        return result

    # --------------------------------------------------------
    # EARLY INVALIDATION
    # --------------------------------------------------------

    early_invalidation = (
        mfe
        <= EARLY_INVALIDATION_MAX_MFE_DOLLARS
        and adverse
        >= EARLY_INVALIDATION_MIN_ADVERSE_DOLLARS
        and opposite_count
        >= EARLY_INVALIDATION_MIN_CONFIRMATIONS
    )

    if early_invalidation:

        close_action = (
            "CALL KAPAT"
            if side == "CALL"
            else "PUT KAPAT"
        )

        result.update(
            {
                "applied": True,
                "action": close_action,
                "status": "EARLY_INVALIDATION_EXIT",
                "reason": (
                    "Pozisyon yeterli MFE üretmeden tersine döndü "
                    "ve karşı yapı ardışık olarak teyit edildi."
                ),
            }
        )

        return result

    result[
        "reason"
    ] = "PROTECTION_CONDITIONS_NOT_MET"

    return result


# ============================================================
# TRADE LIFECYCLE
# ============================================================

def manage_trade_lifecycle(
    current_price,
    position_type,
    support_1,
    resistance_1,
    support_2,
    resistance_2,
    decision_action="BEKLE",
):
    """
    Trade lifecycle yöneticisi.

    KRİTİK:
    Decision Engine kararı birincil kaynaktır.

    Bu fonksiyon kendi başına yeni CALL/PUT
    giriş sinyali üretmez.
    """

    price = safe_float(
        current_price,
        0.0
    )

    position = normalize_position(
        position_type
    )

    action = normalize_action(
        decision_action
    )

    levels = monitor_position_levels(
        price,
        position,
        support_1,
        resistance_1,
        support_2,
        resistance_2,
    )

    # --------------------------------------------------------
    # INVALID PRICE
    # --------------------------------------------------------

    if price <= 0:

        return {
            "action": "BEKLE",
            "status": "INVALID_PRICE",
            "advice": "Geçerli piyasa fiyatı yok.",
            "position": position,
            "decision_action": action,
            "level_status": levels,
        }

    # --------------------------------------------------------
    # NO POSITION
    # --------------------------------------------------------

    if position == "NONE":

        if action == "CALL AL":

            return {
                "action": "CALL AL",
                "status": "NEW_CALL",
                "advice": "Decision Engine CALL AL kararı verdi.",
                "position": "NONE",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "PUT AL":

            return {
                "action": "PUT AL",
                "status": "NEW_PUT",
                "advice": "Decision Engine PUT AL kararı verdi.",
                "position": "NONE",
                "decision_action": action,
                "level_status": levels,
            }

        return {
            "action": "BEKLE",
            "status": "NO_POSITION",
            "advice": "Açık pozisyon yok. Yeni giriş bekleniyor.",
            "position": "NONE",
            "decision_action": action,
            "level_status": levels,
        }

    # --------------------------------------------------------
    # CALL POSITION
    # --------------------------------------------------------

    if position == "CALL":

        if action == "CALL KAPAT":

            return {
                "action": "CALL KAPAT",
                "status": "CLOSE_CALL",
                "advice": "Decision Engine CALL pozisyonunun kapatılmasını istedi.",
                "position": "CALL",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "CALL KORU":

            return {
                "action": "CALL KORU",
                "status": "HOLD_CALL",
                "advice": "CALL pozisyonu korunuyor.",
                "position": "CALL",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "BEKLE":

            return {
                "action": "CALL KORU",
                "status": "HOLD_CALL",
                "advice": (
                    "Decision Engine yeni işlem üretmedi. "
                    "Mevcut CALL pozisyonu korunuyor."
                ),
                "position": "CALL",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "PUT AL":

            return {
                "action": "CALL KAPAT",
                "status": "REVERSE_CALL",
                "advice": (
                    "PUT giriş kararı geldi. "
                    "Önce mevcut CALL kapatılmalıdır."
                ),
                "position": "CALL",
                "decision_action": action,
                "next_action": "PUT AL",
                "level_status": levels,
            }

        if action == "PUT KAPAT":

            return {
                "action": "CALL KAPAT",
                "status": "CONFLICT_CALL",
                "advice": (
                    "Mevcut CALL pozisyonu ile PUT KAPAT "
                    "kararı uyumsuz. CALL kapatma öncelikli."
                ),
                "position": "CALL",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "CALL AL":

            return {
                "action": "CALL KORU",
                "status": "ALREADY_CALL",
                "advice": (
                    "Zaten CALL pozisyonu açık. "
                    "Yeni CALL açılmaz."
                ),
                "position": "CALL",
                "decision_action": action,
                "level_status": levels,
            }

    # --------------------------------------------------------
    # PUT POSITION
    # --------------------------------------------------------

    if position == "PUT":

        if action == "PUT KAPAT":

            return {
                "action": "PUT KAPAT",
                "status": "CLOSE_PUT",
                "advice": "Decision Engine PUT pozisyonunun kapatılmasını istedi.",
                "position": "PUT",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "PUT KORU":

            return {
                "action": "PUT KORU",
                "status": "HOLD_PUT",
                "advice": "PUT pozisyonu korunuyor.",
                "position": "PUT",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "BEKLE":

            return {
                "action": "PUT KORU",
                "status": "HOLD_PUT",
                "advice": (
                    "Decision Engine yeni işlem üretmedi. "
                    "Mevcut PUT pozisyonu korunuyor."
                ),
                "position": "PUT",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "CALL AL":

            return {
                "action": "PUT KAPAT",
                "status": "REVERSE_PUT",
                "advice": (
                    "CALL giriş kararı geldi. "
                    "Önce mevcut PUT kapatılmalıdır."
                ),
                "position": "PUT",
                "decision_action": action,
                "next_action": "CALL AL",
                "level_status": levels,
            }

        if action == "CALL KAPAT":

            return {
                "action": "PUT KAPAT",
                "status": "CONFLICT_PUT",
                "advice": (
                    "Mevcut PUT pozisyonu ile CALL KAPAT "
                    "kararı uyumsuz. PUT kapatma öncelikli."
                ),
                "position": "PUT",
                "decision_action": action,
                "level_status": levels,
            }

        if action == "PUT AL":

            return {
                "action": "PUT KORU",
                "status": "ALREADY_PUT",
                "advice": (
                    "Zaten PUT pozisyonu açık. "
                    "Yeni PUT açılmaz."
                ),
                "position": "PUT",
                "decision_action": action,
                "level_status": levels,
            }

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    return {
        "action": "BEKLE",
        "status": "SAFE_FALLBACK",
        "advice": "Trade Manager güvenli bekleme modunda.",
        "position": position,
        "decision_action": action,
        "level_status": levels,
    }


# ============================================================
# EXECUTION GATE
# ============================================================

def evaluate_risk_and_execution(
    signal,
    current_price,
    support_1,
    resistance_1,
    decision_action=None,
):
    """
    Execution Gate.

    Eski sistemde signal doğrudan fiyat/S-R ile
    eşleştirilerek giriş yapılıyordu.

    Yeni sistemde:
        Decision Engine > Signal Engine

    Bu nedenle decision_action verilmişse
    ana karar kaynağı Decision Engine'dir.
    """

    price = safe_float(
        current_price,
        0.0
    )

    signal = normalize_action(
        signal
    )

    decision = normalize_action(
        decision_action
    )

    s1 = safe_float(
        support_1,
        0.0
    )

    r1 = safe_float(
        resistance_1,
        0.0
    )

    result = {
        "approved": False,
        "action": "BEKLE",
        "reason": "Bekleme modunda.",
        "price": price,
        "support_1": s1,
        "resistance_1": r1,
        "signal": signal,
        "decision_action": decision,
    }

    if price <= 0:

        result["reason"] = (
            "Geçerli fiyat bulunamadı."
        )

        return result

    # --------------------------------------------------------
    # DECISION ENGINE ANA KAYNAK
    # --------------------------------------------------------

    if decision_action is not None:

        if decision == "CALL AL":

            result["approved"] = True
            result["action"] = "CALL AL"
            result["reason"] = (
                "Decision Engine CALL AL kararı verdi."
            )

            return result

        if decision == "PUT AL":

            result["approved"] = True
            result["action"] = "PUT AL"
            result["reason"] = (
                "Decision Engine PUT AL kararı verdi."
            )

            return result

        result["reason"] = (
            f"Decision Engine kararı: {decision}"
        )

        return result

    # --------------------------------------------------------
    # LEGACY FALLBACK
    #
    # Decision Engine kararı verilmemişse eski
    # giriş mantığı yalnızca yardımcı fallback olarak
    # kullanılabilir.
    # --------------------------------------------------------

    if signal == "CALL AL":

        if r1 > 0 and price >= r1:

            result["approved"] = True
            result["action"] = "CALL AL"
            result["reason"] = (
                "CALL sinyali ve R1 üzeri fiyat teyidi."
            )

        else:

            result["reason"] = (
                "CALL sinyali var ancak R1 kırılımı teyit edilmedi."
            )

        return result

    if signal == "PUT AL":

        if s1 > 0 and price <= s1:

            result["approved"] = True
            result["action"] = "PUT AL"
            result["reason"] = (
                "PUT sinyali ve S1 altı fiyat teyidi."
            )

        else:

            result["reason"] = (
                "PUT sinyali var ancak S1 kırılımı teyit edilmedi."
            )

        return result

    result["reason"] = (
        "Yeni pozisyon açma koşulu oluşmadı."
    )

    return result


# ============================================================
# FULL TRADE MANAGER
# ============================================================

def trade_manager(data):
    """
    Ana Trade Manager.

    Beklenen input:

    {
        "price": ...,
        "decision": {...},
        "position": {...},
        "support_resistance": {...}
    }

    Decision Engine'in kararı esas alınır.
    """

    if not isinstance(data, dict):

        return {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "action": "BEKLE",
            "status": "INVALID_DATA",
            "reason": "Geçersiz veri formatı.",
        }

    price = safe_float(
        data.get("price"),
        0.0
    )

    decision = safe_dict(
        data.get("decision")
    )

    position = data.get(
        "position",
        {}
    )

    sr = normalize_sr(
        data.get("support_resistance")
    )

    decision_action = normalize_action(
        decision.get("action", "BEKLE")
    )

    position_type = normalize_position(
        position
    )

    lifecycle_state = normalize_lifecycle_state(
        data.get(
            "lifecycle_state",
            data.get(
                "trade_lifecycle_state",
                {},
            ),
        )
    )

    current_timestamp = extract_current_timestamp(
        data
    )

    reentry_gate = evaluate_same_direction_reentry(
        requested_action=decision_action,
        current_price=price,
        current_timestamp=current_timestamp,
        decision=decision,
        lifecycle_state=lifecycle_state,
    )

    protection = evaluate_position_protection(
        current_price=price,
        position=position,
        decision=decision,
        data=data,
    )

    protected_decision_action = decision_action

    if (
        position_type == "NONE"
        and reentry_gate.get(
            "blocked",
            False,
        )
        and decision_action
        in (
            "CALL AL",
            "PUT AL",
        )
    ):
        protected_decision_action = "BEKLE"

    # Decision Engine açıkça kapatma / ters yön girişi verdiyse
    # Trade Manager bunu değiştirmez.
    if (
        protection.get("applied")
        and decision_action
        not in (
            "CALL KAPAT",
            "PUT KAPAT",
            "CALL AL",
            "PUT AL",
        )
    ):
        protected_decision_action = normalize_action(
            protection.get(
                "action",
                decision_action,
            )
        )

    lifecycle = manage_trade_lifecycle(
        current_price=price,
        position_type=position_type,
        support_1=sr["support_1"],
        resistance_1=sr["resistance_1"],
        support_2=sr["support_2"],
        resistance_2=sr["resistance_2"],
        decision_action=protected_decision_action,
    )

    if reentry_gate.get(
        "blocked",
        False,
    ):
        lifecycle.update(
            {
                "action": "BEKLE",
                "status": "REENTRY_BLOCKED",
                "advice": (
                    "Aynı yön pozisyon kısa süre önce kapatıldı. "
                    "Yeni bağımsız reversal olayı oluşmadan tekrar giriş engellendi."
                ),
            }
        )

    lifecycle_state_update = dict(
        lifecycle_state
    )

    lifecycle_action = normalize_action(
        lifecycle.get(
            "action",
            "BEKLE",
        )
    )

    if (
        position_type in (
            "CALL",
            "PUT",
        )
        and lifecycle_action
        in (
            "CALL KAPAT",
            "PUT KAPAT",
        )
    ):
        lifecycle_state_update = build_exit_lifecycle_state(
            previous_state=lifecycle_state,
            side=position_type,
            current_price=price,
            current_timestamp=current_timestamp,
            decision=decision,
            lifecycle=lifecycle,
            protection=protection,
        )

    elif (
        position_type == "NONE"
        and lifecycle_action
        in (
            "CALL AL",
            "PUT AL",
        )
    ):
        entry_side = (
            "CALL"
            if lifecycle_action == "CALL AL"
            else "PUT"
        )

        lifecycle_state_update = build_entry_lifecycle_state(
            previous_state=lifecycle_state,
            side=entry_side,
            current_price=price,
            current_timestamp=current_timestamp,
        )

    return {
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,

        "action": lifecycle.get(
            "action",
            "BEKLE"
        ),

        "status": lifecycle.get(
            "status",
            "UNKNOWN"
        ),

        "advice": lifecycle.get(
            "advice",
            ""
        ),

        "reason": decision.get(
            "reason",
            ""
        ),

        "price": price,

        "position": position_type,

        "decision_action": decision_action,

        "decision_score": safe_float(
            decision.get(
                "final_score"
            ),
            0.0
        ),

        "decision_confidence": safe_float(
            decision.get(
                "confidence"
            ),
            0.0
        ),

        "trend_bias": safe_string(
            decision.get(
                "trend_bias"
            ),
            "NEUTRAL"
        ).upper(),

        "signal_direction": safe_string(
            decision.get(
                "signal_direction"
            ),
            "BEKLE"
        ).upper(),

        "sr_event": safe_string(
            decision.get(
                "sr_event"
            ),
            "NONE"
        ).upper(),

        "support_1": sr["support_1"],
        "support_2": sr["support_2"],
        "resistance_1": sr["resistance_1"],
        "resistance_2": sr["resistance_2"],

        "level_status": lifecycle.get(
            "level_status",
            {}
        ),

        "original_decision_action": decision_action,

        "protected_decision_action": protected_decision_action,

        "reentry_gate": reentry_gate,

        "reentry_blocked": reentry_gate.get(
            "blocked",
            False,
        ),

        "reentry_reason": reentry_gate.get(
            "reason",
            "",
        ),

        "reentry_elapsed_minutes": reentry_gate.get(
            "elapsed_minutes"
        ),

        "reentry_fresh_event": reentry_gate.get(
            "fresh_event",
            False,
        ),

        "reentry_fresh_structure": reentry_gate.get(
            "fresh_structure",
            False,
        ),

        "reentry_count": reentry_gate.get(
            "same_direction_reentry_count",
            0,
        ),

        "reentry_current_sr_event": reentry_gate.get(
            "current_sr_event",
            "NONE",
        ),

        "lifecycle_state_update": lifecycle_state_update,

        "protection_applied": protection.get(
            "applied",
            False,
        ),

        "protection_status": protection.get(
            "status",
            "NO_PROTECTION_EXIT",
        ),

        "protection_reason": protection.get(
            "reason",
            "",
        ),

        "position_performance": protection.get(
            "performance",
            {},
        ),

        "opposite_structure": protection.get(
            "opposite_structure",
            {},
        ),

        "opposite_confirmation_count": protection.get(
            "opposite_confirmation_count",
            0,
        ),

        "position_state_update": protection.get(
            "position_state_update",
            safe_dict(position),
        ),
    }


# ============================================================
# TEST SCENARIOS
# ============================================================

def trade_manager_test_scenarios():

    return {

        "NEW_CALL": {
            "price": 725.0,

            "decision": {
                "action": "CALL AL",
                "reason": "CALL giriş koşulları sağlandı.",
                "final_score": 90,
                "confidence": 90,
                "trend_bias": "BULLISH",
                "signal_direction": "CALL",
                "sr_event": "RESISTANCE_BREAK",
            },

            "position": {},

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "NEW_PUT": {
            "price": 719.0,

            "decision": {
                "action": "PUT AL",
                "reason": "PUT giriş koşulları sağlandı.",
                "final_score": 10,
                "confidence": 90,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
            },

            "position": {},

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "NO_POSITION_WAIT": {
            "price": 720.8,

            "decision": {
                "action": "BEKLE",
                "reason": "Signal Engine işlem yönü üretmedi.",
                "final_score": 39.5,
                "confidence": 58,
                "trend_bias": "NEUTRAL",
                "signal_direction": "BEKLE",
                "sr_event": "INSIDE_RANGE",
            },

            "position": {},

            "support_resistance": {
                "support_1": 718.48,
                "support_2": 713.95,
                "resistance_1": 725.58,
                "resistance_2": 728.15,
            },
        },

        "CALL_HOLD": {
            "price": 723.0,

            "decision": {
                "action": "CALL KORU",
                "reason": "Call pozisyonu korunuyor.",
                "final_score": 85,
                "confidence": 85,
                "trend_bias": "BULLISH",
                "signal_direction": "CALL",
                "sr_event": "INSIDE_RANGE",
            },

            "position": {
                "type": "CALL"
            },

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "PUT_HOLD": {
            "price": 718.0,

            "decision": {
                "action": "PUT KORU",
                "reason": "Put pozisyonu korunuyor.",
                "final_score": 15,
                "confidence": 85,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "INSIDE_RANGE",
            },

            "position": {
                "type": "PUT"
            },

            "support_resistance": {
                "support_1": 717.0,
                "support_2": 714.0,
                "resistance_1": 720.0,
                "resistance_2": 724.0,
            },
        },

        "CALL_CLOSE": {
            "price": 718.0,

            "decision": {
                "action": "CALL KAPAT",
                "reason": "Bearish reversal.",
                "final_score": 20,
                "confidence": 88,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
            },

            "position": {
                "type": "CALL"
            },

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "PUT_CLOSE": {
            "price": 725.0,

            "decision": {
                "action": "PUT KAPAT",
                "reason": "Bullish reversal.",
                "final_score": 88,
                "confidence": 90,
                "trend_bias": "BULLISH",
                "signal_direction": "CALL",
                "sr_event": "RESISTANCE_BREAK",
            },

            "position": {
                "type": "PUT"
            },

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "CALL_REVERSE_TO_PUT": {
            "price": 719.0,

            "decision": {
                "action": "PUT AL",
                "reason": "Bearish reversal.",
                "final_score": 15,
                "confidence": 90,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
            },

            "position": {
                "type": "CALL"
            },

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "PUT_REVERSE_TO_CALL": {
            "price": 725.0,

            "decision": {
                "action": "CALL AL",
                "reason": "Bullish reversal.",
                "final_score": 90,
                "confidence": 90,
                "trend_bias": "BULLISH",
                "signal_direction": "CALL",
                "sr_event": "RESISTANCE_BREAK",
            },

            "position": {
                "type": "PUT"
            },

            "support_resistance": {
                "support_1": 720.0,
                "support_2": 717.0,
                "resistance_1": 724.0,
                "resistance_2": 727.0,
            },
        },

        "PUT_PROFIT_PROTECTION": {
            "price": 719.0,

            "decision": {
                "action": "PUT KORU",
                "trend_bias": "NEUTRAL",
                "signal_direction": "PUT",
                "sr_event": "INSIDE_RANGE",
                "_pattern": {
                    "pattern": "DOUBLE_BOTTOM",
                    "bias": "BULLISH",
                },
            },

            "position": {
                "type": "PUT",
                "entry_price": 720.0,
                "best_price": 718.0,
                "opposite_confirmation_count": 0,
            },

            "support_resistance": {
                "support_1": 718.0,
                "support_2": 716.0,
                "resistance_1": 722.0,
                "resistance_2": 724.0,
            },
        },

        "PUT_EARLY_INVALIDATION": {
            "price": 714.20,

            "decision": {
                "action": "PUT KORU",
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
                "_pattern": {
                    "pattern": "DOUBLE_BOTTOM",
                    "bias": "BULLISH",
                },
            },

            "position": {
                "type": "PUT",
                "entry_price": 713.50,
                "best_price": 713.19,
                "opposite_confirmation_count": 2,
            },

            "support_resistance": {
                "support_1": 713.8,
                "support_2": 712.0,
                "resistance_1": 715.0,
                "resistance_2": 717.0,
            },
        },

        "PUT_REENTRY_30M_BLOCK": {
            "price": 718.80,
            "timestamp": "2026-08-11T12:30:00-04:00",
            "decision": {
                "action": "PUT AL",
                "final_score": 75,
                "confidence": 90,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
            },
            "position": {},
            "lifecycle_state": {
                "last_exit_side": "PUT",
                "last_exit_time": "2026-08-11T12:00:00-04:00",
                "last_exit_price": 719.26,
                "last_exit_status": "PROFIT_PROTECTION_EXIT",
                "last_exit_sr_event": "INSIDE_RANGE",
                "last_exit_reversal_event_id": 1,
                "same_direction_reentry_count": 0,
            },
            "support_resistance": {
                "support_1": 718.50,
                "support_2": 716.00,
                "resistance_1": 721.00,
                "resistance_2": 724.00,
            },
        },

        "PUT_REENTRY_60M_FRESH_STRUCTURE": {
            "price": 718.07,
            "timestamp": "2026-08-11T13:00:00-04:00",
            "decision": {
                "action": "PUT AL",
                "final_score": 75,
                "confidence": 90,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
            },
            "position": {},
            "lifecycle_state": {
                "last_exit_side": "PUT",
                "last_exit_time": "2026-08-11T12:00:00-04:00",
                "last_exit_price": 719.26,
                "last_exit_status": "PROFIT_PROTECTION_EXIT",
                "last_exit_sr_event": "INSIDE_RANGE",
                "last_exit_reversal_event_id": 1,
                "same_direction_reentry_count": 0,
            },
            "support_resistance": {
                "support_1": 718.25,
                "support_2": 716.00,
                "resistance_1": 721.00,
                "resistance_2": 724.00,
            },
        },

        "PUT_SECOND_CONTINUATION_BLOCK": {
            "price": 717.05,
            "timestamp": "2026-08-11T15:00:00-04:00",
            "decision": {
                "action": "PUT AL",
                "final_score": 75,
                "confidence": 90,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "SUPPORT_BREAK",
            },
            "position": {},
            "lifecycle_state": {
                "last_exit_side": "PUT",
                "last_exit_time": "2026-08-11T13:45:00-04:00",
                "last_exit_price": 718.25,
                "last_exit_status": "EARLY_INVALIDATION_EXIT",
                "last_exit_sr_event": "INSIDE_RANGE",
                "last_exit_reversal_event_id": 1,
                "same_direction_reentry_count": 1,
            },
            "support_resistance": {
                "support_1": 717.20,
                "support_2": 715.00,
                "resistance_1": 720.00,
                "resistance_2": 723.00,
            },
        },

        "PUT_NEW_FIRST_SIGNAL_ALLOW": {
            "price": 718.50,
            "timestamp": "2026-08-11T12:30:00-04:00",
            "decision": {
                "action": "PUT AL",
                "final_score": 82,
                "confidence": 95,
                "trend_bias": "BEARISH",
                "signal_direction": "PUT",
                "sr_event": "INSIDE_RANGE",
                "reversal_confirmation": {
                    "event_role": "FIRST_SIGNAL",
                    "event_id": 9,
                    "put_entry_candidate": True,
                    "reversal_score": 100,
                },
            },
            "position": {},
            "lifecycle_state": {
                "last_exit_side": "PUT",
                "last_exit_time": "2026-08-11T12:00:00-04:00",
                "last_exit_price": 719.26,
                "last_exit_status": "PROFIT_PROTECTION_EXIT",
                "last_exit_sr_event": "INSIDE_RANGE",
                "last_exit_reversal_event_id": 1,
                "same_direction_reentry_count": 0,
            },
            "support_resistance": {
                "support_1": 718.00,
                "support_2": 716.00,
                "resistance_1": 721.00,
                "resistance_2": 724.00,
            },
        },

        "OPPOSITE_CALL_AFTER_PUT_EXIT": {
            "price": 720.50,
            "timestamp": "2026-08-11T12:10:00-04:00",
            "decision": {
                "action": "CALL AL",
                "final_score": 85,
                "confidence": 92,
                "trend_bias": "BULLISH",
                "signal_direction": "CALL",
                "sr_event": "RESISTANCE_BREAK",
            },
            "position": {},
            "lifecycle_state": {
                "last_exit_side": "PUT",
                "last_exit_time": "2026-08-11T12:00:00-04:00",
                "last_exit_price": 719.26,
                "last_exit_status": "PROFIT_PROTECTION_EXIT",
                "last_exit_sr_event": "INSIDE_RANGE",
                "last_exit_reversal_event_id": 1,
                "same_direction_reentry_count": 1,
            },
            "support_resistance": {
                "support_1": 718.00,
                "support_2": 716.00,
                "resistance_1": 720.00,
                "resistance_2": 723.00,
            },
        },
    }


# ============================================================
# EXPECTED RESULTS
# ============================================================

def trade_manager_expected_results():

    return {

        "NEW_CALL": "CALL AL",
        "NEW_PUT": "PUT AL",
        "NO_POSITION_WAIT": "BEKLE",
        "CALL_HOLD": "CALL KORU",
        "PUT_HOLD": "PUT KORU",
        "CALL_CLOSE": "CALL KAPAT",
        "PUT_CLOSE": "PUT KAPAT",
        "CALL_REVERSE_TO_PUT": "CALL KAPAT",
        "PUT_REVERSE_TO_CALL": "PUT KAPAT",
        "PUT_PROFIT_PROTECTION": "PUT KAPAT",
        "PUT_EARLY_INVALIDATION": "PUT KAPAT",
        "PUT_REENTRY_30M_BLOCK": "BEKLE",
        "PUT_REENTRY_60M_FRESH_STRUCTURE": "PUT AL",
        "PUT_SECOND_CONTINUATION_BLOCK": "BEKLE",
        "PUT_NEW_FIRST_SIGNAL_ALLOW": "PUT AL",
        "OPPOSITE_CALL_AFTER_PUT_EXIT": "CALL AL",
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_trade_manager():

    scenarios = trade_manager_test_scenarios()

    expected = trade_manager_expected_results()

    results = {}

    total = 0
    passed = 0

    for name, data in scenarios.items():

        total += 1

        try:

            result = trade_manager(
                data
            )

            actual = result.get(
                "action",
                "ERROR"
            )

            expected_action = expected.get(
                name,
                "BEKLE"
            )

            test_passed = (
                actual == expected_action
            )

            if test_passed:
                passed += 1

            results[name] = {
                "expected": expected_action,
                "actual": actual,
                "passed": test_passed,
                "status": result.get(
                    "status"
                ),
                "position": result.get(
                    "position"
                ),
                "decision": result.get(
                    "decision_action"
                ),
            }

        except Exception as e:

            results[name] = {
                "expected": expected.get(
                    name,
                    "BEKLE"
                ),
                "actual": "ERROR",
                "passed": False,
                "error": str(e),
            }

    status = (
        "PASS"
        if passed == total
        else "FAIL"
    )

    return {
        "status": status,
        "engine": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "tests": results,
    }


# ============================================================
# PRINT VALIDATION REPORT
# ============================================================

def print_validation_report():

    report = validate_trade_manager()

    print()
    print("=" * 100)
    print("QQQ PRO TRADE MANAGER VALIDATION")
    print("=" * 100)

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

    print("-" * 100)

    for name, test in report["tests"].items():

        expected = test.get(
            "expected",
            "?"
        )

        actual = test.get(
            "actual",
            "?"
        )

        status = (
            "PASS"
            if test.get("passed")
            else "FAIL"
        )

        print(
            f"{name:<28} | "
            f"BEKLENEN: {expected:<12} | "
            f"GERÇEK: {actual:<12} | "
            f"{status}"
        )

        if not test.get("passed"):

            print(
                f"    POSITION={test.get('position')} "
                f"DECISION={test.get('decision')}"
            )

            if test.get("error"):
                print(
                    f"    ERROR={test.get('error')}"
                )

    print("-" * 100)

    print(
        f"SONUÇ: {report['passed']}/"
        f"{report['total_tests']} TEST PASS"
    )

    print("=" * 100)

    return report


# ============================================================
# SIMPLE VALIDATION ALIAS
# ============================================================

def validate():
    return validate_trade_manager()


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":
    print_validation_report()