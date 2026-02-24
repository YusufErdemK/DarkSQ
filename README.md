# 🛡 DarkSQ — ZeXis OS Security Suite

**DarkSQ**, ZeXis OS için geliştirilmiş, Apple estetiğine sahip profesyonel bir güvenlik uygulamasıdır.  
GTK4 + libadwaita (GNOME native) ile yazılmıştır. WhiteSur GTK/Icon temaları ile tam uyumludur.

---

## ✨ Özellikler

| Özellik | Açıklama |
|---|---|
| **Hızlı Tarama** | Ana dizin taraması |
| **Tam Sistem Taraması** | Tüm `/` taranır |
| **Dosya/Klasör Seç** | İstediğin yolu tara |
| **Karantina** | Şüpheli dosyaları izole et, geri yükle veya sil |
| **Gerçek Zamanlı Koruma** | Downloads ve /tmp anlık izleme |
| **Dosya Şifreleme** | `.zxfe` formatında şifreleme ve çözme |
| **Sistem Olayları** | Tüm güvenlik aktivitesini kayıt altında tut |
| **CPU/RAM İzleme** | Anlık sistem metrikleri |
| **Karanlık/Aydınlık Mod** | GNOME sistem temasına otomatik uyum |

---

## 📦 Gereksinimler

```bash
# GTK4 + libadwaita (sistem paketi)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1

# psutil (CPU/RAM için)
pip3 install psutil --break-system-packages
```

---

## 🚀 Kurulum

```bash
cd DarkSQ
chmod +x install.sh
sudo ./install.sh
```

Kurulumdan sonra terminalde `darksq` komutu veya GNOME uygulama menüsünden açılabilir.

---

## 🔧 Geliştirici Modu (kurulum yapmadan çalıştır)

```bash
cd DarkSQ
pip3 install psutil --break-system-packages
python3 main.py
```

---

## 🗂 Proje Yapısı

```
DarkSQ/
├── main.py          # Giriş noktası
├── app.py           # Adw.Application sınıfı
├── window.py        # Ana pencere ve tüm UI sayfaları
├── engine.py        # Güvenlik motoru (tarama, karantina, şifreleme, RT koruma)
├── install.sh       # Kurulum scripti
├── requirements.txt
└── README.md
```

---

## 🔐 .zxfe Şifreleme Formatı

DarkSQ kendi şifreleme formatını kullanır:

```
[MAGIC: ZXFE] [VERSION: 1B] [NAME_LEN: 2B] [ORIG_NAME] [XOR_ENCRYPTED_DATA]
```

- Anahtar `~/.darksq/key.bin` dosyasında saklanır  
- XOR tabanlı, hafif ve hızlı  
- Yalnızca DarkSQ tarafından çözülebilir

---

## 📍 Veri Dizinleri

| Dizin | Amaç |
|---|---|
| `~/.darksq/` | Ana konfigürasyon dizini |
| `~/.darksq/quarantine/` | Karantinaya alınan dosyalar |
| `~/.darksq/config.json` | Uygulama ayarları |
| `~/.darksq/events.json` | Olay günlüğü |
| `~/.darksq/key.bin` | Şifreleme anahtarı |

---

> **DarkSQ**, ZeXis OS'un resmi güvenlik katmanıdır. GNOME ve WhiteSur temasıyla tam entegre çalışır.
