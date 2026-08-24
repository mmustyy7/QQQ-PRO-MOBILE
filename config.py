# ================================
# QQQ PRO TRADING SUITE
# config.py
# Merkezi Ayarlar
# ================================

# İzlenecek ana sembol
DEFAULT_SYMBOL = "QQQ"

# Veri periyotları
INTRADAY_PERIOD = "1d"
INTRADAY_INTERVAL = "1m"

SWING_PERIOD = "5d"
SWING_INTERVAL = "15m"

# Cache süreleri (saniye)
MARKET_CACHE = 10
OPTION_CACHE = 30
NEWS_CACHE = 300

# Teknik indikatör ayarları
RSI_PERIOD = 14

EMA_FAST = 9
EMA_MID = 20
EMA_SLOW = 50

VWAP_ENABLED = True

# Destek / Direnç
DEFAULT_SUPPORT = 661.30
DEFAULT_RESISTANCE = 680.00
RESISTANCE_STEP = 4.00

# Alarm seviyeleri
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Hacim filtresi
HIGH_VOLUME_FACTOR = 1.50

# Opsiyon
DEFAULT_DELTA = 0.50
DEFAULT_GAMMA = "Yüksek"

# Kâr / Zarar
TARGET_PROFIT_PERCENT = 25
STOP_LOSS_PERCENT = -15

# Renkler
COLOR_BULL = "#00C853"
COLOR_BEAR = "#D50000"
COLOR_NEUTRAL = "#FFAB00"

# Başlık
APP_TITLE = "QQQ PRO AI TRADING SUITE"

# Versiyon
VERSION = "2.0 Professional"