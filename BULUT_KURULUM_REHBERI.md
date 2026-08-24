# QQQ PRO — Android / Bulut Kurulumu

Bu paket Streamlit Community Cloud için hazırlanmıştır. Bilgisayarınız kapalıyken telefon üzerinden açılır.

## Gerekli ücretsiz hesaplar

1. GitHub hesabı: https://github.com/signup
2. Streamlit Community Cloud: https://share.streamlit.io/

## GitHub'a yükleme

1. GitHub'da `QQQ-PRO-MOBILE` adlı yeni bir **private repository** oluşturun.
2. Bu ZIP'in içeriğini çıkarın.
3. ZIP'in içindeki dosyaların tamamını repository köküne yükleyin. `app.py` doğrudan kökte görünmelidir.
4. `Commit changes` düğmesine basın.

## Streamlit'e kurma

1. https://share.streamlit.io/ adresini açın ve GitHub ile giriş yapın.
2. `Create app` seçin.
3. Repository: `QQQ-PRO-MOBILE`
4. Branch: `main`
5. Main file path: `app.py`
6. `Advanced settings` bölümünde Python 3.12 seçin.
7. Secrets alanına aşağıdakini girin; parolayı kendiniz değiştirin:

```toml
APP_PASSWORD = "BURAYA_GUCLU_BIR_PAROLA_YAZIN"
```

8. `Deploy` düğmesine basın.

## Android telefona ekleme

1. Oluşan `https://....streamlit.app` adresini Chrome ile açın.
2. Sağ üstteki üç noktaya dokunun.
3. `Ana ekrana ekle` veya `Uygulamayı yükle` seçin.
4. QQQ PRO simgesini ana ekrandan açın.

## Veri kaynağı

Bu ilk bulut sürümü mevcut production sistemiyle aynı şekilde Yahoo Finance/yfinance kullanır ve API anahtarı istemez. Bu kaynak resmî tam-borsa gerçek zaman lisansı değildir; gecikme, eksik bar veya hız sınırı görülebilir.

Gerçek kapsamlı canlı veri aşamasında `market_data.py` için lisanslı veri adaptörü eklenmelidir. Alpaca ücretsiz Basic katmanı yalnızca IEX hisse verisini ve sınırlı/indicative opsiyon verisini sağlar. Tam ABD hisse borsaları ve OPRA opsiyon verisi ücretli abonelik gerektirir. API anahtarları GitHub'a yazılmaz; Streamlit Secrets alanına girilir.

## Güvenlik

- Uygulama broker'a otomatik emir göndermez.
- APP_PASSWORD GitHub dosyalarına eklenmez.
- API anahtarları sohbet içinde veya repository içinde paylaşılmaz.
- Fırsat Radarı gölge uyarıdır; tek başına pozisyon açtırmaz.

