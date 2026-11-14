# 🚀 BIST Tavan Radarı

Borsa İstanbul'da (BIST 30 / 50 / 100 veya özel liste) tavan olma potansiyeli
taşıyan hisseleri tarar, 0–100 arası skorla sıralar, gerekçelerini yazar ve
ekranda / Telegram'da bildirim verir.

> ⚠️ Yatırım tavsiyesi değildir. Skor bir **olasılık değil**, sıralama puanıdır.
> Broker'a emir göndermez.

## Ne kontrol ediliyor?

| Kriter | Puan |
|---|---|
| Günlük yükseliş / tavana yakınlık (±%10 limit) | 0–30 |
| Hacim patlaması (20g ortalamaya göre, seans saatine göre düzeltilmiş) | 0–20 |
| 20 günlük direnç kırılımı (+52 haftalık zirve) | 0–15 |
| Trend: Fiyat > EMA20 > EMA50 | 0–10 |
| Gün yükseğine yakın işlem (güçlü kapanış) | 0–10 |
| RSI 55–85 | 0–5 |
| Haber / KAP başlıkları (sözleşme, ihale, bedelsiz, geri alım… / ceza, tedbir…) | −15…+15 |

Etiketler: 🔒 TAVANDA • 🔥 Güçlü aday (≥75) • ⚡ Aday (≥55) • 👀 İzle (≥35)

## Çalıştırma

```bash
pip install -r requirements.txt
streamlit run bist_app.py          # ekranlı sürüm (telefondan da açılır)
python bist_scan.py --index "BIST 30"           # komut satırı
python bist_scan.py --loop 5 --telegram          # 5 dk'da bir tara + Telegram
```

Streamlit Cloud'da ayrı bir uygulama olarak kurun: **Main file path = `bist_app.py`**.
Secrets (isteğe bağlı):

```toml
APP_PASSWORD = "..."
TELEGRAM_BOT_TOKEN = "..."   # @BotFather -> /newbot
TELEGRAM_CHAT_ID = "..."     # https://api.telegram.org/bot<TOKEN>/getUpdates
```

## Dosyalar

- `bist_radar/symbols.py` – endeks listeleri (çeyreklik güncellenmeli)
- `bist_radar/data.py` – Yahoo Finance günlük veri (~15 dk gecikmeli)
- `bist_radar/scoring.py` – tavan fiyatı, fiyat adımı, indikatörler, skor
- `bist_radar/news.py` – Google News RSS + Türkçe anahtar kelime puanlama
- `bist_radar/notify.py` – Telegram bildirimi
- `bist_radar/scanner.py` – tarama akışı
- `tests/test_bist_radar.py` – birim testleri (`python -m pytest tests`)

## Sınırlamalar / sonraki adımlar

- **Gerçek zamanlı veri ve kurumsal alıcı (AKD / aracı kurum dağılımı)** ücretsiz
  kaynaklarda yok; Matriks, Foreks, İdeal gibi lisanslı bir sağlayıcı için
  `data.py`'ye adaptör yazılmalı. Şimdilik "hacim patlaması" bunun yerine kullanılıyor.
- **KAP**'ın resmî açık API'si yok; haberler KAP bildirimlerini aktaran haber
  kaynaklarından okunuyor. `news.fetch_news` aynı formatta liste döndüren bir
  KAP okuyucuyla değiştirilebilir.
- Skor ağırlıkları geçmiş veriyle (backtest) kalibre edilmeli: "skor ≥75 olan
  hisselerin yüzde kaçı gerçekten tavan oldu?" ölçülmeden yüzde verilmemeli.
