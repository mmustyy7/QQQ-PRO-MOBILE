from datetime import datetime

import numpy as np
import pandas as pd

from bist_radar.data import _split_download
from bist_radar.news import _parse_rss, score_headline
from bist_radar.scanner import scan, to_frame
from bist_radar.scoring import TR_TZ, analyze, apply_news, ceiling_price, tick_size
from bist_radar.symbols import parse_custom_list

AFTER_CLOSE = datetime(2026, 11, 13, 19, 0, tzinfo=TR_TZ)


def make_df(n=120, last_change=0.0, last_vol_mult=1.0, trend=0.001, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + trend + rng.normal(0, 0.005, n))
    close[-1] = close[-2] * (1 + last_change)
    high = close * 1.005
    low = close * 0.995
    high[-1] = close[-1]  # gün yükseğinde
    vol = np.full(n, 1_000_000.0)
    vol[-1] *= last_vol_mult
    idx = pd.bdate_range(end="2026-11-13", periods=n)
    return pd.DataFrame({"Open": close, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def test_tick_and_ceiling():
    assert tick_size(15) == 0.01 and tick_size(120) == 0.10 and tick_size(3000) == 2.5
    assert ceiling_price(100) == 110.0
    assert ceiling_price(18.37) == 20.20  # 20.207 -> 0.02 adımına aşağı
    assert ceiling_price(47.13) == 51.80  # 51.843 -> 0.05 adımı


def test_strong_candidate_scores_high():
    r = analyze("TEST", make_df(last_change=0.08, last_vol_mult=3.5), now=AFTER_CLOSE)
    assert r.score >= 75, (r.score, r.reasons)
    assert any("Hacim" in x for x in r.reasons)
    assert any("direnç" in x for x in r.reasons)


def test_at_ceiling_detected():
    df = make_df(last_change=0.0)
    prev = df["Close"].iloc[-2]
    df.iloc[-1, df.columns.get_loc("Close")] = ceiling_price(prev)
    df.iloc[-1, df.columns.get_loc("High")] = ceiling_price(prev)
    r = analyze("TVN", df, now=AFTER_CLOSE)
    assert r.at_ceiling and r.label == "🔒 TAVANDA"


def test_falling_stock_scores_low():
    r = analyze("DUS", make_df(last_change=-0.05, trend=-0.003), now=AFTER_CLOSE)
    assert r.score < 20


def test_missing_data():
    assert analyze("YOK", None).error
    assert analyze("AZ", make_df(n=10)).error


def test_intraday_volume_normalized():
    df = make_df(last_vol_mult=1.0)
    df.index = df.index[:-1].append(pd.DatetimeIndex([pd.Timestamp("2026-11-13")]))
    noon = datetime(2026, 11, 13, 12, 0, tzinfo=TR_TZ)  # seansın 1/4'ü
    r = analyze("X", df, now=noon)
    assert 3.9 < r.volume_ratio < 4.1


def test_headline_scoring():
    w, hits = score_headline("ASELS KAP: Savunma Sanayii Başkanlığı ile 120 milyon $ SÖZLEŞME imzaladı")
    assert w > 0 and "sözleşme imzala" in hits
    w2, _ = score_headline("Şirkete SPK tedbir kararı, işlem yasağı getirildi")
    assert w2 < 0
    w3, hits3 = score_headline("Pay geri alım programı başladı")
    assert w3 == 3 and hits3 == ["pay geri alım"]
    w4, _ = score_headline("İHALE kazandı")
    assert w4 == 3


def test_apply_news():
    r = analyze("TEST", make_df(last_change=0.05, last_vol_mult=2), now=AFTER_CLOSE)
    before = r.score
    apply_news(r, [{"title": "Yeni iş ilişkisi", "weight": 3}])
    assert r.news_score == 9 and r.score >= before
    assert any("Olumlu haber" in x for x in r.reasons)


def test_rss_parse():
    now = datetime.now(TR_TZ).strftime("%a, %d %b %Y %H:%M:%S %z")
    xml = f"""<rss><channel>
      <item><title>THYAO yeni sipariş verdi</title><link>http://a</link><pubDate>{now}</pubDate></item>
      <item><title>Eski haber</title><pubDate>Mon, 01 Jan 2024 10:00:00 +0300</pubDate></item>
    </channel></rss>"""
    items = _parse_rss(xml, 24)
    assert len(items) == 1 and items[0]["weight"] == 3


def test_split_download_and_scan():
    a, b = make_df(last_change=0.09, last_vol_mult=4), make_df(seed=1)
    raw = pd.concat({"AAA.IS": a, "BBB.IS": b}, axis=1)
    data = _split_download(raw, ["AAA", "BBB", "CCC"])
    assert set(data) == {"AAA", "BBB"}
    results = scan(["AAA", "BBB", "CCC"], lambda c: data, news_fetcher=lambda c: [], news_top_n=2)
    assert results[0].code == "AAA"
    assert results[-1].error
    assert list(to_frame(results)["Hisse"]) == ["AAA", "BBB"]


def test_parse_custom():
    assert parse_custom_list("asels, thyao  KCHOL\nSASA.IS asels") == ["ASELS", "THYAO", "KCHOL", "SASA"]
