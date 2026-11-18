# ============================================================
# MOMENTUM TARAYICI — Streamlit sayfası
# Açılışından +%10 / +%15 / +%20 prim potansiyeli olan ABD
# hisselerini tarar, puanlar ve gerekçeleriyle listeler.
# ============================================================

from __future__ import annotations

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import momentum_scanner as ms  # noqa: E402

st.set_page_config(page_title="Momentum Tarayıcı", page_icon="🚀", layout="wide")


# ------------------------------------------------------------
# Parola (ana uygulama ile aynı oturum anahtarı)
# ------------------------------------------------------------
def require_password() -> None:
    try:
        configured = str(st.secrets.get("APP_PASSWORD", "")).strip()
    except Exception:
        configured = str(os.getenv("APP_PASSWORD", "")).strip()
    if not configured:
        st.error("Bulut parolası ayarlanmamış. Streamlit ayarlarında APP_PASSWORD secret değerini ekleyin.")
        st.stop()
    if st.session_state.get("cloud_authenticated", False):
        return
    st.title("🔐 Momentum Tarayıcı Giriş")
    pw = st.text_input("Uygulama parolası", type="password")
    if st.button("Giriş Yap", width="stretch"):
        if pw == configured:
            st.session_state.cloud_authenticated = True
            st.rerun()
        else:
            st.error("Parola yanlış.")
    st.stop()


require_password()

st.markdown(
    """
    <style>
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.65rem; }
        h1 { font-size: 1.5rem !important; }
        h2, h3 { font-size: 1.1rem !important; }
        div[data-testid="stMetric"] { min-width: 130px; }
    }
    .sig { color: #00C853; margin: 0.1rem 0; }
    .risk { color: #FF5252; margin: 0.1rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚀 Momentum Tarayıcı — ABD")
st.caption(
    "Açılışından +%10 / +%15 / +%20 prim yapma potansiyeli taşıyan hisseleri "
    "hacim, teknik kırılım, haber, opsiyon akışı ve açığa satış verileriyle puanlar."
)

# ------------------------------------------------------------
# Ayarlar
# ------------------------------------------------------------
with st.expander("⚙️ Tarama ayarları", expanded=False):
    c1, c2 = st.columns(2)
    min_price = c1.number_input("Min. fiyat ($)", 0.1, 1000.0, 1.0, 0.5)
    max_price = c2.number_input("Maks. fiyat ($)", 1.0, 5000.0, 1000.0, 10.0)
    min_dv = c1.number_input("Min. bugünkü işlem hacmi (milyon $)", 0.0, 500.0, 3.0, 1.0)
    min_avg = c2.number_input("Min. ortalama günlük hacim (bin adet)", 0.0, 50_000.0, 300.0, 50.0)
    max_universe = c1.slider("Detaylı incelenecek hisse sayısı", 50, 300, 150, 25)
    deep_count = c2.slider("Haber / opsiyon bakılacak en iyi aday", 5, 60, 30, 5)
    include_news = c1.checkbox("Haberleri analiz et", True)
    include_options = c2.checkbox("Opsiyon akışını analiz et", True)
    watch_txt = st.text_area(
        "İzleme listesi (her taramada mutlaka kontrol edilir)",
        ", ".join(ms.DEFAULT_WATCHLIST),
        height=90,
    )
    min_score = st.slider("Listede gösterilecek minimum puan", 0, 90, 35, 5)

settings = ms.ScanSettings(
    min_price=float(min_price),
    max_price=float(max_price),
    min_dollar_volume=float(min_dv) * 1e6,
    min_avg_volume=float(min_avg) * 1e3,
    max_universe=int(max_universe),
    deep_count=int(deep_count),
    include_news=include_news,
    include_options=include_options,
    watchlist=[s for s in watch_txt.replace("\n", ",").replace(" ", ",").split(",") if s.strip()],
)

now_ny = datetime.now(ms.NY)
phase = ms.market_phase(now_ny)
st.info(f"🕒 New York saati: **{now_ny:%d.%m.%Y %H:%M}** — {ms.PHASE_LABELS[phase]}")
if phase == "premarket":
    st.caption("Pre-market'te hedefler önceki kapanışa göre hesaplanır; açılıştan sonra açılış fiyatına göre güncellenir.")
elif phase in ("closed", "postmarket"):
    st.caption("Seans kapalıyken liste son seansın sonuçlarını ve yarına taşınabilecek adayları gösterir.")

if st.button("🔎 Taramayı Başlat", type="primary", width="stretch"):
    bar = st.progress(0.0, text="Başlatılıyor…")
    try:
        result = ms.run_scan(settings, progress=lambda f, m: bar.progress(min(1.0, f), text=m))
        st.session_state.momentum_result = result
    except Exception as exc:
        st.error(f"Tarama başarısız: {exc}")
    bar.empty()

result: ms.ScanResult | None = st.session_state.get("momentum_result")
if result is None:
    st.write("Başlamak için **Taramayı Başlat** düğmesine basın. Tam tarama genellikle 30–90 saniye sürer.")
    st.stop()

# ------------------------------------------------------------
# Özet
# ------------------------------------------------------------
table = result.table
shown = table[table["Puan"] >= min_score] if not table.empty else table
grades = table["Sınıf"].value_counts() if not table.empty else pd.Series(dtype=int)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Taranan evren", result.universe_size)
m2.metric("Filtreyi geçen", result.analysed)
m3.metric("A sınıfı", int(grades.get("A", 0)))
m4.metric("B sınıfı", int(grades.get("B", 0)))
st.caption(
    f"Tarama zamanı: {result.started_at.astimezone(ms.NY):%H:%M:%S} NY · "
    f"süre {result.duration_sec:.0f} sn · veri günü {result.analysis_date or '-'}"
)
if result.errors:
    with st.expander(f"⚠️ Veri uyarıları ({len(result.errors)})"):
        for e in result.errors[:50]:
            st.write("•", e)

if shown.empty:
    st.warning("Seçilen minimum puanın üzerinde aday bulunamadı.")
    st.stop()

# ------------------------------------------------------------
# Tablo
# ------------------------------------------------------------
st.subheader("📋 Aday listesi")
cols = ["Sembol", "Puan", "Sınıf", "Fiyat", "Açılıştan %", "Gap %", "Pre-mkt %", "RVOL",
        "Ulaşılan", "Hedef +%10", "Hedef +%15", "Hedef +%20", "Öne çıkan", "Risk",
        "Dolar hacmi", "Piyasa değeri", "Şirket", "Kaynak"]
st.dataframe(
    shown[cols],
    width="stretch",
    height=min(640, 38 + 35 * len(shown)),
    column_config={
        "Puan": st.column_config.ProgressColumn("Puan", min_value=0, max_value=100, format="%.0f"),
        "Fiyat": st.column_config.NumberColumn(format="$%.2f"),
        "Hedef +%10": st.column_config.NumberColumn(format="$%.2f"),
        "Hedef +%15": st.column_config.NumberColumn(format="$%.2f"),
        "Hedef +%20": st.column_config.NumberColumn(format="$%.2f"),
        "Açılıştan %": st.column_config.NumberColumn(format="%+.1f%%"),
        "Gap %": st.column_config.NumberColumn(format="%+.1f%%"),
        "Pre-mkt %": st.column_config.NumberColumn(format="%+.1f%%"),
        "RVOL": st.column_config.NumberColumn(format="%.1fx"),
        "Dolar hacmi": st.column_config.NumberColumn(format="compact"),
        "Piyasa değeri": st.column_config.NumberColumn(format="compact"),
        "Öne çıkan": st.column_config.TextColumn(width="large"),
        "Risk": st.column_config.TextColumn(width="medium"),
    },
)
st.download_button(
    "⬇️ Listeyi CSV olarak indir",
    shown.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"momentum_tarama_{result.started_at.astimezone(ms.NY):%Y%m%d_%H%M}.csv",
    mime="text/csv",
    width="stretch",
)

# ------------------------------------------------------------
# Detay kartları
# ------------------------------------------------------------
st.subheader("🔬 Aday detayları")
GRADE_ICON = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "⚪"}


def pct(x):
    return "-" if x is None else f"%{x * 100:+.1f}"


for sym in shown["Sembol"].head(20):
    d = result.details[sym]
    f, sc = d["features"], d["score"]
    header = (f"{GRADE_ICON[sc['grade']]} {sym} — {sc['score']:.0f} puan · ${f['price']:.2f} · "
              f"açılıştan {pct(f.get('change_from_open'))} · {f['name']}")
    with st.expander(header, expanded=sc["grade"] == "A"):
        a, b, c = st.columns(3)
        a.metric("Fiyat", f"${f['price']:.2f}", pct(f.get("change_from_prev")))
        b.metric("RVOL", "-" if f.get("rvol") is None else f"{f['rvol']:.1f}x")
        c.metric("Gün zirvesi", "-" if not f.get("hod") else f"${f['hod']:.2f}")

        st.markdown(f"**Hedefler ({f['target_ref_label'].lower()} ${f['target_ref']:.2f} bazlı):** "
                    f"+%10 → **${f['t10']:.2f}** · +%15 → **${f['t15']:.2f}** · +%20 → **${f['t20']:.2f}**"
                    + (f" · ✅ ulaşılan: {' '.join(sc['targets_hit'])}" if sc["targets_hit"] else ""))
        st.markdown(f"**Kritik destek / izleme stopu:** ${sc['stop_level']:.2f} ({pct(sc['stop_pct'])})"
                    + (f" · VWAP ${f['vwap']:.2f}" if f.get("vwap") else ""))

        bd = pd.DataFrame({"Bileşen": list(sc["breakdown"].keys()),
                           "Puan": list(sc["breakdown"].values())}).set_index("Bileşen")
        st.bar_chart(bd, horizontal=True, height=220)

        left, right = st.columns(2)
        with left:
            st.markdown("**✅ Sinyaller**")
            for s_ in sc["signals"] or ["-"]:
                st.markdown(f"<p class='sig'>• {s_}</p>", unsafe_allow_html=True)
        with right:
            st.markdown("**⚠️ Riskler**")
            for r_ in sc["risks"] or ["Belirgin risk sinyali yok"]:
                st.markdown(f"<p class='risk'>• {r_}</p>", unsafe_allow_html=True)

        info_bits = []
        if f.get("market_cap"):
            info_bits.append(f"Piyasa değeri {ms._fmt_money(f['market_cap'])}")
        if f.get("float_shares"):
            info_bits.append(f"Float {f['float_shares'] / 1e6:.1f}M")
        if f.get("short_float"):
            info_bits.append(f"Açığa satış %{f['short_float'] * 100:.0f}")
        if f.get("inst_pct"):
            info_bits.append(f"Kurumsal sahiplik %{f['inst_pct'] * 100:.0f}")
        if f.get("atr_pct"):
            info_bits.append(f"ATR %{f['atr_pct'] * 100:.1f}")
        if f.get("sector"):
            info_bits.append(f"{f['sector']} / {f.get('industry', '')}")
        if info_bits:
            st.caption(" · ".join(info_bits))

        news = (f.get("news_info") or {}).get("recent") or []
        if news:
            st.markdown("**📰 Son haberler**")
            for n in news[:5]:
                age = "" if n.get("age_h") is None else f"{n['age_h']:.0f} sa önce · "
                tags = f" — _{', '.join(n['tags'])}_" if n.get("tags") else ""
                title = f"[{n['title']}]({n['url']})" if n.get("url") else n["title"]
                st.markdown(f"- {age}{title}{tags}")
        elif not f.get("deep"):
            st.caption("Haber / opsiyon analizi yalnızca ilk adaylar için yapılır.")

st.divider()
st.caption(
    "⚠️ Bu ekran yatırım tavsiyesi değildir ve broker'a emir göndermez. Puan, geçmiş "
    "davranış ve anlık verilere dayalı bir olasılık sıralamasıdır; %10+ yükselişi garanti etmez. "
    "Yüksek puanlı küçük şirketler aynı hızla düşebilir. Veri kaynağı Yahoo Finance'tir; "
    "gecikmeli veya eksik olabilir."
)
