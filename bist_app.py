# ============================================================
# BIST TAVAN RADARI — Streamlit arayüzü
#
# Çalıştırma (bilgisayarda):   streamlit run bist_app.py
# Bulut (Streamlit Cloud):     Main file path = bist_app.py
#
# Yatırım tavsiyesi DEĞİLDİR. Broker'a emir göndermez.
# ============================================================

from __future__ import annotations

import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from bist_radar.data import fetch_daily
from bist_radar.news import fetch_news
from bist_radar.notify import format_alert, send_telegram
from bist_radar.scanner import scan, to_frame
from bist_radar.scoring import TR_TZ, is_market_open
from bist_radar.symbols import INDEXES, parse_custom_list

st.set_page_config(page_title="BIST Tavan Radarı", page_icon="🚀", layout="wide")


def secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, "")).strip()


# ------------------------------------------------------------
# Parola (APP_PASSWORD tanımlıysa zorunlu)
# ------------------------------------------------------------
password = secret("APP_PASSWORD")
if password and not st.session_state.get("bist_auth"):
    st.title("🔐 BIST Tavan Radarı")
    entered = st.text_input("Uygulama parolası", type="password")
    if st.button("Giriş Yap", use_container_width=True):
        if entered == password:
            st.session_state.bist_auth = True
            st.rerun()
        st.error("Parola hatalı.")
    st.stop()


# ------------------------------------------------------------
# Önbellekli veri fonksiyonları
# ------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def cached_prices(codes: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    return fetch_daily(list(codes))


@st.cache_data(ttl=600, show_spinner=False)
def cached_news(code: str) -> list[dict]:
    return fetch_news(code)


# ------------------------------------------------------------
# Kenar çubuğu
# ------------------------------------------------------------
st.sidebar.title("⚙️ Tarama ayarları")
universe = st.sidebar.selectbox("Hisse evreni", [*INDEXES.keys(), "Özel liste"], index=2)
if universe == "Özel liste":
    custom = st.sidebar.text_area("Hisse kodları (virgül/boşluk ile)", "ASELS, THYAO, SASA")
    codes = parse_custom_list(custom)
else:
    codes = INDEXES[universe]

min_score = st.sidebar.slider("Minimum skor (listeleme)", 0, 100, 35, 5)
use_news = st.sidebar.checkbox("Haber / KAP taraması", value=True)
news_top_n = st.sidebar.slider("Haberi taranacak hisse sayısı", 5, 40, 15, 5, disabled=not use_news)
alert_score = st.sidebar.slider("Bildirim eşiği (skor)", 50, 100, 75, 5)

st.sidebar.markdown("---")
auto = st.sidebar.checkbox("Otomatik yenile", value=False)
refresh_min = st.sidebar.selectbox("Yenileme aralığı (dk)", [2, 5, 10, 15], index=1)

tg_token, tg_chat = secret("TELEGRAM_BOT_TOKEN"), secret("TELEGRAM_CHAT_ID")
use_tg = st.sidebar.checkbox(
    "Telegram bildirimi gönder",
    value=bool(tg_token and tg_chat),
    disabled=not (tg_token and tg_chat),
    help="Secrets'a TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID ekleyin.",
)
if st.sidebar.button("🔄 Şimdi tara", use_container_width=True):
    st.cache_data.clear()


# ------------------------------------------------------------
# Başlık
# ------------------------------------------------------------
now = datetime.now(TR_TZ)
st.title("🚀 BIST Tavan Radarı")
st.caption(
    f"{universe} • {len(codes)} hisse • {now:%d.%m.%Y %H:%M} • "
    + ("🟢 Seans açık" if is_market_open(now) else "🔴 Seans kapalı (son kapanışa göre — yarın için adaylar)")
    + " • Veri ~15 dk gecikmeli"
)

if not codes:
    st.warning("Taranacak hisse yok.")
    st.stop()

with st.spinner("Hisseler taranıyor…"):
    results = scan(
        codes,
        price_fetcher=lambda c: cached_prices(tuple(c)),
        news_fetcher=cached_news if use_news else None,
        news_top_n=news_top_n if use_news else 0,
    )

df = to_frame(results)
failed = [r for r in results if r.error]

if df.empty:
    st.error("Veri alınamadı. İnternet bağlantısını veya Yahoo Finance erişimini kontrol edin.")
    st.stop()

# ------------------------------------------------------------
# Özet
# ------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("🔒 Tavanda", int((df["Durum"] == "🔒 TAVANDA").sum()))
c2.metric("🔥 Güçlü aday", int((df["Durum"] == "🔥 Güçlü aday").sum()))
c3.metric("⚡ Aday", int((df["Durum"] == "⚡ Aday").sum()))
c4.metric("Yükselen / Düşen", f"{int((df['Değişim %'] > 0).sum())} / {int((df['Değişim %'] < 0).sum())}")

# ------------------------------------------------------------
# Bildirimler (aynı hisse için günde bir kez)
# ------------------------------------------------------------
sent_key = f"alerted_{now:%Y%m%d}"
alerted: set = st.session_state.setdefault(sent_key, set())
hot = df[(df["Skor"] >= alert_score) | (df["Durum"] == "🔒 TAVANDA")]
for row in hot.to_dict("records"):
    if row["Hisse"] in alerted:
        continue
    alerted.add(row["Hisse"])
    st.toast(f"{row['Durum']} {row['Hisse']} — skor {row['Skor']:.0f}", icon="🚨")
    if use_tg:
        send_telegram(tg_token, tg_chat, format_alert(row))

# ------------------------------------------------------------
# Aday kartları
# ------------------------------------------------------------
listed = df[df["Skor"] >= min_score].reset_index(drop=True)
st.subheader(f"🎯 Tavan adayları ({len(listed)})")

by_code = {r.code: r for r in results}
for row in listed.head(12).to_dict("records"):
    r = by_code[row["Hisse"]]
    with st.container(border=True):
        a, b, c = st.columns([2, 1, 1])
        a.markdown(f"### {row['Durum']} &nbsp; **{row['Hisse']}**")
        b.metric("Fiyat", f"{row['Fiyat']:.2f}", f"{row['Değişim %']:+.2f}%")
        c.metric("Skor", f"{row['Skor']:.0f}/100", f"tavana {row['Tavana kalan %']:.1f}%", delta_color="off")
        st.progress(min(int(row["Skor"]), 100))
        for reason in r.reasons:
            st.markdown(f"- {reason}")
        if r.news:
            with st.expander(f"📰 Haberler ({len(r.news)})"):
                for n in r.news:
                    mark = "🟢" if n["weight"] > 0 else "🔴" if n["weight"] < 0 else "⚪"
                    st.markdown(f"{mark} [{n['title']}]({n['link']})")

# ------------------------------------------------------------
# Tüm tablo
# ------------------------------------------------------------
st.subheader("📋 Tüm hisseler")
st.dataframe(
    df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Skor": st.column_config.ProgressColumn("Skor", min_value=0, max_value=100, format="%.0f"),
        "Değişim %": st.column_config.NumberColumn(format="%+.2f%%"),
        "Gerekçeler": st.column_config.TextColumn(width="large"),
    },
)
st.download_button(
    "⬇️ CSV indir",
    df.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"bist_tavan_radari_{now:%Y%m%d_%H%M}.csv",
    mime="text/csv",
)

if failed:
    with st.expander(f"⚠️ Verisi alınamayan hisseler ({len(failed)})"):
        st.write(", ".join(f"{r.code} ({r.error})" for r in failed))

with st.expander("ℹ️ Skor nasıl hesaplanıyor?"):
    st.markdown(
        """
| Bileşen | Puan |
|---|---|
| Günlük yükseliş (tavana yakınlık) | 0–30 |
| Hacim patlaması (20 günlük ortalamaya göre, seans saatine göre düzeltilmiş) | 0–20 |
| 20 günlük direnç kırılımı (+52 haftalık zirve) | 0–15 |
| Trend (Fiyat > EMA20 > EMA50) | 0–10 |
| Gün yükseğine yakın işlem (güçlü kapanış) | 0–10 |
| RSI 55–85 momentum bölgesi | 0–5 |
| Haber / KAP başlık analizi (olumlu + / olumsuz −) | −15…+15 |

**Skor bir olasılık değildir**; hangi hisselere önce bakmanız gerektiğini gösteren bir sıralamadır.
Tavan fiyatı = önceki kapanış × 1,10 (fiyat adımına yuvarlanır, yaklaşık değerdir).
Ücretsiz veri ~15 dk gecikmelidir; kurumsal alıcı (AKD) verisi lisanslı kaynak gerektirir.
**Yatırım tavsiyesi değildir.**
"""
    )

if auto:
    st.caption(f"⏱️ {refresh_min} dk sonra otomatik yenilenecek…")
    time.sleep(refresh_min * 60)
    st.rerun()
