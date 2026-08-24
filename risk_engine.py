"""
QQQ PRO v4
RISK ENGINE

Görev:
- İşlem risk kontrolü
- Pozisyon büyüklüğü hesaplama
- ATR bazlı risk mesafesi
- Risk/Reward kontrolü

Emir göndermez.
Sadece risk kararı üretir.
"""


def safe_float(value, default=0):

    try:
        return float(value)
    except:
        return default


def calculate_risk_distance(price, atr):

    price = safe_float(price)
    atr = safe_float(atr)

    if price <= 0:
        return 0

    atr_risk = atr * 0.75
    percent_risk = price * 0.0025

    return max(
        atr_risk,
        percent_risk
    )


def calculate_position_size(
    account_balance,
    risk_percent,
    stop_distance
):

    balance = safe_float(account_balance)
    risk = safe_float(risk_percent)
    stop = safe_float(stop_distance)

    if balance <= 0:
        return 0

    if risk <= 0:
        return 0

    if stop <= 0:
        return 0

    risk_amount = balance * (risk / 100)

    size = risk_amount / stop

    if size <= 0:
        return 0

    return round(size, 2)


def check_risk_reward(
    entry,
    stop,
    target,
    signal=None
):

    # --------------------------------------------------------
    # RAW VALUE VALIDATION
    # --------------------------------------------------------

    if entry is None or stop is None or target is None:
        return {
            "valid": False,
            "reason": "Eksik giriş/stop/hedef fiyatı."
        }

    entry = safe_float(entry, None)
    stop = safe_float(stop, None)
    target = safe_float(target, None)

    if entry is None or stop is None or target is None:
        return {
            "valid": False,
            "reason": "Geçersiz fiyat verisi."
        }

    if entry <= 0:
        return {
            "valid": False,
            "reason": "Geçersiz giriş fiyatı."
        }

    if stop <= 0:
        return {
            "valid": False,
            "reason": "Geçersiz stop fiyatı."
        }

    if target <= 0:
        return {
            "valid": False,
            "reason": "Geçersiz hedef fiyatı."
        }

    # --------------------------------------------------------
    # STOP DISTANCE
    # --------------------------------------------------------

    risk = abs(entry - stop)

    if risk <= 0:
        return {
            "valid": False,
            "reason": "Stop mesafesi yok."
        }

    # --------------------------------------------------------
    # SIGNAL NORMALIZATION
    # --------------------------------------------------------

    normalized_signal = None

    if signal is not None:

        normalized_signal = str(signal).strip().upper()

        if normalized_signal not in [
            "CALL",
            "PUT"
        ]:
            return {
                "valid": False,
                "risk": round(risk, 2),
                "reward": 0,
                "ratio": 0,
                "reason": "Geçersiz işlem yönü."
            }

    # --------------------------------------------------------
    # DIRECTION VALIDATION
    #
    # CALL:
    # STOP < ENTRY < TARGET
    #
    # PUT:
    # TARGET < ENTRY < STOP
    #
    # signal verilmemiş eski çağrılarda yön,
    # stop ve target'ın entry'nin iki tarafında
    # bulunmasından güvenli şekilde belirlenir.
    # --------------------------------------------------------

    if normalized_signal == "CALL":

        if not (
            stop < entry < target
        ):
            return {
                "valid": False,
                "risk": round(risk, 2),
                "reward": 0,
                "ratio": 0,
                "reason": "CALL için stop/hedef yönü geçersiz."
            }

    elif normalized_signal == "PUT":

        if not (
            target < entry < stop
        ):
            return {
                "valid": False,
                "risk": round(risk, 2),
                "reward": 0,
                "ratio": 0,
                "reason": "PUT için stop/hedef yönü geçersiz."
            }

    else:

        call_direction = (
            stop < entry < target
        )

        put_direction = (
            target < entry < stop
        )

        if not (
            call_direction or put_direction
        ):
            return {
                "valid": False,
                "risk": round(risk, 2),
                "reward": 0,
                "ratio": 0,
                "reason": "Stop/hedef yönü geçersiz veya belirsiz."
            }

    # --------------------------------------------------------
    # REWARD
    # --------------------------------------------------------

    reward = abs(target - entry)

    if reward <= 0:
        return {
            "valid": False,
            "risk": round(risk, 2),
            "reward": round(reward, 2),
            "ratio": 0,
            "reason": "Hedef mesafesi yok."
        }

    # --------------------------------------------------------
    # RISK / REWARD
    # --------------------------------------------------------

    ratio = reward / risk

    valid = ratio >= 1.2

    return {

        "valid": valid,

        "risk": round(risk, 2),

        "reward": round(reward, 2),

        "ratio": round(ratio, 2),

        "reason":
            "Risk/ödül uygun."
            if valid
            else
            "Risk/ödül yetersiz."
    }


def validate_trade(
    signal,
    confidence,
    final_score,
    risk_reward
):

    confidence = safe_float(confidence)
    score = safe_float(final_score)

    confidence = max(
        0,
        min(confidence, 100)
    )

    score = max(
        0,
        min(score, 100)
    )

    if signal not in [
        "CALL",
        "PUT"
    ]:

        return {
            "allowed": False,
            "reason": "Geçersiz sinyal."
        }

    if confidence < 60:

        return {
            "allowed": False,
            "reason": "Confidence düşük."
        }

    if signal == "CALL" and score < 60:

        return {
            "allowed": False,
            "reason": "CALL skoru yetersiz."
        }

    if signal == "PUT" and score > 40:

        return {
            "allowed": False,
            "reason": "PUT skoru yetersiz."
        }

    if not isinstance(
        risk_reward,
        dict
    ):

        return {
            "allowed": False,
            "reason": "Risk/ödül verisi yok."
        }

    if not risk_reward.get(
        "valid",
        False
    ):

        return {
            "allowed": False,
            "reason": "Risk/ödül uygun değil."
        }

    return {
        "allowed": True,
        "reason": "Risk kriterleri uygun."
    }