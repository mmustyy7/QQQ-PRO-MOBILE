import streamlit as st
from datetime import datetime
import pytz

# ==========================
# TÜRKİYE SAATİ
# ==========================
def turkey_time():
    tz = pytz.timezone("Europe/Istanbul")
    return datetime.now(tz)


# ==========================
# ABD (NEW YORK) SAATİ
# ==========================
def newyork_time():
    tz = pytz.timezone("America/New_York")
    return datetime.now(tz)


# ==========================
# SAYI BİÇİMLENDİRME
# ==========================
def format_price(value):
    try:
        return f"{float(value):.2f}"
    except:
        return "0.00"


def format_percent(value):
    try:
        return f"{float(value):.2f}%"
    except:
        return "0.00%"


# ==========================
# RENKLİ DURUM
# ==========================
def color_price(change):
    if change > 0:
        return "🟢"
    elif change < 0:
        return "🔴"
    else:
        return "⚪"


# ==========================
# LOG
# ==========================
def log(message):
    print(f"[{datetime.now()}] {message}")


# ==========================
# STREAMLIT MESAJLARI
# ==========================
def success(msg):
    st.success(msg)


def warning(msg):
    st.warning(msg)


def error(msg):
    st.error(msg)