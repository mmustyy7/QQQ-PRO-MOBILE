# ==========================================
# QQQ PRO TRADING SUITE
# options_chain.py
# Güncellenmiş & Güvenli Sürüm
# ==========================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np


@st.cache_data(ttl=30)
def get_expirations(symbol="QQQ"):
    try:
        return yf.Ticker(symbol).options
    except Exception:
        return []


@st.cache_data(ttl=30)
def get_option_chain_data(symbol, expiration):
    try:
        chain = yf.Ticker(symbol).option_chain(expiration)
        return chain.calls, chain.puts
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


def nearest_strikes(df, price, count=12):
    if df is None:
        return pd.DataFrame()

    if df.empty:
        return df.copy()

    result = df.copy()

    if price is None:
        return result

    try:
        price = float(price)
    except (TypeError, ValueError):
        return result

    if not np.isfinite(price) or price <= 0:
        return result

    if "strike" not in result.columns:
        return result

    result["strike"] = pd.to_numeric(
        result["strike"],
        errors="coerce"
    )

    result = result.dropna(
        subset=["strike"]
    ).copy()

    if result.empty:
        return result

    result["distance"] = (
        result["strike"] - price
    ).abs()

    return (
        result
        .sort_values("distance", kind="stable")
        .head(count)
        .reset_index(drop=True)
    )


def calculate_approx_greeks(
    df,
    underlying_price,
    option_type="CALL"
):
    """
    Display-only approximation.
    Signal score içinde kullanılmaz.

    Güvenlik:
    - None underlying_price
    - 0 veya negatif fiyat
    - geçersiz DataFrame
    - geçersiz strike
    durumlarında güvenli şekilde geri döner.
    """

    if df is None:
        return pd.DataFrame()

    result = df.copy()

    if result.empty:
        return result

    if underlying_price is None:
        return result

    try:
        underlying_price = float(underlying_price)
    except (TypeError, ValueError):
        return result

    if not np.isfinite(underlying_price) or underlying_price <= 0:
        return result

    if "strike" not in result.columns:
        return result

    strikes = pd.to_numeric(
        result["strike"],
        errors="coerce"
    )

    valid_strikes = strikes.notna()

    if not valid_strikes.any():
        return result

    diff = (
        strikes - underlying_price
    ) / underlying_price

    option_type = str(
        option_type
    ).upper().strip()

    if option_type == "CALL":
        approx_delta = (
            0.5 - diff * 5
        ).clip(0.01, 0.99)
    else:
        approx_delta = -(
            0.5 + diff * 5
        ).clip(0.01, 0.99)

    result["approx_delta"] = (
        pd.to_numeric(
            approx_delta,
            errors="coerce"
        )
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    gamma_denominator = (
        2 *
        (underlying_price * 0.005) ** 2
    )

    if gamma_denominator > 0:
        approx_gamma = (
            np.exp(
                -(
                    (strikes - underlying_price) ** 2
                ) /
                gamma_denominator
            ) *
            0.1
        )
    else:
        approx_gamma = 0.0

    result["approx_gamma"] = (
        pd.to_numeric(
            approx_gamma,
            errors="coerce"
        )
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    return result


# ============================================================
# OPTION INTELLIGENCE ENGINE
# 0DTE CALL / PUT GÜÇ ANALİZİ
# ============================================================
def analyze_option_strength(
    calls,
    puts,
    price
):
    result = {
        "call_strength": 50,
        "put_strength": 50,
        "recommended_side": "NONE",
        "best_call_strike": None,
        "best_put_strike": None,
        "delta_target": 0.45,
        "gamma_wall": None,
        "put_wall": None,
        "call_resistance_low": None,
        "call_resistance_high": None,
        "put_support_low": None,
        "put_support_high": None,
        "gamma_wall_strength": 0,
        "put_wall_strength": 0,
        "wall_bias": "BETWEEN_WALLS",
        "iv_status": "NORMAL"
    }

    if (
        calls is None
        or puts is None
        or calls.empty
        or puts.empty
        or price is None
    ):
        return result

    try:
        price = float(price)
    except (TypeError, ValueError):
        return result

    if not np.isfinite(price) or price <= 0:
        return result

    calls = calls.copy()
    puts = puts.copy()

    required_columns = [
        "strike",
        "volume",
        "openInterest"
    ]

    for frame in (calls, puts):

        for column in required_columns:
            if column not in frame.columns:
                frame[column] = 0.0

        frame["strike"] = pd.to_numeric(
            frame["strike"],
            errors="coerce"
        ).fillna(0.0)

        frame["volume"] = pd.to_numeric(
            frame["volume"],
            errors="coerce"
        ).fillna(0.0)

        frame["openInterest"] = pd.to_numeric(
            frame["openInterest"],
            errors="coerce"
        ).fillna(0.0)

    calls = calls[
        calls["strike"] > 0
    ].copy()

    puts = puts[
        puts["strike"] > 0
    ].copy()

    if calls.empty or puts.empty:
        return result

    # -------------------------------------------------
    # Volume / Open Interest Analizi
    # -------------------------------------------------
    calls["volume_oi_ratio"] = (
        calls["volume"] /
        calls["openInterest"].replace(0, 1)
    )

    puts["volume_oi_ratio"] = (
        puts["volume"] /
        puts["openInterest"].replace(0, 1)
    )

    # -------------------------------------------------
    # Ağırlıklı Gamma Wall & Put Wall
    # -------------------------------------------------
    top_calls = calls.nlargest(
        5,
        "openInterest"
    )

    top_puts = puts.nlargest(
        5,
        "openInterest"
    )

    if (
        not top_calls.empty
        and top_calls["openInterest"].sum() > 0
    ):
        result["gamma_wall"] = float(
            np.average(
                top_calls["strike"].to_numpy(dtype=float),
                weights=top_calls["openInterest"].to_numpy(dtype=float)
            )
        )

        result["gamma_wall_strength"] = int(
            top_calls["openInterest"].sum()
        )

    if (
        not top_puts.empty
        and top_puts["openInterest"].sum() > 0
    ):
        result["put_wall"] = float(
            np.average(
                top_puts["strike"].to_numpy(dtype=float),
                weights=top_puts["openInterest"].to_numpy(dtype=float)
            )
        )

        result["put_wall_strength"] = int(
            top_puts["openInterest"].sum()
        )

    # -------------------------------------------------
    # Wall Bölgeleri
    # -------------------------------------------------
    wall_range = price * 0.003

    if result["gamma_wall"] is not None:
        result["call_resistance_low"] = (
            result["gamma_wall"] - wall_range
        )

        result["call_resistance_high"] = (
            result["gamma_wall"] + wall_range
        )

    if result["put_wall"] is not None:
        result["put_support_low"] = (
            result["put_wall"] - wall_range
        )

        result["put_support_high"] = (
            result["put_wall"] + wall_range
        )

    # -------------------------------------------------
    # Wall Bias
    # -------------------------------------------------
    if (
        result["gamma_wall"] is not None
        and abs(price - result["gamma_wall"]) / price < 0.003
    ):
        result["wall_bias"] = "PRICE_NEAR_CALL_WALL"

    elif (
        result["put_wall"] is not None
        and abs(price - result["put_wall"]) / price < 0.003
    ):
        result["wall_bias"] = "PRICE_NEAR_PUT_WALL"

    else:
        result["wall_bias"] = "BETWEEN_WALLS"

    # -------------------------------------------------
    # CALL SCORE
    # -------------------------------------------------
    calls["score"] = (
        calls["volume"].rank(pct=True).fillna(0).astype(float) * 30
        +
        calls["openInterest"].rank(pct=True).fillna(0).astype(float) * 30
        +
        (
            1 -
            abs(calls["strike"] - price) / price
        ).clip(0, 1).astype(float) * 20
    )

    calls.loc[
        calls["volume_oi_ratio"].between(
            0.30,
            1.50
        ),
        "score"
    ] += 20.0

    calls.loc[
        calls["volume_oi_ratio"] > 3,
        "score"
    ] -= 10.0

    calls.loc[
        calls["volume_oi_ratio"] < 0.10,
        "score"
    ] -= 10.0

    calls["score"] = pd.to_numeric(
        calls["score"],
        errors="coerce"
    ).fillna(0.0).astype(float)

    if not calls.empty:

        best_call = calls.sort_values(
            "score",
            ascending=False
        ).iloc[0]

        result["best_call_strike"] = float(
            best_call["strike"]
        )

        call_strength = float(
            calls["score"].mean()
        )

    else:
        call_strength = 50.0

    # -------------------------------------------------
    # PUT SCORE
    # -------------------------------------------------
    puts["score"] = (
        puts["volume"].rank(pct=True).fillna(0).astype(float) * 30
        +
        puts["openInterest"].rank(pct=True).fillna(0).astype(float) * 30
        +
        (
            1 -
            abs(puts["strike"] - price) / price
        ).clip(0, 1).astype(float) * 20
    )

    puts.loc[
        puts["volume_oi_ratio"].between(
            0.30,
            1.50
        ),
        "score"
    ] += 20.0

    puts.loc[
        puts["volume_oi_ratio"] > 3,
        "score"
    ] -= 10.0

    puts.loc[
        puts["volume_oi_ratio"] < 0.10,
        "score"
    ] -= 10.0

    puts["score"] = pd.to_numeric(
        puts["score"],
        errors="coerce"
    ).fillna(0.0).astype(float)

    if not puts.empty:

        best_put = puts.sort_values(
            "score",
            ascending=False
        ).iloc[0]

        result["best_put_strike"] = float(
            best_put["strike"]
        )

        put_strength = float(
            puts["score"].mean()
        )

    else:
        put_strength = 50.0

    result["call_strength"] = int(
        min(
            100,
            max(
                0,
                round(call_strength)
            )
        )
    )

    result["put_strength"] = int(
        min(
            100,
            max(
                0,
                round(put_strength)
            )
        )
    )

    # -------------------------------------------------
    # YÖN KARARI
    # -------------------------------------------------
    if call_strength > put_strength + 10:
        result["recommended_side"] = "CALL"

    elif put_strength > call_strength + 10:
        result["recommended_side"] = "PUT"

    else:
        result["recommended_side"] = "NEUTRAL"

    return result


# ============================================================
# 0DTE STRIKE SELECTOR
# ============================================================
def select_best_contract(
    chain,
    price,
    direction="CALL"
):
    if (
        chain is None
        or chain.empty
        or price is None
    ):
        return {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Veri yok"
        }

    try:
        price = float(price)
    except (TypeError, ValueError):
        return {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Geçersiz fiyat"
        }

    if not np.isfinite(price) or price <= 0:
        return {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Geçersiz fiyat"
        }

    df = chain.copy()

    required_columns = [
        "strike",
        "volume",
        "openInterest"
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = 0.0

    df["strike"] = pd.to_numeric(
        df["strike"],
        errors="coerce"
    )

    df["volume"] = pd.to_numeric(
        df["volume"],
        errors="coerce"
    ).fillna(0.0)

    df["openInterest"] = pd.to_numeric(
        df["openInterest"],
        errors="coerce"
    ).fillna(0.0)

    df = df.dropna(
        subset=["strike"]
    ).copy()

    if df.empty:
        return {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Uygun kontrat bulunamadı"
        }

    # -------------------------------------------------
    # 1. ATM Yakınlık Skoru
    # -------------------------------------------------
    df["distance_pct"] = (
        abs(df["strike"] - price) /
        price
    ).astype(float)

    df["atm_score"] = (
        1 -
        df["distance_pct"]
    ).clip(0, 1).astype(float) * 20.0

    # -------------------------------------------------
    # 2. Yaklaşık Delta
    # -------------------------------------------------
    direction = str(
        direction
    ).upper().strip()

    if direction == "CALL":

        df["delta"] = (
            0.50 -
            (
                (df["strike"] - price) /
                price *
                5
            )
        ).clip(0.05, 0.95)

    else:

        df["delta"] = -(
            0.50 +
            (
                (df["strike"] - price) /
                price *
                5
            )
        ).clip(0.05, 0.95)

    df["delta"] = pd.to_numeric(
        df["delta"],
        errors="coerce"
    ).fillna(0.0).astype(float)

    # -------------------------------------------------
    # 3. Delta Skoru
    # KRİTİK DÜZELTME:
    # delta_score artık float olarak başlatılıyor.
    # Böylece pandas 3.12 / yeni pandas sürümünde
    # float dizi int64 kolona yazılırken hata oluşmaz.
    # -------------------------------------------------
    df["delta_score"] = 0.0

    ideal = df["delta"].abs().between(
        0.35,
        0.55
    )

    df.loc[
        ideal,
        "delta_score"
    ] = 15.0

    non_ideal_score = (
        15.0 -
        abs(
            df["delta"].abs() -
            0.45
        ) *
        40.0
    ).clip(0, 15)

    df.loc[
        ~ideal,
        "delta_score"
    ] = non_ideal_score.loc[
        ~ideal
    ].astype(float)

    df["delta_score"] = pd.to_numeric(
        df["delta_score"],
        errors="coerce"
    ).fillna(0.0).astype(float)

    # -------------------------------------------------
    # 4. Volume Skoru
    # -------------------------------------------------
    df["volume_score"] = (
        df["volume"]
        .rank(pct=True)
        .fillna(0.0)
        .astype(float)
    ) * 15.0

    # -------------------------------------------------
    # 5. Open Interest Skoru
    # -------------------------------------------------
    df["oi_score"] = (
        df["openInterest"]
        .rank(pct=True)
        .fillna(0.0)
        .astype(float)
    ) * 15.0

    # -------------------------------------------------
    # 6. Volume / OI Skoru
    # -------------------------------------------------
    df["volume_oi_ratio"] = (
        df["volume"] /
        df["openInterest"].replace(
            0,
            1
        )
    )

    df["volume_oi_ratio"] = pd.to_numeric(
        df["volume_oi_ratio"],
        errors="coerce"
    ).replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(0.0).astype(float)

    df["ratio_score"] = 5.0

    df.loc[
        df["volume_oi_ratio"].between(
            0.3,
            1.5
        ),
        "ratio_score"
    ] = 10.0

    df.loc[
        df["volume_oi_ratio"] > 3,
        "ratio_score"
    ] = 2.0

    df["ratio_score"] = pd.to_numeric(
        df["ratio_score"],
        errors="coerce"
    ).fillna(5.0).astype(float)

    # -------------------------------------------------
    # 7. Bid / Ask Spread Skoru
    # -------------------------------------------------
    if "ask" not in df.columns:
        df["ask"] = 0.0

    if "bid" not in df.columns:
        df["bid"] = 0.0

    df["ask"] = pd.to_numeric(
        df["ask"],
        errors="coerce"
    ).fillna(0.0).astype(float)

    df["bid"] = pd.to_numeric(
        df["bid"],
        errors="coerce"
    ).fillna(0.0).astype(float)

    df["spread"] = (
        df["ask"] -
        df["bid"]
    ).clip(lower=0.0).astype(float)

    df["spread_pct"] = (
        df["spread"] /
        df["ask"].replace(
            0,
            1
        )
    ).astype(float)

    df["spread_score"] = (
        15.0 -
        df["spread_pct"] *
        100.0
    ).clip(0, 15).astype(float)

    # -------------------------------------------------
    # 8. IV Skoru
    # -------------------------------------------------
    if "impliedVolatility" not in df.columns:
        df["impliedVolatility"] = 0.20

    df["impliedVolatility"] = pd.to_numeric(
        df["impliedVolatility"],
        errors="coerce"
    ).fillna(0.20).astype(float)

    df["iv_score"] = 5.0

    df.loc[
        df["impliedVolatility"] > 0.80,
        "iv_score"
    ] = 2.0

    df.loc[
        df["impliedVolatility"] < 0.15,
        "iv_score"
    ] = 2.0

    # -------------------------------------------------
    # 9. Yaklaşık Gamma Skoru
    # -------------------------------------------------
    gamma_denominator = (
        2 *
        (price * 0.005) ** 2
    )

    if gamma_denominator > 0:

        df["gamma_score"] = (
            np.exp(
                -(
                    (df["strike"] - price) ** 2
                ) /
                gamma_denominator
            )
        ) * 5.0

    else:
        df["gamma_score"] = 0.0

    df["gamma_score"] = pd.to_numeric(
        df["gamma_score"],
        errors="coerce"
    ).replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(0.0).astype(float)

    # -------------------------------------------------
    # 10. Nihai Kontrat Skoru
    # -------------------------------------------------
    df["contract_score"] = (
          df["atm_score"].astype(float)
        + df["delta_score"].astype(float)
        + df["volume_score"].astype(float)
        + df["oi_score"].astype(float)
        + df["ratio_score"].astype(float)
        + df["spread_score"].astype(float)
        + df["iv_score"].astype(float)
        + df["gamma_score"].astype(float)
    )

    df["contract_score"] = pd.to_numeric(
        df["contract_score"],
        errors="coerce"
    ).replace(
        [np.inf, -np.inf],
        np.nan
    ).astype(float)

    valid_scores = df[
        "contract_score"
    ].dropna()

    if valid_scores.empty:
        return {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Uygun kontrat bulunamadı"
        }

    best_index = valid_scores.idxmax()

    if pd.isna(best_index):
        return {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Uygun kontrat bulunamadı"
        }

    best = df.loc[best_index]

    try:
        strike = float(best["strike"])
    except (TypeError, ValueError):
        strike = None

    try:
        delta = float(best["delta"])
    except (TypeError, ValueError):
        delta = 0.0

    try:
        volume = int(float(best["volume"]))
    except (TypeError, ValueError):
        volume = 0

    try:
        open_interest = int(
            float(best["openInterest"])
        )
    except (TypeError, ValueError):
        open_interest = 0

    return {
        "strike": strike,
        "delta": delta,
        "volume": volume,
        "open_interest": open_interest,
        "reason": (
            f"{direction} için çok kriterli "
            "optimize kontrat"
        )
    }


# ============================================================
# TRADE EXECUTION FILTER
# 0DTE KONTRAT KALİTE KONTROLÜ
# ============================================================
def evaluate_contract_quality(contract):
    result = {
        "trade_allowed": False,
        "quality_score": 50,
        "risk": "ORTA",
        "reason": []
    }

    if not contract:
        result["reason"].append(
            "Kontrat verisi yok"
        )
        return result

    score = 50

    try:
        volume = float(
            contract.get("volume", 0) or 0
        )
    except (TypeError, ValueError):
        volume = 0.0

    try:
        oi = float(
            contract.get("open_interest", 0) or 0
        )
    except (TypeError, ValueError):
        oi = 0.0

    if volume >= 1000:
        score += 15
        result["reason"].append(
            "Hacim güçlü"
        )

    elif volume < 100:
        score -= 15
        result["reason"].append(
            "Hacim zayıf"
        )

    if oi >= 500:
        score += 15
        result["reason"].append(
            "OI yeterli"
        )

    elif oi < 100:
        score -= 10
        result["reason"].append(
            "OI düşük"
        )

    score = max(
        0,
        min(
            100,
            score
        )
    )

    result["quality_score"] = score

    if score >= 70:
        result["trade_allowed"] = True
        result["risk"] = "DÜŞÜK"

    elif score >= 50:
        result["trade_allowed"] = True
        result["risk"] = "ORTA"

    else:
        result["trade_allowed"] = False
        result["risk"] = "YÜKSEK"

    return result


# ============================================================
# OPTIONS CHAIN
# ============================================================
def get_options_chain(
    symbol="QQQ",
    current_price=None
):
    try:
        expirations = get_expirations(
            symbol
        )

        if not expirations:
            return (
                pd.DataFrame(),
                pd.DataFrame(),
                ""
            )

        expiry = expirations[0]

        calls, puts = get_option_chain_data(
            symbol,
            expiry
        )

        if (
            calls is None
            or puts is None
            or calls.empty
            or puts.empty
        ):
            return (
                pd.DataFrame(),
                pd.DataFrame(),
                expiry
            )

        columns = [
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "volume",
            "openInterest",
            "impliedVolatility"
        ]

        calls = calls.copy()
        puts = puts.copy()

        for frame in (calls, puts):

            for column in columns:

                if column not in frame.columns:
                    frame[column] = 0.0

        calls = calls[
            columns
        ].copy()

        puts = puts[
            columns
        ].copy()

        if current_price is not None:

            try:
                current_price = float(
                    current_price
                )
            except (TypeError, ValueError):
                current_price = None

        if (
            current_price is not None
            and np.isfinite(current_price)
            and current_price > 0
        ):

            calls = calculate_approx_greeks(
                nearest_strikes(
                    calls,
                    current_price
                ),
                current_price,
                "CALL"
            )

            puts = calculate_approx_greeks(
                nearest_strikes(
                    puts,
                    current_price
                ),
                current_price,
                "PUT"
            )

        return (
            calls,
            puts,
            expiry
        )

    except Exception:
        return (
            pd.DataFrame(),
            pd.DataFrame(),
            ""
        )


# ============================================================
# OPTIONS ANALYSIS
# ============================================================
@st.cache_data(ttl=30)
def analyze_options_chain(
    symbol="QQQ"
):
    try:
        ticker = yf.Ticker(
            symbol
        )

        history = ticker.history(
            period="5d",
            interval="1m"
        )

        if (
            history is None
            or history.empty
            or "Close" not in history.columns
        ):
            price = None

        else:

            close = pd.to_numeric(
                history["Close"],
                errors="coerce"
            ).dropna()

            price = (
                float(close.iloc[-1])
                if not close.empty
                else None
            )

        calls, puts, expiry = get_options_chain(
            symbol,
            price
        )

        if calls.empty or puts.empty:
            return default_options_response(
                "Option chain is empty"
            )

        intelligence = analyze_option_strength(
            calls,
            puts,
            price
        )

        call_contract = select_best_contract(
            calls,
            price,
            "CALL"
        )

        put_contract = select_best_contract(
            puts,
            price,
            "PUT"
        )

        call_quality = evaluate_contract_quality(
            call_contract
        )

        put_quality = evaluate_contract_quality(
            put_contract
        )

        call_volume = pd.to_numeric(
            calls["volume"],
            errors="coerce"
        ).fillna(0).sum()

        put_volume = pd.to_numeric(
            puts["volume"],
            errors="coerce"
        ).fillna(0).sum()

        call_oi = pd.to_numeric(
            calls["openInterest"],
            errors="coerce"
        ).fillna(0).sum()

        put_oi = pd.to_numeric(
            puts["openInterest"],
            errors="coerce"
        ).fillna(0).sum()

        pc_volume = (
            float(
                put_volume /
                call_volume
            )
            if call_volume > 0
            else 1.0
        )

        pc_oi = (
            float(
                put_oi /
                call_oi
            )
            if call_oi > 0
            else 1.0
        )

        score = 50.0

        if intelligence[
            "recommended_side"
        ] == "CALL":

            score += 10.0

        elif intelligence[
            "recommended_side"
        ] == "PUT":

            score -= 10.0

        score += (
            intelligence[
                "call_strength"
            ] - 50
        ) * 0.30

        score -= (
            intelligence[
                "put_strength"
            ] - 50
        ) * 0.30

        if call_quality[
            "trade_allowed"
        ]:
            score += 5.0

        if put_quality[
            "trade_allowed"
        ]:
            score -= 5.0

        score = max(
            0,
            min(
                100,
                int(score)
            )
        )

        if score >= 60:
            signal = "CALL OPTION FLOW"

        elif score <= 40:
            signal = "PUT OPTION FLOW"

        else:
            signal = "BALANCED OPTION FLOW"

        return {
            "score": score,
            "final_score": score,
            "signal": signal,
            "expiry_date": expiry,
            "call_volume": int(call_volume),
            "put_volume": int(put_volume),
            "pc_volume_ratio": round(
                pc_volume,
                2
            ),
            "pc_oi_ratio": round(
                pc_oi,
                2
            ),
            "call_strength": intelligence[
                "call_strength"
            ],
            "put_strength": intelligence[
                "put_strength"
            ],
            "recommended_side": intelligence[
                "recommended_side"
            ],
            "best_call_strike": intelligence[
                "best_call_strike"
            ],
            "best_put_strike": intelligence[
                "best_put_strike"
            ],
            "delta_target": intelligence[
                "delta_target"
            ],
            "gamma_wall": intelligence[
                "gamma_wall"
            ],
            "put_wall": intelligence[
                "put_wall"
            ],
            "call_resistance_low": intelligence[
                "call_resistance_low"
            ],
            "call_resistance_high": intelligence[
                "call_resistance_high"
            ],
            "put_support_low": intelligence[
                "put_support_low"
            ],
            "put_support_high": intelligence[
                "put_support_high"
            ],
            "gamma_wall_strength": intelligence[
                "gamma_wall_strength"
            ],
            "put_wall_strength": intelligence[
                "put_wall_strength"
            ],
            "wall_bias": intelligence[
                "wall_bias"
            ],
            "iv_status": intelligence[
                "iv_status"
            ],
            "recommended_call": call_contract,
            "recommended_put": put_contract,
            "call_quality": call_quality,
            "put_quality": put_quality,
            "comment": (
                "0DTE Option Intelligence aktif "
                "(Çok kriterli seçim & Ağırlıklı "
                "Walls & Destek/Direnç Seviyeleri)."
            )
        }

    except Exception as error:

        return default_options_response(
            str(error)
        )


# ============================================================
# DEFAULT RESPONSE
# ============================================================
def default_options_response(
    error=""
):
    return {
        "score": 50,
        "final_score": 50,
        "signal": "NO OPTION DATA",
        "expiry_date": "",
        "call_volume": 0,
        "put_volume": 0,
        "pc_volume_ratio": 1.0,
        "pc_oi_ratio": 1.0,
        "call_strength": 50,
        "put_strength": 50,
        "recommended_side": "NONE",
        "best_call_strike": None,
        "best_put_strike": None,
        "delta_target": 0.45,
        "gamma_wall": None,
        "put_wall": None,
        "call_resistance_low": None,
        "call_resistance_high": None,
        "put_support_low": None,
        "put_support_high": None,
        "gamma_wall_strength": 0,
        "put_wall_strength": 0,
        "wall_bias": "BETWEEN_WALLS",
        "iv_status": "NORMAL",
        "recommended_call": {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Veri yok"
        },
        "recommended_put": {
            "strike": None,
            "delta": 0,
            "volume": 0,
            "open_interest": 0,
            "reason": "Veri yok"
        },
        "call_quality": {
            "trade_allowed": False,
            "quality_score": 50,
            "risk": "ORTA",
            "reason": ["Veri yok"]
        },
        "put_quality": {
            "trade_allowed": False,
            "quality_score": 50,
            "risk": "ORTA",
            "reason": ["Veri yok"]
        },
        "comment": (
            error
            if error
            else "Veri bulunamadı"
        )
    }