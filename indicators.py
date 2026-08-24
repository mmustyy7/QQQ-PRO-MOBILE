# indicators.py

import pandas as pd
import numpy as np


def hesapla_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def hesapla_ema(close, period):
    return close.ewm(span=period, adjust=False).mean()


def hesapla_vwap(df):
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    volume = df["Volume"]
    return (typical_price * volume).cumsum() / volume.cumsum()


def hesapla_atr(df, period=14):
    """
    Piyasa ister 5 dolarlık ister 20 dolarlık hareketler yapsın,
    bant genişliğini ATR'ye göre dinamik ölçekler.
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def hesapla_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return macd, signal, histogram


def hesapla_hacim_orani(df, is_market_open=False):
    """
    Açılış anındaki (market open) ilk dakikalarda hacim çarpanını
    özel 'Açılış Volatilite Modu'na göre optimize eder.
    """
    if df is None or len(df) < 3:
        return 1.0

    son_hacim = df["Volume"].iloc[-1]
    rolling_window = min(10, len(df))
    ortalama = df["Volume"].rolling(rolling_window).mean().iloc[-1]

    if pd.isna(ortalama) or ortalama == 0:
        return 1.0

    faktor = float(son_hacim / ortalama)
    
    # Açılış modunda ani patlamaları daha hassas süzmek için ölçekleme
    if is_market_open:
        faktor = faktor * 0.85

    return faktor


def hesapla_hacim_yonu(df):
    temp = df.copy()
    temp["PriceChange"] = temp["Close"].diff()

    yesil = temp.loc[temp["PriceChange"] > 0, "Volume"].rolling(3).sum()
    kirmizi = temp.loc[temp["PriceChange"] < 0, "Volume"].rolling(3).sum()

    yesil = yesil.iloc[-1] if not yesil.empty and not pd.isna(yesil.iloc[-1]) else 0
    kirmizi = kirmizi.iloc[-1] if not kirmizi.empty and not pd.isna(kirmizi.iloc[-1]) else 1

    if kirmizi == 0:
        kirmizi = 1

    return yesil / kirmizi


def ema_trend(df):
    ema9 = hesapla_ema(df["Close"], 9)
    ema21 = hesapla_ema(df["Close"], 21)

    if ema9.iloc[-1] > ema21.iloc[-1]:
        return "BULLISH"
    elif ema9.iloc[-1] < ema21.iloc[-1]:
        return "BEARISH"

    return "SIDEWAYS"