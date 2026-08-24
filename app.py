# ============================================================
# QQQ PRO v6 FINAL LIVE
# PROFESSIONAL 0DTE OPTIONS DASHBOARD
#
# FINAL VERIFIED PIPELINE
#
# MARKET DATA
#     ↓
# TREND ENGINE
#     ↓
# GAP ENGINE
#     ↓
# SIGNAL ENGINE
#     ↓
# SUPPORT / RESISTANCE
#     ↓
# PATTERN ENGINE
#     ↓
# OPTIONS CHAIN
#     ↓
# 0DTE OPTIONS RISK
#     ↓
# BIG MOVE WARNING
#     ↓
# REVERSAL CONFIRMATION v1.3
#     ↓
# DECISION ENGINE v5.8.2
#     ↓
# TRADE MANAGER
#
# NOT:
# Broker'a otomatik emir göndermez.
# Nihai karar ve pozisyon yönetim tavsiyesi üretir.
# ============================================================

from __future__ import annotations

import importlib
import os
import time
import traceback
from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="QQQ PRO v6 FINAL LIVE",
    page_icon="📈",
    layout="wide",
)


# ============================================================
# TARAYICI OTOMATİK ÇEVİRİ KORUMASI
# ============================================================
#
# Chrome / Edge otomatik çevirisi finans terimlerini bozabiliyor:
# PUT -> KOY, CALL -> ÇAĞRI, MARKET -> PAZAR vb.
# Bu blok QQQ PRO arayüzünün çevrilmesini engeller.
#
components.html(
    """
    <script>
    try {
        const doc = window.parent.document;

        doc.documentElement.setAttribute("translate", "no");
        doc.documentElement.classList.add("notranslate");

        if (doc.body) {
            doc.body.setAttribute("translate", "no");
            doc.body.classList.add("notranslate");
        }

        let meta = doc.querySelector('meta[name="google"]');

        if (!meta) {
            meta = doc.createElement("meta");
            meta.setAttribute("name", "google");
            doc.head.appendChild(meta);
        }

        meta.setAttribute("content", "notranslate");

        const markNoTranslate = () => {
            const app = doc.querySelector(
                '[data-testid="stAppViewContainer"]'
            );

            if (app) {
                app.setAttribute("translate", "no");
                app.classList.add("notranslate");
            }

            doc.querySelectorAll(
                '[data-testid="stMetric"], ' +
                '[data-testid="stMarkdownContainer"], ' +
                '[data-testid="stNotification"]'
            ).forEach((el) => {
                el.setAttribute("translate", "no");
                el.classList.add("notranslate");
            });
        };

        markNoTranslate();

        const observer = new MutationObserver(
            () => markNoTranslate()
        );

        observer.observe(
            doc.body,
            {
                childList: true,
                subtree: true
            }
        );
    } catch (e) {
        console.log(
            "QQQ PRO no-translate protection:",
            e
        );
    }
    </script>
    """,
    height=0,
)


# ============================================================
# ENGINE IMPORTS
# ============================================================

try:
    from market_data import get_market_data
    from trend_engine import trend_engine
    from gap_engine import analyze_gap
    from signal_engine import signal_engine

    from support_resistance import (
        calculate_support_resistance,
        analyze_support_resistance,
    )

    from pattern_engine import pattern_engine
    from big_move_warning_engine import analyze_big_move_warning
    from reversal_confirmation_engine import (
        analyze_reversal_confirmation,
    )
    from options_chain import analyze_options_chain
    from decision_engine import decision_engine
    from trade_manager import trade_manager

    options_risk_module = importlib.import_module(
        "0dte_options_risk_layer"
    )

    analyze_0dte_options_risk = (
        options_risk_module.analyze_0dte_options_risk
    )

except Exception:
    st.error(
        "Motor import hatası. QQQ PRO çekirdek dosyalarını kontrol edin."
    )
    st.code(traceback.format_exc())
    st.stop()


# Fırsat Radarı production karar zincirinden bilinçli olarak ayrıdır.
# Dosya eksikse ana uygulama çalışmaya devam eder.
try:
    from opportunity_candidate_engine import (
        opportunity_candidate_engine,
    )
    OPPORTUNITY_RADAR_AVAILABLE = True
    OPPORTUNITY_RADAR_IMPORT_ERROR = ""
except Exception as exc:
    opportunity_candidate_engine = None
    OPPORTUNITY_RADAR_AVAILABLE = False
    OPPORTUNITY_RADAR_IMPORT_ERROR = str(exc)


# ============================================================
# CONSTANTS
# ============================================================

SYMBOLS = ["QQQ", "SPY"]

REFRESH_OPTIONS = {
    "3 saniye (Hızlı)": 3,
    "5 saniye": 5,
    "10 saniye": 10,
    "15 saniye": 15,
    "30 saniye": 30,
}

VALID_ACTIONS = {
    "CALL AL",
    "PUT AL",
    "BEKLE",
    "CALL KORU",
    "PUT KORU",
    "CALL KAPAT",
    "PUT KAPAT",
}


# ============================================================
# SESSION STATE
# ============================================================

SESSION_DEFAULTS = {
    "market": None,
    "trend": None,
    "gap": None,
    "signal": None,
    "support_resistance": None,
    "pattern": None,
    "big_move_warning": None,
    "reversal_confirmation": None,
    "reversal_event_state": None,
    "options_data": None,
    "options_risk": None,
    "decision": None,
    "trade_manager": None,
    "opportunity_radar": None,
    "opportunity_radar_state": {},
    "debug": None,
    "last_update": None,
    "sim_balance": 10000.0,
    "open_position": None,
}

for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value: Any, default: float = 0.0) -> float:
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

        if pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip().upper()


def get_signal(data: Dict[str, Any]) -> str:
    data = safe_dict(data)

    raw = normalize_text(
        data.get("final_signal")
        or data.get("signal")
        or data.get("dominant_direction")
        or "NEUTRAL"
    )

    if "CALL" in raw:
        return "CALL"

    if "PUT" in raw:
        return "PUT"

    return "BEKLE"


def get_score(data: Dict[str, Any]) -> float:
    data = safe_dict(data)

    return safe_float(
        data.get(
            "final_score",
            data.get("score", 50.0),
        ),
        50.0,
    )


def signal_icon(signal_value: str) -> str:
    if signal_value == "CALL":
        return "🟢"

    if signal_value == "PUT":
        return "🔴"

    return "🟡"


def get_position_type() -> str:
    position = st.session_state.get("open_position")

    if not isinstance(position, dict):
        return "NONE"

    raw = normalize_text(
        position.get("type")
        or position.get("position")
        or position.get("side")
        or ""
    )

    if "CALL" in raw:
        return "CALL"

    if "PUT" in raw:
        return "PUT"

    return "NONE"


def calculate_sr_final(
    df: pd.DataFrame,
    price: float,
) -> Dict[str, Any]:
    """
    Final entegrasyon testindeki aynı S/R akışını kullanır:
    1) calculate_support_resistance
    2) analyze_support_resistance
    3) iki sonucu merge eder
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}

    base = calculate_support_resistance(df)

    if not isinstance(base, dict):
        base = {}

    try:
        analyzed = analyze_support_resistance(df, price)
    except TypeError:
        analyzed = analyze_support_resistance(
            df=df,
            price=price,
        )

    if not isinstance(analyzed, dict):
        analyzed = {}

    result = dict(base)
    result.update(analyzed)

    return result


def default_options_risk(reason: str) -> Dict[str, Any]:
    return {
        "risk_level": "BLOCK",
        "risk_score": 0,
        "trade_allowed": False,
        "side": "NONE",
        "option_bias": "NONE",
        "confidence": 0,
        "data_valid": False,
        "signal_aligned": False,
        "status": "ERROR",
        "reasons": [reason],
    }


def build_decision_reason(
    decision: Dict[str, Any],
    trend: Dict[str, Any],
    signal: Dict[str, Any],
    sr: Dict[str, Any],
    pattern: Dict[str, Any],
) -> str:
    """
    Decision Engine'in kararını değiştirmez.
    UI için anlaşılır Türkçe açıklama üretir.
    """
    decision = safe_dict(decision)

    existing = str(
        decision.get("reason") or ""
    ).strip()

    if existing:
        return existing

    action = normalize_text(
        decision.get("action"),
        "BEKLE",
    )

    dominant = normalize_text(
        decision.get("dominant_direction")
        or decision.get("final_signal"),
        "NEUTRAL",
    )

    sr_event = normalize_text(
        decision.get("sr_event")
        or sr.get("event")
        or sr.get("sr_event"),
        "NONE",
    )

    pattern_bias = normalize_text(
        pattern.get("bias")
        or pattern.get("final_signal"),
        "NEUTRAL",
    )

    # Pattern motoru BULLISH/BEARISH, karar motoru CALL/PUT dili kullanır.
    pattern_side = {
        "BULLISH": "CALL",
        "CALL": "CALL",
        "BEARISH": "PUT",
        "PUT": "PUT",
    }.get(pattern_bias, "NEUTRAL")

    final_score = safe_float(
        decision.get("final_score"),
        0.0,
    )

    confidence = safe_float(
        decision.get("confidence"),
        0.0,
    )

    if action == "CALL AL":
        return (
            "CALL yönü gerekli teyitleri geçti; Trend + Signal + "
            "S/R giriş onayı ve risk kapısı işlemi destekliyor."
        )

    if action == "PUT AL":
        return (
            "PUT yönü gerekli teyitleri geçti; Trend + Signal + "
            "S/R giriş onayı ve risk kapısı işlemi destekliyor."
        )

    if action == "CALL KAPAT":
        return "CALL pozisyonu için çıkış koşulu oluştu."

    if action == "PUT KAPAT":
        return "PUT pozisyonu için çıkış koşulu oluştu."

    if action == "CALL KORU":
        return "CALL pozisyonunun ana tezi korunuyor."

    if action == "PUT KORU":
        return "PUT pozisyonunun ana tezi korunuyor."

    if sr_event in {
        "",
        "NONE",
        "INSIDE_RANGE",
        "RANGE",
        "NO_EVENT",
    }:
        return (
            "Trend veya sinyal yön gösterebilir; ancak S/R giriş teyidi "
            "yok veya fiyat range içinde. Yeni işlem açılmıyor."
        )

    if dominant == "NEUTRAL":
        return "CALL ve PUT tarafları arasında yeterli skor üstünlüğü yok."

    if final_score < 55:
        return (
            f"{dominant} yönü baskın ancak final skor "
            f"{final_score:.1f}; giriş için yeterli değil."
        )

    if pattern_side not in {"NEUTRAL", dominant}:
        return (
            f"{dominant} yönü baskın fakat Pattern Engine "
            f"{pattern_bias} yönünde karşı teyit üretiyor."
        )

    if confidence < 70:
        return (
            f"Yön mevcut fakat güven {confidence:.1f}%; "
            "giriş eşiği karşılanmadı."
        )

    return "Giriş kapılarından en az biri onaylanmadığı için BEKLE."


def extract_trade_action(
    trade_result: Dict[str, Any],
    decision: Dict[str, Any],
) -> str:
    trade_result = safe_dict(trade_result)
    decision = safe_dict(decision)

    for key in (
        "final_action",
        "action",
        "trade_action",
        "manager_action",
        "recommended_action",
        "decision",
    ):
        value = normalize_text(
            trade_result.get(key)
        )

        if value in VALID_ACTIONS:
            return value

    decision_action = normalize_text(
        decision.get("action"),
        "BEKLE",
    )

    if decision_action in VALID_ACTIONS:
        return decision_action

    return "BEKLE"


# ============================================================
# TEST MODE
# ============================================================

def apply_test_mode(
    decision: Dict[str, Any],
    test_mode: str,
    position: str,
) -> Dict[str, Any]:

    if not isinstance(decision, dict):
        return decision

    test = decision.copy()
    test["test_mode"] = False
    test["test_message"] = "GERÇEK MOTOR SİNYALİ AKTİF"

    if test_mode == "NORMAL":
        return test

    if test_mode == "CALL AL TEST":
        test["action"] = "CALL AL"
        test["signal"] = "CALL"
        test["final_signal"] = "CALL"
        test["test_mode"] = True
        test["test_message"] = "CALL AL TEST AKTİF"
        return test

    if test_mode == "PUT AL TEST":
        test["action"] = "PUT AL"
        test["signal"] = "PUT"
        test["final_signal"] = "PUT"
        test["test_mode"] = True
        test["test_message"] = "PUT AL TEST AKTİF"
        return test

    if test_mode == "SAT TEST":
        if position == "CALL":
            test["action"] = "CALL KAPAT"
            test["final_signal"] = "CALL KAPAT"

        elif position == "PUT":
            test["action"] = "PUT KAPAT"
            test["final_signal"] = "PUT KAPAT"

        else:
            test["action"] = "BEKLE"
            test["final_signal"] = "BEKLE"

        test["test_mode"] = True
        test["test_message"] = "SAT TEST AKTİF"
        return test

    return test


# ============================================================
# PIPELINE RUNNER
# ============================================================

def run_pipeline(sym: str) -> Dict[str, Any]:
    try:
        # ----------------------------------------------------
        # 1. MARKET DATA
        # ----------------------------------------------------
        market = get_market_data(sym)

        if not isinstance(market, dict):
            raise RuntimeError(
                "Market Data geçerli dict döndürmedi."
            )

        price = safe_float(
            market.get("price"),
            0.0,
        )

        if (
            not market.get("data_ok", False)
            and price <= 0
        ):
            raise RuntimeError(
                "Piyasa verisi alınamadı."
            )

        df_5m = market.get("df_5m")

        df_1m = market.get("df_1m")

        # ----------------------------------------------------
        # FIRSAT RADARI — GÖLGE
        # ----------------------------------------------------
        # Bu sonuç Decision Engine veya Trade Manager girdilerine
        # eklenmez. Yalnızca erken uyarı ve ekran görünürlüğüdür.
        radar_state = st.session_state.get(
            "opportunity_radar_state",
            {},
        )
        if not isinstance(radar_state, dict):
            radar_state = {}

        if (
            OPPORTUNITY_RADAR_AVAILABLE
            and callable(opportunity_candidate_engine)
            and isinstance(df_1m, pd.DataFrame)
            and not df_1m.empty
        ):
            try:
                opportunity_radar = opportunity_candidate_engine(
                    df_1m,
                    radar_state,
                )
                if not isinstance(opportunity_radar, dict):
                    opportunity_radar = {
                        "status": "ERROR",
                        "action": "BEKLE",
                        "side": "NONE",
                        "error": "Radar geçerli dict döndürmedi.",
                        "state": radar_state,
                    }
            except Exception as exc:
                opportunity_radar = {
                    "status": "ERROR",
                    "action": "BEKLE",
                    "side": "NONE",
                    "error": str(exc),
                    "state": radar_state,
                }
        else:
            opportunity_radar = {
                "status": "UNAVAILABLE",
                "action": "BEKLE",
                "side": "NONE",
                "error": (
                    OPPORTUNITY_RADAR_IMPORT_ERROR
                    if not OPPORTUNITY_RADAR_AVAILABLE
                    else "1 dakikalık veri henüz hazır değil."
                ),
                "state": radar_state,
            }

        if not isinstance(df_5m, pd.DataFrame):
            raise RuntimeError(
                "5m DataFrame bulunamadı."
            )

        # ----------------------------------------------------
        # 2. TREND ENGINE
        # ----------------------------------------------------
        trend = trend_engine(market)

        if not isinstance(trend, dict):
            trend = {}

        # ----------------------------------------------------
        # 3. GAP ENGINE
        # ----------------------------------------------------
        gap = analyze_gap(market)

        if not isinstance(gap, dict):
            gap = {}

        # ----------------------------------------------------
        # 4. SIGNAL ENGINE
        # ----------------------------------------------------
        signal = signal_engine(
            market,
            trend,
        )

        if not isinstance(signal, dict):
            signal = {}

        # ----------------------------------------------------
        # 5. SUPPORT / RESISTANCE
        # ----------------------------------------------------
        support_resistance = calculate_sr_final(
            df_5m,
            price,
        )

        # ----------------------------------------------------
        # 6. PATTERN ENGINE
        # ----------------------------------------------------
        pattern = pattern_engine(
            market=market,
            df=df_5m,
        )

        if not isinstance(pattern, dict):
            pattern = {
                "valid": False,
                "status": "ERROR",
                "pattern": "NONE",
                "bias": "NEUTRAL",
                "score": 0,
                "final_score": 0,
                "confidence": 0,
                "signal": "NEUTRAL",
                "final_signal": "NEUTRAL",
                "patterns": [],
                "reason": "Pattern Engine geçerli sonuç döndürmedi.",
            }

        # ----------------------------------------------------
        # 7. BIG MOVE WARNING ENGINE
        # ----------------------------------------------------
        try:
            big_move_warning = analyze_big_move_warning(
                market=market,
                df=market.get("df_1m"),
            )

            if not isinstance(
                big_move_warning,
                dict,
            ):
                big_move_warning = {
                    "valid": False,
                    "warning": False,
                    "warning_type": "NONE",
                    "warning_score": 0.0,
                    "filtered_warning": False,
                    "risk_level": "LOW",
                    "call_veto": False,
                    "put_entry_candidate": False,
                    "reason": (
                        "Big Move Warning Engine "
                        "geçerli dict döndürmedi."
                    ),
                }

        except Exception as exc:
            big_move_warning = {
                "valid": False,
                "warning": False,
                "warning_type": "NONE",
                "warning_score": 0.0,
                "filtered_warning": False,
                "risk_level": "LOW",
                "call_veto": False,
                "put_entry_candidate": False,
                "reason": (
                    f"Big Move Warning Engine hatası: {exc}"
                ),
            }

        # ----------------------------------------------------
        # 8. REVERSAL CONFIRMATION ENGINE v1.3
        # ----------------------------------------------------
        reversal_event_state = (
            st.session_state.get(
                "reversal_event_state"
            )
        )

        if not isinstance(
            reversal_event_state,
            dict,
        ):
            reversal_event_state = None

        try:
            reversal_confirmation = (
                analyze_reversal_confirmation(
                    market=market,
                    big_move_warning=big_move_warning,
                    trend_data=trend,
                    signal_data=signal,
                    sr_data=support_resistance,
                    pattern_data=pattern,
                    event_state=reversal_event_state,
                )
            )

            if not isinstance(
                reversal_confirmation,
                dict,
            ):
                reversal_confirmation = {
                    "engine": (
                        "QQQ PRO Reversal Confirmation Engine"
                    ),
                    "version": "1.3",
                    "valid": False,
                    "status": "ERROR",
                    "reversal_score": 0.0,
                    "reversal_level": "NONE",
                    "put_entry_candidate": False,
                    "put_hold_confirmation": False,
                    "hard_call_protection": False,
                    "late_put_blocked": False,
                    "event_role": "NO_EVENT",
                    "event_state": {},
                    "reason": (
                        "Reversal Engine geçerli dict "
                        "döndürmedi."
                    ),
                }

        except Exception as exc:
            reversal_confirmation = {
                "engine": (
                    "QQQ PRO Reversal Confirmation Engine"
                ),
                "version": "1.3",
                "valid": False,
                "status": "ERROR",
                "reversal_score": 0.0,
                "reversal_level": "NONE",
                "put_entry_candidate": False,
                "put_hold_confirmation": False,
                "hard_call_protection": False,
                "late_put_blocked": False,
                "event_role": "NO_EVENT",
                "event_state": {},
                "reason": (
                    f"Reversal Confirmation Engine "
                    f"hatası: {exc}"
                ),
            }

        next_reversal_event_state = (
            reversal_confirmation.get(
                "event_state"
            )
        )

        if not isinstance(
            next_reversal_event_state,
            dict,
        ):
            next_reversal_event_state = {}

        # ----------------------------------------------------
        # 9. OPTIONS CHAIN
        # ----------------------------------------------------
        options_data = analyze_options_chain(sym)

        if not isinstance(options_data, dict):
            options_data = {}

        # ----------------------------------------------------
        # 10. 0DTE OPTIONS RISK
        # ----------------------------------------------------
        market_signal = normalize_text(
            signal.get("final_signal")
            or signal.get("signal")
            or "NONE"
        )

        if market_signal not in {"CALL", "PUT"}:
            market_signal = "NONE"

        try:
            options_risk = analyze_0dte_options_risk(
                options_data,
                market_signal=market_signal,
                underlying_price=price,
            )
        except Exception as exc:
            options_risk = default_options_risk(
                f"0DTE risk hatası: {exc}"
            )

        if not isinstance(options_risk, dict):
            options_risk = default_options_risk(
                "0DTE Options Risk Layer geçerli sonuç döndürmedi."
            )

        # ----------------------------------------------------
        # 11. CURRENT POSITION
        # ----------------------------------------------------
        position = st.session_state.get(
            "open_position"
        )

        if not isinstance(position, dict):
            position = {}

        # ----------------------------------------------------
        # 12. DECISION ENGINE INPUT
        # ----------------------------------------------------
        decision_inputs = {
            "price": price,

            "market_data": market,

            "trend": trend,
            "trend_data": trend,

            "gap": gap,
            "gap_data": gap,

            "signal": signal,
            "signal_data": signal,

            "support_resistance": support_resistance,
            "sr": support_resistance,
            "sr_data": support_resistance,

            "pattern": pattern,
            "pattern_data": pattern,

            "big_move_warning": big_move_warning,
            "warning": big_move_warning,

            "reversal_confirmation":
                reversal_confirmation,
            "reversal": reversal_confirmation,
            "reversal_data": reversal_confirmation,

            "options_risk": options_risk,

            "position": position,
        }

        # ----------------------------------------------------
        # 13. DECISION ENGINE
        # ----------------------------------------------------
        decision = decision_engine(
            decision_inputs
        )

        if not isinstance(decision, dict):
            decision = {
                "engine": "QQQ PRO Decision Engine",
                "version": "5.8.2",
                "action": "BEKLE",
                "final_signal": "NEUTRAL",
                "final_score": 50,
                "confidence": 0,
                "status": "ERROR",
            }

        # UI açıklaması; motor kararını değiştirmez.
        decision["reason"] = build_decision_reason(
            decision,
            trend,
            signal,
            support_resistance,
            pattern,
        )

        # ----------------------------------------------------
        # 14. TRADE MANAGER
        # ----------------------------------------------------
        trade_inputs = {
            "price": price,
            "market_data": market,
            "decision": decision,
            "decision_data": decision,
            "support_resistance": support_resistance,
            "sr": support_resistance,
            "position": position,
            "options_risk": options_risk,
        }

        try:
            trade_result = trade_manager(
                trade_inputs
            )

            if not isinstance(
                trade_result,
                dict,
            ):
                trade_result = {}

        except Exception as exc:
            # Decision çalışmışsa dashboard tamamen düşmesin.
            # Hata debug alanında açıkça gösterilir.
            trade_result = {
                "status": "ERROR",
                "error": str(exc),
                "action": decision.get(
                    "action",
                    "BEKLE",
                ),
            }

        final_trade_action = extract_trade_action(
            trade_result,
            decision,
        )

        # ----------------------------------------------------
        # 15. DEBUG DATA
        # ----------------------------------------------------
        debug_data = {
            "MARKET": {
                "symbol": sym,
                "price": price,
                "data_ok": market.get("data_ok"),
                "market_open": market.get("market_open"),
                "session": market.get("session"),
                "source": market.get("source"),
                "df_1m_rows": (
                    len(market["df_1m"])
                    if isinstance(
                        market.get("df_1m"),
                        pd.DataFrame,
                    )
                    else 0
                ),
                "df_5m_rows": len(df_5m),
                "df_15m_rows": (
                    len(market["df_15m"])
                    if isinstance(
                        market.get("df_15m"),
                        pd.DataFrame,
                    )
                    else 0
                ),
            },

            "TREND": trend,
            "GAP": gap,
            "SIGNAL": signal,
            "SUPPORT_RESISTANCE": support_resistance,
            "PATTERN": pattern,
            "BIG_MOVE_WARNING": big_move_warning,
            "REVERSAL_CONFIRMATION":
                reversal_confirmation,
            "OPTIONS_DATA": options_data,
            "OPTIONS_RISK": options_risk,
            "DECISION_INPUTS": decision_inputs,
            "DECISION_OUTPUT": decision,
            "TRADE_MANAGER_INPUTS": trade_inputs,
            "TRADE_MANAGER_OUTPUT": trade_result,
            "OPPORTUNITY_RADAR": opportunity_radar,
        }

        return {
            "market": market,
            "trend": trend,
            "gap": gap,
            "signal": signal,
            "support_resistance": support_resistance,
            "pattern": pattern,
            "big_move_warning": big_move_warning,
            "reversal_confirmation":
                reversal_confirmation,
            "reversal_event_state":
                next_reversal_event_state,
            "options_data": options_data,
            "options_risk": options_risk,
            "position": position,
            "decision": decision,
            "trade_manager": trade_result,
            "opportunity_radar": opportunity_radar,
            "opportunity_radar_state": opportunity_radar.get(
                "state",
                radar_state,
            ),
            "trade_action": final_trade_action,
            "debug": debug_data,
            "status": "READY",
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


# ============================================================
# HEADER
# ============================================================

st.title("🚀 QQQ PRO v6 SON SÜRÜM CANLI")

st.caption(
    "0DTE Opsiyon Karar Paneli | "
    "Son Doğrulanan Sistem | "
    "Karar Motoru v5.8.13 | Dönüş Teyidi v1.3.3 | İşlem Yöneticisi v6.4"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⚙ Sistem Ayarları")

symbol = st.sidebar.selectbox(
    "Sembol",
    SYMBOLS,
    index=0,
    key="selected_symbol",
)

refresh_text = st.sidebar.selectbox(
    "Canlı Veri Yenileme",
    list(REFRESH_OPTIONS.keys()),
    index=1,
)

refresh_seconds = REFRESH_OPTIONS[
    refresh_text
]

auto_refresh = st.sidebar.checkbox(
    "🔄 Otomatik Yenileme (Canlı Akış)",
    value=False,
)

if st.sidebar.button(
    "⚡ Verileri Şimdi Güncelle"
):
    st.cache_data.clear()

    for key in (
        "market",
        "trend",
        "gap",
        "signal",
        "support_resistance",
        "pattern",
        "big_move_warning",
        "reversal_confirmation",
        "options_data",
        "options_risk",
        "decision",
        "trade_manager",
        "debug",
    ):
        st.session_state[key] = None

    st.rerun()


# ============================================================
# POSITION SIMULATOR
# ============================================================

st.sidebar.divider()

st.sidebar.subheader(
    "🎯 Pozisyon Simülatörü"
)

st.sidebar.caption(
    "Broker emri göndermez; yalnızca Trade Manager "
    "pozisyon yaşam döngüsünü test eder."
)

st.sidebar.text(
    f"Sanal Bakiye: "
    f"${st.session_state.sim_balance:,.2f}"
)

sim1, sim2 = st.sidebar.columns(2)

with sim1:
    if st.button(
        "🟢 CALL Aç",
        key="sim_call",
    ):
        current_price = safe_float(
            safe_dict(
                st.session_state.market
            ).get("price"),
            0.0,
        )

        st.session_state.open_position = {
            "type": "CALL",
            "entry": current_price,
            "opened_at": datetime.now().isoformat(),
        }

        st.rerun()

with sim2:
    if st.button(
        "🔴 PUT Aç",
        key="sim_put",
    ):
        current_price = safe_float(
            safe_dict(
                st.session_state.market
            ).get("price"),
            0.0,
        )

        st.session_state.open_position = {
            "type": "PUT",
            "entry": current_price,
            "opened_at": datetime.now().isoformat(),
        }

        st.rerun()


current_position = get_position_type()

if current_position != "NONE":
    position_data = safe_dict(
        st.session_state.open_position
    )

    st.sidebar.info(
        f"Aktif Pozisyon: {current_position}\n\n"
        f"Giriş: {safe_float(position_data.get('entry')):.2f}"
    )

    if st.sidebar.button(
        "⚠️ Pozisyonu Kapat",
        key="close_position",
    ):
        st.session_state.open_position = None
        st.rerun()

else:
    st.sidebar.info(
        "Aktif pozisyon yok."
    )


# ============================================================
# TEST PANEL
# ============================================================

test_mode = st.sidebar.selectbox(
    "🧪 Görsel Sinyal Test Paneli",
    [
        "NORMAL",
        "CALL AL TEST",
        "PUT AL TEST",
        "SAT TEST",
    ],
)

st.sidebar.caption(
    "Test paneli yalnızca ekrandaki gösterimi değiştirir; "
    "gerçek motor sonuçlarını değiştirmez."
)


# ============================================================
# RUN PIPELINE
# ============================================================

res = run_pipeline(
    symbol
)

if res.get("status") == "READY":
    st.session_state.market = res["market"]
    st.session_state.trend = res["trend"]
    st.session_state.gap = res["gap"]
    st.session_state.signal = res["signal"]
    st.session_state.support_resistance = (
        res["support_resistance"]
    )
    st.session_state.pattern = res["pattern"]
    st.session_state.big_move_warning = (
        res["big_move_warning"]
    )
    st.session_state.reversal_confirmation = (
        res["reversal_confirmation"]
    )
    st.session_state.reversal_event_state = (
        res["reversal_event_state"]
    )
    st.session_state.options_data = (
        res["options_data"]
    )
    st.session_state.options_risk = (
        res["options_risk"]
    )
    st.session_state.decision = res["decision"]
    st.session_state.trade_manager = (
        res["trade_manager"]
    )
    st.session_state.opportunity_radar = (
        res["opportunity_radar"]
    )
    st.session_state.opportunity_radar_state = (
        res["opportunity_radar_state"]
    )
    st.session_state.debug = res["debug"]
    st.session_state.last_update = datetime.now()

else:
    st.error(
        "Pipeline çalıştırılamadı."
    )

    st.code(
        res.get(
            "error",
            "Bilinmeyen hata.",
        )
    )

    if res.get("traceback"):
        st.code(
            res["traceback"]
        )


# ============================================================
# CURRENT DATA
# ============================================================

market = safe_dict(
    st.session_state.market
)

trend = safe_dict(
    st.session_state.trend
)

gap = safe_dict(
    st.session_state.gap
)

signal = safe_dict(
    st.session_state.signal
)

support_resistance = safe_dict(
    st.session_state.support_resistance
)

pattern = safe_dict(
    st.session_state.pattern
)

big_move_warning = safe_dict(
    st.session_state.big_move_warning
)

reversal_confirmation = safe_dict(
    st.session_state.reversal_confirmation
)

options_data = safe_dict(
    st.session_state.options_data
)

options_risk = safe_dict(
    st.session_state.options_risk
)

decision = safe_dict(
    st.session_state.decision
)

trade_result = safe_dict(
    st.session_state.trade_manager
)


# ============================================================
# CLOUD ACCESS PROTECTION
# ============================================================

def require_cloud_password() -> None:
    """Public URL'de QQQ PRO ekranını parola ile korur."""
    try:
        configured_password = str(
            st.secrets.get("APP_PASSWORD", "")
        ).strip()
    except Exception:
        configured_password = str(
            os.getenv("APP_PASSWORD", "")
        ).strip()

    if not configured_password:
        st.error(
            "Bulut parolası ayarlanmamış. Streamlit ayarlarında "
            "APP_PASSWORD secret değerini ekleyin."
        )
        st.stop()

    if st.session_state.get("cloud_authenticated", False):
        return

    st.title("🔐 QQQ PRO Mobil Giriş")
    entered_password = st.text_input(
        "Uygulama parolası",
        type="password",
    )
    if st.button("Giriş Yap", use_container_width=True):
        if entered_password == configured_password:
            st.session_state.cloud_authenticated = True
            st.rerun()
        else:
            st.error("Parola yanlış.")
    st.stop()


require_cloud_password()


# Telefon ekranında kolonların okunabilir biçimde alt alta geçmesini sağlar.
st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem;
            padding-left: 0.65rem;
            padding-right: 0.65rem;
        }
        div[data-testid="stMetric"] {
            min-width: 145px;
        }
        h1 { font-size: 1.55rem !important; }
        h2, h3 { font-size: 1.15rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

opportunity_radar = safe_dict(
    st.session_state.opportunity_radar
)

position_type = get_position_type()

display_decision = apply_test_mode(
    decision,
    test_mode,
    position_type,
)


# ============================================================
# PIPELINE STATUS
# ============================================================

st.divider()
st.subheader("🧬 SİSTEM DURUMU")

pipeline_items = [
    ("PİYASA", bool(market)),
    ("TREND", bool(trend)),
    ("GAP", bool(gap)),
    ("SİNYAL", bool(signal)),
    ("S/R", bool(support_resistance)),
    ("PATTERN", bool(pattern)),
    ("BÜYÜK HAREKET", bool(big_move_warning)),
    ("DÖNÜŞ TEYİDİ", bool(reversal_confirmation)),
    ("OPSİYONLAR", bool(options_data)),
    ("0DTE RISK", bool(options_risk)),
    ("KARAR", bool(decision)),
    ("İŞLEM", bool(trade_result)),
    ("FIRSAT RADARI", bool(opportunity_radar)),
]

for start in range(
    0,
    len(pipeline_items),
    6,
):
    row_items = pipeline_items[
        start:start + 6
    ]
    pipeline_cols = st.columns(
        len(row_items)
    )

    for col, (name, ok) in zip(
        pipeline_cols,
        row_items,
    ):
        with col:
            st.metric(
                name,
                "✅" if ok else "❌",
            )


# ============================================================
# MAIN DASHBOARD
# ============================================================

st.divider()
st.subheader("📡 FIRSAT RADARI — GÖLGE")

radar_action = normalize_text(
    opportunity_radar.get("action"),
    "BEKLE",
)
radar_status = normalize_text(
    opportunity_radar.get("status"),
    "UNAVAILABLE",
)
radar_side = normalize_text(
    opportunity_radar.get("side"),
    "NONE",
)
radar_features = safe_dict(
    opportunity_radar.get("features")
)
radar_range = safe_dict(
    opportunity_radar.get("range_gate")
)

if radar_action == "YATAY — İŞLEM YOK":
    st.warning("YATAY — İŞLEM YOK")
elif "ONAYLI ADAY" in radar_action:
    st.success(
        f"{radar_action} — NİHAİ PRODUCTION ONAYI GEREKLİ"
    )
elif "ADAY" in radar_action or radar_action == "ONAY BEKLE":
    st.info(radar_action)
elif radar_status in ("ERROR", "UNAVAILABLE"):
    st.error(
        "Fırsat Radarı kullanılamıyor: "
        + str(opportunity_radar.get("error", "Bilinmeyen hata"))
    )
else:
    st.caption("Radar yeni ve teyitli bir fırsat bekliyor.")

radar_cols = st.columns(6)
radar_cols[0].metric("Radar", radar_action)
radar_cols[1].metric("Yön", radar_side)
radar_cols[2].metric(
    "Aday Skoru",
    f"{safe_float(opportunity_radar.get('candidate_score')):.0f}/5",
)
radar_cols[3].metric(
    "Hacim Oranı",
    f"{safe_float(radar_features.get('volume_ratio')):.2f}",
)
radar_cols[4].metric(
    "Yatay Zayıflık",
    f"{safe_float(radar_range.get('weak_count')):.0f}/5",
)
radar_cols[5].metric(
    "Rejim",
    normalize_text(radar_range.get("regime"), "UNKNOWN"),
)

st.caption(
    "Bu panel gölge erken uyarıdır. Decision Engine ve Trade Manager "
    "kararlarını değiştirmez; tek başına pozisyon açtırmaz."
)

if market and display_decision:
    st.divider()

    price = safe_float(
        market.get("price"),
        0.0,
    )

    decision_action = normalize_text(
        display_decision.get("action"),
        "BEKLE",
    )

    trade_action = extract_trade_action(
        trade_result,
        display_decision,
    )

    final_action = (
        decision_action
        if display_decision.get(
            "test_mode",
            False,
        )
        else trade_action
    )

    real_signal = get_signal(
        display_decision
    )

    score = get_score(
        display_decision
    )

    confidence = safe_float(
        display_decision.get("confidence"),
        0.0,
    )

    decision_trend = normalize_text(
        display_decision.get("trend")
        or trend.get("trend_bias")
        or trend.get("trend"),
        "NEUTRAL",
    )

    sr_event = normalize_text(
        display_decision.get("sr_event")
        or support_resistance.get("event")
        or support_resistance.get("sr_event"),
        "NONE",
    )

    risk_level = normalize_text(
        display_decision.get("risk_level")
        or options_risk.get("risk_level"),
        "UNKNOWN",
    )

    trade_allowed = bool(
        display_decision.get(
            "trade_allowed",
            options_risk.get(
                "trade_allowed",
                True,
            ),
        )
    )

    pattern_name = normalize_text(
        pattern.get("pattern"),
        "NONE",
    )

    pattern_bias = normalize_text(
        pattern.get("bias")
        or pattern.get("final_signal"),
        "NEUTRAL",
    )

    gap_direction = normalize_text(
        gap.get("gap_direction")
        or gap.get("direction"),
        "NO_GAP",
    )

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    st.subheader(
        "🎯 NİHAİ İŞLEM KARARI"
    )

    if display_decision.get(
        "test_mode",
        False,
    ):
        st.warning(
            display_decision.get(
                "test_message",
                "TEST MODU AKTİF",
            )
        )
    else:
        st.success(
            "GERÇEK SİSTEM AKTİF"
        )

    if final_action in {
        "CALL AL",
        "CALL KORU",
    }:
        st.success(
            f"## 🟢 {final_action}"
        )

    elif final_action in {
        "PUT AL",
        "PUT KORU",
    }:
        st.error(
            f"## 🔴 {final_action}"
        )

    elif final_action in {
        "CALL KAPAT",
        "PUT KAPAT",
    }:
        st.warning(
            f"## ⛔ {final_action}"
        )

    else:
        st.info(
            "## 🟡 BEKLE"
        )

    st.info(
        display_decision.get(
            "reason",
            "Karar açıklaması yok.",
        )
    )

    # --------------------------------------------------------
    # PRIMARY METRICS
    # --------------------------------------------------------

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.metric(
            f"{symbol} FİYAT",
            f"{price:.2f}",
        )

    with c2:
        st.metric(
            "PİYASA YÖNÜ",
            f"{signal_icon(real_signal)} {real_signal}",
        )

    with c3:
        st.metric(
            "SON SKOR",
            f"{score:.1f}/100",
        )

    with c4:
        st.metric(
            "GÜVEN",
            f"{confidence:.1f}%",
        )

    with c5:
        st.metric(
            "0DTE RİSK",
            risk_level,
        )

    with c6:
        st.metric(
            "İŞLEME İZİN",
            "EVET" if trade_allowed else "HAYIR",
        )

    # --------------------------------------------------------
    # ENGINE STATE
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        "🧠 MOTORLARIN ORTAK KARAR DURUMU"
    )

    e1, e2, e3, e4, e5, e6 = st.columns(6)

    with e1:
        st.metric(
            "TREND",
            decision_trend,
            f"Skor {safe_float(trend.get('trend_score')):.0f}",
        )

    with e2:
        st.metric(
            "SIGNAL",
            normalize_text(
                signal.get("signal"),
                "NEUTRAL",
            ),
            f"Skor {safe_float(signal.get('score')):.0f}",
        )

    with e3:
        st.metric(
            "GAP",
            gap_direction,
            f"{safe_float(gap.get('gap_percent')):.3f}%",
        )

    with e4:
        st.metric(
            "S/R DURUMU",
            sr_event,
            f"Skor {safe_float(display_decision.get('sr_score')):.0f}",
        )

    with e5:
        st.metric(
            "PATTERN",
            pattern_name,
            pattern_bias,
        )

    with e6:
        st.metric(
            "POZİSYON",
            position_type,
            final_action,
        )

    # --------------------------------------------------------
    # CALL / PUT SCORE
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        "⚖️ CALL / PUT KARAR DENGESİ"
    )

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        st.metric(
            "CALL PUANI",
            f"{safe_float(display_decision.get('call_score')):.2f}",
        )

    with s2:
        st.metric(
            "PUT PUANI",
            f"{safe_float(display_decision.get('put_score')):.2f}",
        )

    with s3:
        st.metric(
            "CALL TEYİDİ",
            int(
                safe_float(
                    display_decision.get(
                        "call_confirmations"
                    )
                )
            ),
        )

    with s4:
        st.metric(
            "PUT TEYİDİ",
            int(
                safe_float(
                    display_decision.get(
                        "put_confirmations"
                    )
                )
            ),
        )

    # --------------------------------------------------------
    # TECHNICAL LEVELS
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        "📍 DESTEK / DİRENÇ SEVİYELERİ"
    )

    resistance_2 = safe_float(
        support_resistance.get(
            "resistance_2"
        )
    )

    resistance_1 = safe_float(
        support_resistance.get(
            "resistance_1",
            support_resistance.get(
                "resistance",
                0.0,
            ),
        )
    )

    support_1 = safe_float(
        support_resistance.get(
            "support_1",
            support_resistance.get(
                "support",
                0.0,
            ),
        )
    )

    support_2 = safe_float(
        support_resistance.get(
            "support_2"
        )
    )

    pivot = safe_float(
        support_resistance.get(
            "pivot"
        )
    )

    sr1, sr2, sr3, sr4, sr5 = st.columns(5)

    with sr1:
        st.metric(
            "🔴 DİRENÇ 2",
            f"{resistance_2:.2f}",
        )

    with sr2:
        st.metric(
            "🔴 DİRENÇ 1",
            f"{resistance_1:.2f}",
        )

    with sr3:
        st.metric(
            "⚖️ PIVOT",
            f"{pivot:.2f}",
        )

    with sr4:
        st.metric(
            "🟢 DESTEK 1",
            f"{support_1:.2f}",
        )

    with sr5:
        st.metric(
            "🟢 DESTEK 2",
            f"{support_2:.2f}",
        )

    # --------------------------------------------------------
    # BIG MOVE + REVERSAL
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        "⚠️ BÜYÜK HAREKET / DÖNÜŞ KORUMA KATMANI"
    )

    bm1, bm2, bm3, bm4 = st.columns(4)

    with bm1:
        st.metric(
            "BÜYÜK HAREKET RİSKİ",
            normalize_text(
                big_move_warning.get(
                    "risk_level"
                ),
                "LOW",
            ),
            (
                f"Skor "
                f"{safe_float(big_move_warning.get('warning_score')):.0f}"
            ),
        )

    with bm2:
        st.metric(
            "REVERSAL",
            normalize_text(
                reversal_confirmation.get(
                    "reversal_level"
                ),
                "NONE",
            ),
            (
                f"Skor "
                f"{safe_float(reversal_confirmation.get('reversal_score')):.0f}"
            ),
        )

    with bm3:
        st.metric(
            "GEÇ PUT BLOĞU",
            (
                "AKTİF"
                if reversal_confirmation.get(
                    "late_put_blocked"
                )
                else "PASİF"
            ),
            normalize_text(
                reversal_confirmation.get(
                    "event_role"
                ),
                "NO_EVENT",
            ),
        )

    with bm4:
        st.metric(
            "GÜÇLÜ CALL KORUMASI",
            (
                "AKTİF"
                if reversal_confirmation.get(
                    "hard_call_protection"
                )
                else "PASİF"
            ),
            normalize_text(
                reversal_confirmation.get(
                    "status"
                ),
                "UNKNOWN",
            ),
        )

    if reversal_confirmation.get(
        "late_put_blocked"
    ):
        st.warning(
            "⚠️ LATE PUT PROTECTION: "
            "Uzamış düşüş / dip bölgesinde "
            "yeni PUT girişi bloke edildi."
        )

    if reversal_confirmation.get(
        "hard_call_protection"
    ):
        st.success(
            "🛡️ HARD CALL PROTECTION aktif."
        )

    # --------------------------------------------------------
    # GAP + PATTERN + OPTIONS
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        "🔬 YAPISAL TEYİTLER"
    )

    y1, y2, y3 = st.columns(3)

    with y1:
        st.markdown("### GAP")
        st.write(
            f"**Yön:** {gap_direction}"
        )
        st.write(
            f"**Gap:** "
            f"{safe_float(gap.get('gap_percent')):.4f}%"
        )
        st.write(
            f"**Dolum:** "
            f"{safe_float(gap.get('gap_fill_percent')):.2f}%"
        )
        st.write(
            f"**Durum:** "
            f"{'DOLDU' if gap.get('gap_fill') else 'AÇIK'}"
        )
        st.write(
            f"**Sinyal:** "
            f"{gap.get('signal', 'NONE')}"
        )

    with y2:
        st.markdown("### PATTERN")
        st.write(
            f"**Pattern:** {pattern_name}"
        )
        st.write(
            f"**Bias:** {pattern_bias}"
        )
        st.write(
            f"**Skor:** "
            f"{safe_float(pattern.get('final_score', pattern.get('score'))):.0f}"
        )
        st.write(
            f"**Confidence:** "
            f"{safe_float(pattern.get('confidence')):.0f}%"
        )
        st.write(
            f"**Valid:** "
            f"{pattern.get('valid')}"
        )

    with y3:
        st.markdown("### OPSİYONLAR / 0DTE RİSKİ")
        st.write(
            f"**Opsiyon Puanı:** "
            f"{safe_float(options_data.get('final_score', options_data.get('score'))):.0f}"
        )
        st.write(
            f"**Opsiyon Sinyali:** "
            f"{options_data.get('signal', 'NONE')}"
        )
        st.write(
            f"**CALL Gücü:** "
            f"{safe_float(options_data.get('call_strength')):.0f}"
        )
        st.write(
            f"**PUT Gücü:** "
            f"{safe_float(options_data.get('put_strength')):.0f}"
        )
        st.write(
            f"**Risk:** {risk_level}"
        )
        st.write(
            f"**İşleme İzin:** "
            f"{'EVET' if trade_allowed else 'HAYIR'}"
        )

    # --------------------------------------------------------
    # POSITION MANAGEMENT
    # --------------------------------------------------------

    st.divider()
    st.subheader(
        "🎯 İŞLEM YÖNETİCİSİ / POZİSYON YÖNETİMİ"
    )

    tm_status = normalize_text(
        trade_result.get("status"),
        "UNKNOWN",
    )

    tm1, tm2, tm3 = st.columns(3)

    with tm1:
        st.metric(
            "KARAR MOTORU EYLEMİ",
            decision_action,
        )

    with tm2:
        st.metric(
            "İŞLEM YÖNETİCİSİ EYLEMİ",
            trade_action,
        )

    with tm3:
        st.metric(
            "İŞLEM YÖNETİCİSİ DURUMU",
            tm_status,
        )

    if trade_result.get("error"):
        st.warning(
            f"Trade Manager uyarısı: "
            f"{trade_result.get('error')}"
        )

    if position_type == "CALL":
        if final_action == "CALL KAPAT":
            st.error(
                "⛔ CALL POZİSYONUNU KAPAT"
            )
        else:
            st.success(
                "🟢 CALL POZİSYONU TAKİP EDİLİYOR"
            )

    elif position_type == "PUT":
        if final_action == "PUT KAPAT":
            st.error(
                "⛔ PUT POZİSYONUNU KAPAT"
            )
        else:
            st.success(
                "🔴 PUT POZİSYONU TAKİP EDİLİYOR"
            )

    else:
        st.info(
            "Açık pozisyon yok; sistem güvenli yeni giriş arıyor."
        )

    # --------------------------------------------------------
    # SESSION STATUS
    # --------------------------------------------------------

    st.divider()

    last_update = st.session_state.get(
        "last_update"
    )

    session_text = normalize_text(
        market.get("session"),
        "UNKNOWN",
    )

    market_open = bool(
        market.get("market_open")
    )

    status_cols = st.columns(4)

    with status_cols[0]:
        st.metric(
            "SESSION",
            session_text,
        )

    with status_cols[1]:
        st.metric(
            "MARKET",
            "AÇIK" if market_open else "KAPALI",
        )

    with status_cols[2]:
        st.metric(
            "VERİ KAYNAĞI",
            str(
                market.get(
                    "source",
                    "UNKNOWN",
                )
            ),
        )

    with status_cols[3]:
        st.metric(
            "SON GÜNCELLEME",
            (
                last_update.strftime("%H:%M:%S")
                if isinstance(
                    last_update,
                    datetime,
                )
                else "YOK"
            ),
        )


# ============================================================
# DEBUG INSPECTOR
# ============================================================

st.divider()

with st.expander(
    "🔍 SİSTEM TEKNİK DETAYLARI",
    expanded=False,
):
    debug = safe_dict(
        st.session_state.debug
    )

    if not debug:
        st.warning(
            "Debug verisi henüz oluşmadı."
        )

    else:
        sections = [
            ("1️⃣ MARKET DATA", "MARKET"),
            ("2️⃣ TREND ENGINE", "TREND"),
            ("3️⃣ GAP ENGINE", "GAP"),
            ("4️⃣ SIGNAL ENGINE", "SIGNAL"),
            ("5️⃣ SUPPORT / RESISTANCE", "SUPPORT_RESISTANCE"),
            ("6️⃣ PATTERN ENGINE", "PATTERN"),
            ("7️⃣ BIG MOVE WARNING", "BIG_MOVE_WARNING"),
            ("8️⃣ REVERSAL CONFIRMATION", "REVERSAL_CONFIRMATION"),
            ("9️⃣ OPTIONS CHAIN", "OPTIONS_DATA"),
            ("🔟 0DTE OPTIONS RISK", "OPTIONS_RISK"),
            ("1️⃣1️⃣ DECISION INPUT", "DECISION_INPUTS"),
            ("1️⃣2️⃣ DECISION OUTPUT", "DECISION_OUTPUT"),
            ("1️⃣3️⃣ TRADE MANAGER INPUT", "TRADE_MANAGER_INPUTS"),
            ("1️⃣4️⃣ TRADE MANAGER OUTPUT", "TRADE_MANAGER_OUTPUT"),
        ]

        for title, key in sections:
            st.subheader(title)
            st.json(
                debug.get(
                    key,
                    {},
                )
            )


# ============================================================
# AUTO REFRESH
# ============================================================

if auto_refresh:
    st.caption(
        f"🔄 Otomatik yenileme aktif: "
        f"{refresh_seconds} saniye"
    )

    time.sleep(
        refresh_seconds
    )

    st.rerun()
