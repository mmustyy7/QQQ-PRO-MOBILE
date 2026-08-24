import math


def calculate_delta(option_type, spot, strike):
    try:
        spot = float(spot)
        strike = float(strike)
    except (TypeError, ValueError):
        spot = 0.0
        strike = 0.0

    distance = abs(spot - strike)

    if distance < 1:
        delta = 0.50
    elif distance < 3:
        delta = 0.60
    elif distance <= 5:
        delta = 0.70
    else:
        delta = 0.80

    if str(option_type).upper() == "PUT":
        delta = -delta

    return round(delta, 2)


def calculate_gamma(spot, strike):
    try:
        spot = float(spot)
        strike = float(strike)
    except (TypeError, ValueError):
        spot = 0.0
        strike = 0.0

    distance = abs(spot - strike)
    # Uzak strike'larda 0.02'ye çakılı kalmaması için taban esnetildi
    gamma = max(0.005, 0.12 - distance * 0.015)
    return round(gamma, 3)


def calculate_theta(days=0):
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 0

    if days == 0:
        return -0.25
    if days <= 5:
        return -0.12
    return -0.05


def calculate_vega(iv=20):
    try:
        iv = float(iv)
    except (TypeError, ValueError):
        iv = 20.0
    return round(iv * 0.01, 2)


def get_greeks(option_type, spot, strike, iv=20, days=0):
    return {
        "Delta": calculate_delta(option_type, spot, strike),
        "Gamma": calculate_gamma(spot, strike),
        "Theta": calculate_theta(days),
        "Vega": calculate_vega(iv),
    }


# ===========================
# APP BAĞLANTI FONKSİYONU (Uyumlu İmza)
# ===========================

def calculate_greeks(symbol_or_type="CALL", spot=0, strike=0, iv=20, days=0):
    """
    app.py içinden hem sembol hem de opsiyon parametreleriyle çağrılabilmesi için esnekleştirildi.
    """
    # Sembol kontrolü: CALL/PUT haricindeki kısa stringler (NVDA, TSLA, IWM, QQQ vb.) sembol kabul edilir
    if isinstance(symbol_or_type, str) and symbol_or_type.upper() not in ["CALL", "PUT"] and len(symbol_or_type) <= 5:
        return {
            "delta": 0.55,
            "gamma": 0.08,
            "theta": -0.15,
            "vega": 0.20
        }
    
    res = get_greeks(symbol_or_type, spot, strike, iv, days)
    
    return {
        "delta": res.get("Delta", 0.5),
        "gamma": res.get("Gamma", 0.05),
        "theta": res.get("Theta", -0.1),
        "vega": res.get("Vega", 0.1)
    }