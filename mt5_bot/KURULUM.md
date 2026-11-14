# 🤖 MT5 Endeks Botu (ABD 100 / ABD 500)

FP Markets (veya başka bir MT5 kurumu) hesabında ABD 100 / ABD 500 endeks
CFD'lerinde otomatik işlem yapan Python botu.

> ⚠️ **Kaldıraçlı CFD'ler yüksek risklidir; yatırılan paranın tamamı kaybedilebilir.**
> Bu bot kâr garantisi vermez. Önce **backtest**, sonra **kuru çalışma**, sonra
> **en az birkaç hafta demo** hesap. Gerçek hesaba geçmeden önce Türkiye'de yerleşik
> kişiler için SPK lisansı olmayan yurt dışı kurumlarla işlem yapmanın yasal
> durumunu araştırın.

## Strateji (varsayılan)

- **Zaman dilimi:** 15 dakikalık barlar
- **Alış:** Kapanış son 20 barın zirvesini kırar **ve** EMA50 > EMA200 **ve** fiyat EMA50 üstünde
- **Satış:** Tersi (açığa satış `allow_short` ile kapatılabilir)
- **Zarar kes:** 1.5 × ATR, **Kâr al:** 3 × ATR (kazanç/risk = 2)
- **İşlem saatleri:** New York 09:45–15:30 (İstanbul ~17:45–23:30, yaz/kış saatine göre değişir)
- **Gün sonu:** 15:55'te (NY saati) tüm pozisyonlar kapanır, gece pozisyon taşınmaz

## Güvenlik kuralları

| Kural | Varsayılan |
|---|---|
| İşlem başına risk | bakiyenin %0.5'i (lot otomatik hesaplanır) |
| Günlük en fazla kayıp | %2 → tüm pozisyonlar kapanır, bot o gün işlem yapmaz |
| Aynı anda en fazla pozisyon | 2 (sembol başına 1) |
| Günlük en fazla işlem | 4 |
| Gerçek hesap | `--allow-real` verilmeden **çalışmaz** |
| Emir gönderme | `--live` verilmeden **gönderilmez** (sadece MT5'e "bu emir geçerli mi" diye sorulur) |
| Acil durdurma | `mt5_bot` klasörüne `STOP` adlı dosya koyun → her şeyi kapatır |

Tüm kararlar `mt5_bot/logs/bot.log` ve `mt5_bot/logs/journal.csv` dosyalarına yazılır.

## Kurulum (Windows)

1. MetaTrader 5'i FP Markets sitesinden indirip **demo hesabınızla** giriş yapın.
2. Python 3.11+ kurun (python.org, "Add to PATH" işaretli).
3. Bu klasörün bulunduğu yerde:
   ```bat
   pip install -r mt5_bot\requirements.txt
   ```
4. MT5'te üst menüdeki **Algo Trading** düğmesini açın (yeşil olmalı).

## Kullanım (bu sırayla)

```bat
:: 1) Sembol adlarını bulun (US100? NAS100? US500? SPX500?)
python -m mt5_bot.bot --list-symbols

:: 2) Adlar farklıysa mt5_bot\config.example.json'u config.json olarak kopyalayıp düzeltin

:: 3) Geçmiş veride test
python -m mt5_bot.bot --backtest US100
python -m mt5_bot.bot --backtest US500

:: 4) Kuru çalışma: sinyalleri ve emirleri kaydeder, GÖNDERMEZ
python -m mt5_bot.bot

:: 5) Demo hesapta gerçek emir
python -m mt5_bot.bot --live
```

Durdurmak için: `Ctrl+C` (açık pozisyonlar MT5'te SL/TP ile korunmaya devam eder)
veya `STOP` dosyası (pozisyonları da kapatır).

## Backtest sonucunu okumak

- **R** = işlem başına riske edilen tutar. Toplam +10R, %0.5 riskte yaklaşık +%5 demektir.
- **Kâr faktörü** 1'in altındaysa strateji o dönemde zarar etmiştir.
- Sonuçlar spread, kayma ve swap'ı tam yansıtmaz; gerçek sonuç daha kötü olabilir.
- Ayarları geçmişe "fazla uydurmak" (overfitting) en sık yapılan hatadır.

## Ayarlar

`config.example.json` içindeki tüm alanlar `config.json` ile değiştirilebilir
(semboller, zaman dilimi, EMA/ATR süreleri, risk yüzdesi, saatler).
`server_minus_ny_hours`: MT5'teki sunucu saati ile New York saati arasındaki fark
(sadece backtest'in saat filtresi için). Piyasa Gözlemi'ndeki saati New York
saatiyle karşılaştırarak kontrol edin.
