# Seferim

Refahiye ↔ Erzincan minibüs seferlerini yayınlama ve yer ayırma web uygulaması.

## Bu bilgisayarda çalıştırma

```bash
cd /home/zgebkr/minibus-rezervasyon
./baslat.sh
```

Adres: http://127.0.0.1:5050

## Herkese açma (geçici link)

1. Bir terminalde: `./baslat.sh`
2. Başka terminalde: `./yayinla.sh`
3. Çıkan `https://....trycloudflare.com` linkini paylaş

Bilgisayar ve bu terminaller açıkken herkes girebilir.

## Kalıcı yayın (Render — ücretsiz)

1. https://github.com adresinde ücretsiz hesap aç
2. Yeni repo oluştur (ör. `seferim`), bu klasörü yükle
3. https://render.com → Sign up with GitHub
4. **New → Blueprint** veya **Web Service** → bu repoyu seç
5. Render bir adres verir: `https://seferim-xxxx.onrender.com`

`requirements.txt`, `Procfile` ve `render.yaml` projede hazır.

Not: Ücretsiz planda SQLite verisi yeniden deploy’da silinebilir; ileride kalıcı veritabanı eklenebilir.
