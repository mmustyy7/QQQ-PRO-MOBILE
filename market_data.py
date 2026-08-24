# ============================================================
# QQQ PRO
# market_data.py
#
# MASTER MARKET DATA PROVIDER
#
# GÖREVİ:
# - QQQ piyasa verisini almak
# - 1m / 5m / 15m verilerini standartlaştırmak
# - Veri kalitesini kontrol etmek
# - Güncel fiyatı sağlamak
# - Diğer motorlara TEK tip market_data sözlüğü vermek
#
# BU DOSYANIN GÖREVİ DEĞİL:
# - Trend hesaplamak
# - Sinyal üretmek
# - CALL / PUT kararı vermek
# - Destek / direnç hesaplamak
# - RSI / VWAP / EMA üretmek
#
# VERİ AKIŞI:
#
# Yahoo Finance
#      ↓
# market_data.py
#      ↓
# standart market sözlüğü
#      ↓
# trend_engine
# support_resistance
# signal_engine
# decision_engine
#
# ============================================================

import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_SYMBOL = "QQQ"

TIMEFRAMES = {
    "1m": {
        "interval": "1m",
        "period": "1d",
    },
    "5m": {
        "interval": "5m",
        "period": "5d",
    },
    "15m": {
        "interval": "15m",
        "period": "1mo",
    },
}

REQUIRED_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
]

MAX_RETRY = 3
RETRY_DELAY = 1

NEW_YORK_TZ = ZoneInfo("America/New_York")


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value, default=0.0):
    """
    Güvenli float dönüşümü.

    None, NaN, hatalı veya dönüştürülemeyen değerlerde
    default döndürür.
    """

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

            value = value.iloc[-1, 0]

        if pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default


# ============================================================
# EVENT LOOP SAFETY
# ============================================================

def _ensure_event_loop():
    """
    Streamlit / Python ortamlarında oluşabilecek
    event loop problemlerine karşı güvenli kontrol.
    """

    try:
        loop = asyncio.get_event_loop()

        if loop.is_closed():
            raise RuntimeError("Event loop is closed")

    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


# ============================================================
# EMPTY MARKET DATA
# ============================================================

def _empty_market_data(symbol=DEFAULT_SYMBOL):
    """
    Hata durumunda her zaman aynı veri yapısının dönmesini sağlar.

    Böylece diğer motorlarda:
        market.get(...)
    çağrıları güvenli kalır.
    """

    now = datetime.now()

    return {
        "symbol": symbol,

        "timestamp": now,
        "last_update": now,

        "source": "Yahoo Finance",

        "price": 0.0,
        "volume": 0,

        "df_1m": pd.DataFrame(),
        "df_5m": pd.DataFrame(),
        "df_15m": pd.DataFrame(),

        "data_ok": False,
        "market_open": False,

        "session": "CLOSED",

        "health": {
            "status": "ERROR",
            "price": False,
            "1m": False,
            "5m": False,
            "15m": False,
        },
    }


# ============================================================
# YAHOO MULTIINDEX CLEANER
# ============================================================

def _flatten_columns(df):
    """
    Yahoo Finance bazı durumlarda MultiIndex kolon döndürür.

    Örneğin:

        ('Open', 'QQQ')
        ('High', 'QQQ')

    gibi yapıları standart kolonlara çevirir.
    """

    if df is None:
        return pd.DataFrame()

    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    data = df.copy()

    if not isinstance(data.columns, pd.MultiIndex):
        return data

    new_columns = []

    for column in data.columns:

        if isinstance(column, tuple):

            selected = None

            # Önce standart OHLCV kolonunu ara
            for item in column:

                item_str = str(item).strip()

                if item_str in REQUIRED_COLUMNS:
                    selected = item_str
                    break

            if selected is not None:
                new_columns.append(selected)

            else:
                # Fallback
                new_columns.append(str(column[0]))

        else:
            new_columns.append(str(column))

    data.columns = new_columns

    return data


# ============================================================
# DATAFRAME CLEANER
# ============================================================

def clean_dataframe(df):
    """
    Yahoo'dan gelen ham DataFrame'i standart OHLCV
    formatına çevirir.

    Bu fonksiyon indikatör hesaplamaz.
    """

    if df is None:
        return pd.DataFrame()

    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    data = _flatten_columns(df)

    if data.empty:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Kolon isimlerini standartlaştır
    # --------------------------------------------------------

    data.columns = [
        str(column).strip()
        for column in data.columns
    ]

    # --------------------------------------------------------
    # Gerekli kolonları oluştur
    # --------------------------------------------------------

    for column in REQUIRED_COLUMNS:

        if column not in data.columns:
            data[column] = np.nan

    # --------------------------------------------------------
    # Sadece OHLCV kolonları
    # --------------------------------------------------------

    data = data[
        REQUIRED_COLUMNS
    ].copy()

    # --------------------------------------------------------
    # Numeric dönüşüm
    # --------------------------------------------------------

    for column in REQUIRED_COLUMNS:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # Sonsuz değerleri temizle
    # --------------------------------------------------------

    data.replace(
        [np.inf, -np.inf],
        np.nan,
        inplace=True
    )

    # --------------------------------------------------------
    # OHLC geçersiz satırları temizle
    # --------------------------------------------------------

    data.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
        ],
        inplace=True
    )

    # --------------------------------------------------------
    # Volume NaN -> 0
    # --------------------------------------------------------

    data["Volume"] = (
        data["Volume"]
        .fillna(0)
    )

    # --------------------------------------------------------
    # Tarih / index bilgisini koru
    # --------------------------------------------------------

    if isinstance(
        data.index,
        pd.DatetimeIndex
    ):

        try:
            data = data.sort_index()

        except Exception:
            pass

    else:

        try:

            data.index = pd.to_datetime(
                data.index,
                errors="coerce"
            )

            data = data[
                ~data.index.isna()
            ]

            data = data.sort_index()

        except Exception:
            pass

    # --------------------------------------------------------
    # Duplicate timestamp temizliği
    # --------------------------------------------------------

    if isinstance(
        data.index,
        pd.DatetimeIndex
    ):

        data = data[
            ~data.index.duplicated(
                keep="last"
            )
        ]

    return data


# ============================================================
# DATAFRAME VALIDATOR
# ============================================================

def validate_dataframe(
    df,
    minimum_rows=5
):
    """
    DataFrame'in kullanılabilir olup olmadığını kontrol eder.
    """

    if not isinstance(
        df,
        pd.DataFrame
    ):
        return False

    if df.empty:
        return False

    if len(df) < minimum_rows:
        return False

    for column in REQUIRED_COLUMNS:

        if column not in df.columns:
            return False

    try:

        close = pd.to_numeric(
            df["Close"],
            errors="coerce"
        )

    except Exception:
        return False

    if close.empty:
        return False

    if close.isna().all():
        return False

    if safe_float(
        close.iloc[-1],
        0.0
    ) <= 0:
        return False

    return True


# ============================================================
# LAST CLOSE
# ============================================================

def _last_close(df):
    """
    DataFrame'in son geçerli Close değerini döndürür.
    """

    if not isinstance(
        df,
        pd.DataFrame
    ):
        return 0.0

    if df.empty:
        return 0.0

    if "Close" not in df.columns:
        return 0.0

    try:

        close = (
            pd.to_numeric(
                df["Close"],
                errors="coerce"
            )
            .dropna()
        )

        if close.empty:
            return 0.0

        return safe_float(
            close.iloc[-1],
            0.0
        )

    except Exception:
        return 0.0


# ============================================================
# DOWNLOAD MARKET DATA
# ============================================================

def download_market_data(
    symbol,
    interval,
    period
):
    """
    Yahoo Finance'tan ham veri alır ve temizlenmiş
    DataFrame döndürür.
    """

    _ensure_event_loop()

    try:

        df = yf.download(
            tickers=symbol,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=False,
            threads=False,
            prepost=False,
        )

        return clean_dataframe(df)

    except Exception as exc:

        print(
            f"[MARKET_DATA] Yahoo veri hatası "
            f"{symbol} {interval}: {exc}"
        )

        return pd.DataFrame()


# ============================================================
# SAFE DOWNLOAD
# ============================================================

def safe_download(
    symbol,
    interval,
    period,
    retries=MAX_RETRY
):
    """
    Veri alınamazsa kontrollü tekrar dener.
    """

    last_df = pd.DataFrame()

    try:

        retries = max(
            1,
            int(retries)
        )

    except Exception:

        retries = MAX_RETRY

    for attempt in range(
        1,
        retries + 1
    ):

        df = download_market_data(
            symbol=symbol,
            interval=interval,
            period=period,
        )

        if validate_dataframe(df):
            return df

        last_df = df

        if attempt < retries:

            time.sleep(
                RETRY_DELAY
            )

    return last_df


# ============================================================
# LIVE PRICE
# ============================================================

def get_live_price(
    symbol=DEFAULT_SYMBOL
):
    """
    Güncel kullanılabilir fiyatı almaya çalışır.

    Yöntem 1:
        Yahoo 1 dakika verisi

    Yöntem 2:
        Ticker.history()

    Başarısız olursa:
        0.0
    """

    _ensure_event_loop()

    # --------------------------------------------------------
    # YÖNTEM 1
    # --------------------------------------------------------

    try:

        df = yf.download(
            tickers=symbol,
            period="1d",
            interval="1m",
            progress=False,
            auto_adjust=False,
            threads=False,
            prepost=False,
        )

        df = clean_dataframe(df)

        price = _last_close(df)

        if price > 0:
            return price

    except Exception as exc:

        print(
            "[MARKET_DATA] "
            "Live price yöntemi 1 hatası: "
            f"{exc}"
        )

    # --------------------------------------------------------
    # YÖNTEM 2
    # --------------------------------------------------------

    try:

        ticker = yf.Ticker(symbol)

        data = ticker.history(
            period="1d",
            interval="1m",
            prepost=False,
            auto_adjust=False,
        )

        data = clean_dataframe(data)

        price = _last_close(data)

        if price > 0:
            return price

    except Exception as exc:

        print(
            "[MARKET_DATA] "
            "Live price yöntemi 2 hatası: "
            f"{exc}"
        )

    return 0.0


# ============================================================
# TIMEFRAME DATA
# ============================================================

def get_timeframe_data(
    symbol=DEFAULT_SYMBOL,
    timeframe="5m"
):
    """
    İstenen zaman dilimini standart DataFrame olarak döndürür.
    """

    if timeframe not in TIMEFRAMES:

        print(
            "[MARKET_DATA] "
            f"Geçersiz timeframe: {timeframe}"
        )

        return pd.DataFrame()

    config = TIMEFRAMES[
        timeframe
    ]

    return safe_download(
        symbol=symbol,
        interval=config["interval"],
        period=config["period"],
    )


# ============================================================
# MARKET SESSION
# ============================================================

def get_market_session():
    """
    New York saatine göre piyasa seansını belirler.

    REGULAR:
        09:30 - 16:00

    PREMARKET:
        04:00 - 09:30

    AFTER_HOURS:
        16:00 - 20:00

    CLOSED:
        diğer zamanlar
    """

    try:

        now = datetime.now(
            NEW_YORK_TZ
        )

        weekday = now.weekday()

        # Cumartesi / Pazar
        if weekday >= 5:
            return "CLOSED"

        current_time = now.time()

        premarket_start = datetime.strptime(
            "04:00",
            "%H:%M"
        ).time()

        regular_start = datetime.strptime(
            "09:30",
            "%H:%M"
        ).time()

        regular_end = datetime.strptime(
            "16:00",
            "%H:%M"
        ).time()

        after_hours_end = datetime.strptime(
            "20:00",
            "%H:%M"
        ).time()

        # PREMARKET
        if (
            premarket_start
            <= current_time
            < regular_start
        ):
            return "PREMARKET"

        # REGULAR
        if (
            regular_start
            <= current_time
            < regular_end
        ):
            return "REGULAR"

        # AFTER HOURS
        if (
            regular_end
            <= current_time
            < after_hours_end
        ):
            return "AFTER_HOURS"

        return "CLOSED"

    except Exception:
        return "CLOSED"


# ============================================================
# MARKET DATA HEALTH
# ============================================================

def market_data_health(market):
    """
    Market data'nın hangi parçalarının kullanılabilir
    olduğunu kontrol eder.
    """

    result = {
        "status": "ERROR",
        "price": False,
        "1m": False,
        "5m": False,
        "15m": False,
    }

    if not isinstance(
        market,
        dict
    ):
        return result

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    price = safe_float(
        market.get(
            "price",
            0
        ),
        0.0
    )

    if price > 0:
        result["price"] = True

    # --------------------------------------------------------
    # TIMEFRAMES
    # --------------------------------------------------------

    for timeframe in [
        "1m",
        "5m",
        "15m",
    ]:

        df = market.get(
            f"df_{timeframe}"
        )

        if validate_dataframe(df):
            result[timeframe] = True

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    valid_timeframes = (
        result["1m"]
        or result["5m"]
        or result["15m"]
    )

    if (
        result["price"]
        and valid_timeframes
    ):

        result["status"] = "OK"

    elif (
        result["price"]
        or valid_timeframes
    ):

        result["status"] = "PARTIAL"

    return result


# ============================================================
# BUILD MARKET DATA
# ============================================================

def build_market_data(
    symbol=DEFAULT_SYMBOL
):
    """
    Sistemin ana market_data sözlüğünü oluşturur.

    Diğer bütün motorların beklediği temel veri yapısı
    buradan çıkar.

    Bu fonksiyon:
        - fiyat alır
        - 1m veri alır
        - 5m veri alır
        - 15m veri alır
        - volume sağlar
        - veri kalitesini kontrol eder
        - seans bilgisini sağlar

    Bu fonksiyon:
        - trend hesaplamaz
        - sinyal üretmez
        - S/R hesaplamaz
        - CALL / PUT kararı vermez
    """

    now = datetime.now()

    market = {
        "symbol": symbol,

        "timestamp": now,
        "last_update": now,

        "source": "Yahoo Finance",

        "price": 0.0,
        "volume": 0,

        "df_1m": pd.DataFrame(),
        "df_5m": pd.DataFrame(),
        "df_15m": pd.DataFrame(),

        "data_ok": False,
        "market_open": False,

        "session": get_market_session(),
    }

    # ========================================================
    # LIVE PRICE
    # ========================================================

    market["price"] = get_live_price(
        symbol
    )

    # ========================================================
    # TIMEFRAME DATA
    # ========================================================

    for timeframe in TIMEFRAMES:

        market[
            f"df_{timeframe}"
        ] = get_timeframe_data(
            symbol=symbol,
            timeframe=timeframe,
        )

    # ========================================================
    # PRICE FALLBACK
    # ========================================================

    if safe_float(
        market.get("price"),
        0.0
    ) <= 0:

        fallback_sources = [
            market.get("df_1m"),
            market.get("df_5m"),
            market.get("df_15m"),
        ]

        for df in fallback_sources:

            fallback_price = _last_close(
                df
            )

            if fallback_price > 0:

                market["price"] = (
                    fallback_price
                )

                break

    # ========================================================
    # VOLUME
    # ========================================================

    volume = 0

    for timeframe in [
        "1m",
        "5m",
        "15m",
    ]:

        df = market.get(
            f"df_{timeframe}"
        )

        if validate_dataframe(df):

            try:

                value = safe_float(
                    df["Volume"].iloc[-1],
                    0.0
                )

                if value >= 0:

                    volume = int(
                        value
                    )

                    break

            except Exception:
                continue

    market["volume"] = volume

    # ========================================================
    # DATA VALIDATION
    # ========================================================

    health = market_data_health(
        market
    )

    market["health"] = health

    market["data_ok"] = (
        health["status"] == "OK"
    )

    # ========================================================
    # MARKET OPEN
    # ========================================================

    market["market_open"] = (
        market["session"] == "REGULAR"
    )

    # ========================================================
    # UPDATE TIME
    # ========================================================

    market["last_update"] = datetime.now()

    return market


# ============================================================
# PUBLIC MARKET DATA FUNCTION
# ============================================================

def get_market_data(
    symbol=DEFAULT_SYMBOL
):
    """
    Diğer motorların kullanacağı ana public function.

    Kullanım:

        market = get_market_data("QQQ")
    """

    try:

        return build_market_data(
            symbol=symbol
        )

    except Exception as exc:

        print(
            "[MARKET_DATA] "
            f"Market data error: {exc}"
        )

        return _empty_market_data(
            symbol=symbol
        )


# ============================================================
# PRO MARKET DATA
# ============================================================

def get_pro_market_data(
    symbol=DEFAULT_SYMBOL
):
    """
    Geriye dönük uyumluluk için korunmaktadır.

    Ana veri:
        get_market_data()

    Ek olarak:
        health
    """

    market = get_market_data(
        symbol=symbol
    )

    market["health"] = (
        market_data_health(
            market
        )
    )

    return market


# ============================================================
# MODULE SELF TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("QQQ PRO MARKET DATA SELF TEST")
    print("=" * 60)

    market = get_market_data(
        DEFAULT_SYMBOL
    )

    print(
        "SYMBOL :",
        market.get("symbol")
    )

    print(
        "PRICE  :",
        market.get("price")
    )

    print(
        "VOLUME :",
        market.get("volume")
    )

    print(
        "SESSION:",
        market.get("session")
    )

    print(
        "OPEN   :",
        market.get("market_open")
    )

    print(
        "DATA OK:",
        market.get("data_ok")
    )

    print(
        "HEALTH :",
        market.get("health")
    )

    for timeframe in [
        "1m",
        "5m",
        "15m",
    ]:

        df = market.get(
            f"df_{timeframe}"
        )

        print(
            f"{timeframe.upper()} ROWS:",
            len(df)
        )

    print("=" * 60)
    print("MARKET DATA SELF TEST COMPLETE")
    print("=" * 60)