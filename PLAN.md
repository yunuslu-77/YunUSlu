# YunUSlu: 7/24 Kişisel Yapay Zekâ Ajanı (YAi) — Proje Planı

> ✅ Durum: Aşama 1–8 kodlandı ve test edildi (54 test). Kurulum için README.md'ye bak.
> Aşama 0 senin yapacağın hazırlık adımları.

> Hedef: OpenDots, Claude Duet ve Gemini Spark'ın özelliklerini birleştiren,
> **telefonu da kontrol edebilen**, 7/24 bulutta çalışan kişisel asistan.
> Bütçe: Google AI Pro ile gelen **aylık 10 $** Google Cloud / Gemini API kredisi.

---

## 1. Özellik Listesi (hangisinden alındı)

| # | Özellik | Kaynak |
|---|---|---|
| 1 | 7/24 bulutta çalışma (telefon/PC kapalıyken de) | Hepsi |
| 2 | **Proaktif mesajlar**: botun önce senin yazması (önemli e-posta, yaklaşan toplantı) | Claude Duet |
| 3 | **Günlük brifing**: her sabah özet (takvim, e-posta, hava, haber) | Claude Duet, Spark |
| 4 | Google Workspace: Gmail, Takvim, Drive, Docs, Sheets | Gemini Spark |
| 5 | Zamanlanmış / tekrarlayan görevler ("her pazartesi şunu yap") | OpenDots, Spark |
| 6 | **Birden çok uzman ajan ("Dot")**: her birinin adı, rolü, araçları var (Asistan, Araştırmacı, Finans…) | OpenDots |
| 7 | **Onay sistemi**: e-posta gönderme, para, silme gibi işlerden önce "Onaylıyor musun?" diye sorma | Hepsi |
| 8 | Kalıcı hafıza: seni, tercihlerini ve geçmiş konuşmaları hatırlama | Hepsi |
| 9 | **Otomatik öğrenme**: tekrar eden işleri "beceri"ye çevirme (sen onaylayınca) | OpenDots |
| 10 | Kendi bilgisayarı: tarayıcı, dosyalar, terminal (sanal makinede) | OpenDots, Duet, Spark |
| 11 | Sesli konuşma (sesli mesaj al / sesli cevap ver) | OpenDots |
| 12 | Belgeler / sayfalar: botun rapor ve not yazıp saklaması | OpenDots (Pages) |
| 13 | Panel (dashboard): görevler, maliyet, loglar | Claude Duet |
| 14 | **📱 Telefon kontrolü** (aşağıda ayrıntılı) | Yeni (Spark'ın yol haritasında var) |

---

## 2. Mimari

```
┌──────────── TELEFONUN (Android) ────────────┐
│  Telegram (sohbet)   +   "Köprü" uygulaması  │
│                         (Termux + Termux:API) │
└───────────┬────────────────────┬─────────────┘
            │ mesaj               │ WebSocket (şifreli, sürekli bağlı)
            ▼                     ▼
┌─────────────── BULUT SUNUCU (7/24) ──────────────────┐
│  Google Cloud e2-micro (Always Free)                  │
│                                                        │
│  ┌─ Ajan Çekirdeği (Python) ───────────────────────┐ │
│  │  Gemini Flash (beyin)  ←→  Araç çağırma          │ │
│  │  Ajanlar: Asistan / Araştırmacı / Telefon / ...  │ │
│  └──────────────────────────────────────────────────┘ │
│   Zamanlayıcı │ Hafıza (SQLite) │ Onay Kuyruğu │ Panel │
│   Araçlar: Gmail, Takvim, Drive, Web, Tarayıcı, Telefon│
└────────────────────────────────────────────────────────┘
```

**Teknoloji:**
- Dil: **Python 3.12**
- Model: `google-genai` SDK. Varsayılan model **Gemini Flash-Lite / Flash**, zor işlerde **Pro**.
- Sohbet arayüzü: **Telegram Bot** (ücretsiz; ses, foto ve buton destekli; onaylar için buton kullanılır)
- Veritabanı: SQLite (sonra gerekirse Firestore)
- Zamanlayıcı: APScheduler
- Google API: OAuth 2.0 (Gmail, Calendar, Drive, Docs, Sheets)
- Tarayıcı: Playwright (headless Chromium)
- Panel: FastAPI + basit web arayüzü
- Sunucu: GCP e2-micro (us-central1), `systemd` ile otomatik yeniden başlatma

---

## 3. 📱 Telefon Kontrolü (ayrıntı)

**Yöntem:** Telefona **Termux + Termux:API** kurulur. İçinde küçük bir Python
"köprü" programı çalışır ve sunucuya **WebSocket** ile sürekli bağlı kalır.
Bot telefonla ilgili bir şey yapmak istediğinde komutu bu köprüye yollar,
köprü komutu telefonda çalıştırıp sonucu geri döndürür.

> Neden böyle: Root gerekmez, ücretsizdir, ayrıca uygulama mağazası ya da
> özel uygulama yazmak gerekmez. Telefon bağlantıyı **kendisi** başlattığı
> için modem/port ayarı da gerekmez.

### Seviye 1: Temel (Termux:API)
| Özellik | Örnek komut |
|---|---|
| SMS okuma / gönderme (onaylı) | "Annemin son mesajı ne?" |
| Arama geçmişi, arama başlatma (onaylı) | "Ahmet'i ara" |
| Bildirimleri okuma | "Bugün gelen önemli bildirimler?" |
| Konum | "Neredeyim, eve ne kadar var?" |
| Pil / şarj / Wi-Fi durumu | Pil %15 altına düşerse **proaktif uyarı** |
| Fotoğraf çekme, ekrandaki dosyayı alma | "Ön kamerayla foto çek" |
| Pano (kopyala-yapıştır) | "Panodaki linki özetle" |
| Fener, ses seviyesi, titreşim, TTS | "Telefonu sesli konuştur" |
| Rehber | "Mehmet'in numarası ne?" |
| Uygulama / link açma | "YouTube'da şunu aç" |

### Seviye 2: Otomasyon (Tasker veya MacroDroid, isteğe bağlı)
- Alarm kurma, rahatsız etmeyin modu, Wi-Fi/Bluetooth aç-kapa
- Olay tetikleyicileri: "eve gelince", "şarja takınca", "belirli bir uygulamadan bildirim gelince" → bota haber verir

### Seviye 3: Ekranı Görerek Kullanma (ileri seviye, pahalı)
- **Kablosuz ADB** ile ekran görüntüsü + dokunma/kaydırma
- Gemini ekran görüntüsüne bakıp "şuraya dokun" der. Bu, uygulamaların içinde iş yapmayı sağlar.
- ⚠️ Görüntü başına maliyeti var. Sadece açıkça istendiğinde ve **her adımda onay alarak** çalışır.

### Güvenlik
- Köprü sadece senin sunucuna, **gizli bir anahtar** ve TLS ile bağlanır.
- Komutlar **izin listesi** ile sınırlıdır. Rastgele kabuk komutu çalıştırılmaz.
- SMS gönderme, arama, silme, ödeme gibi işler **her zaman Telegram'dan onay** ister.
- Panelde "telefon erişimini kapat" anahtarı ve tüm işlemlerin kaydı bulunur.

> 📌 iPhone kullanıyorsan: iOS bu kadar erişime izin vermiyor. Sadece
> **Kestirmeler (Shortcuts)** ile sınırlı işler yapılabilir (konum, hatırlatıcı,
> mesaj taslağı). Bu plan **Android** için yazıldı.

---

## 4. Bütçe Planı (aylık 10 $)

| Kalem | Tahmini maliyet |
|---|---|
| Sunucu (e2-micro, Always Free bölgesi) | ~0 $ |
| Gemini Flash-Lite / Flash (günlük sohbet, brifing, e-posta özetleri) | ~2–5 $ |
| Gemini Pro (sadece zor işler) | ~1–2 $ |
| Ekran görme / tarayıcı (görüntü işleme) | ~1–2 $ |
| **Toplam** | **≤ 10 $** |

**Aşım koruması:**
1. Google Cloud Billing'de **bütçe uyarısı** (5 $, 8 $, 10 $)
2. Kodda **günlük token limiti**. Limit dolunca bot ucuz modele geçer, gerekirse durur ve sana haber verir.
3. Önbellek (cache): aynı e-postayı tekrar tekrar özetlemez.
4. Proaktif kontroller her dakika değil, **15–30 dakikada bir** yapılır. Mümkün olan yerde Gmail push bildirimi kullanılır.

> Fiyatlar değişebilir. Kurulumdan önce güncel Gemini API fiyatlarına bakılacak.

---

## 5. Yol Haritası (aşamalar)

### Aşama 0: Hazırlık (senin yapacakların)
- [ ] Google AI Studio'dan **Gemini API anahtarı** al
- [ ] Google Cloud projesi aç, 10 $ krediyi bağla, **bütçe uyarısı** kur
- [ ] Telegram'da **@BotFather** ile bot oluştur, token al
- [ ] (Telefon için) Android'e F-Droid'den **Termux** ve **Termux:API** kur

### Aşama 1: Temel Bot
- [x] Telegram ↔ Gemini sohbet (Türkçe)
- [x] Sadece senin kullanıcı ID'ne cevap verme (güvenlik)
- [x] Sesli mesajı anlama, fotoğraf anlama
- [x] Maliyet sayacı + günlük limit

### Aşama 2: Hafıza + Ajanlar
- [x] Konuşma geçmişi, "bunu hatırla" komutu, kişisel profil
- [x] Çoklu ajan yapısı: Asistan (ana), Araştırmacı, Telefon, Finans…
- [x] Onay sistemi (Telegram butonları: ✅ Onayla / ❌ İptal)

### Aşama 3: Google Workspace
- [x] Gmail: okuma, özetleme, taslak yazma, gönderme (onaylı)
- [x] Takvim: etkinlikleri görme, ekleme, hatırlatma
- [x] Drive / Docs / Sheets: dosya bulma, rapor yazma

### Aşama 4: Proaktiflik + Zamanlayıcı
- [x] **Sabah brifingi** (ör. 08:00)
- [x] Önemli e-posta / toplantı uyarısı
- [x] "Her X'te şunu yap" türü özel görevler
- [x] Haftalık özet

### Aşama 5: 📱 Telefon Köprüsü
- [x] Termux köprü programı + WebSocket sunucusu
- [x] Seviye 1 komutlar (SMS, bildirim, konum, pil, kamera…)
- [x] Proaktif telefon uyarıları (düşük pil, önemli bildirim)
- [x] (İsteğe bağlı) Seviye 2: Tasker tetikleyicileri

### Aşama 6: Bilgisayar + Tarayıcı
- [x] Web arama ve sayfa okuma
- [x] Playwright ile tarayıcı kullanma (form doldurma, onaylı)
- [x] Sanal dosya alanı (notlar, raporlar = "Pages")

### Aşama 7: Otomatik Öğrenme
- [x] Tekrarlanan istekleri tespit edip "beceri" önermek
- [x] Onaylanan becerileri kaydedip tekrar kullanmak

### Aşama 8: Panel + Yayına Alma
- [x] Web panel: görevler, onay geçmişi, maliyet grafiği, loglar
- [x] GCP e2-micro'ya kurulum, `systemd`, otomatik yedekleme
- [x] (İsteğe bağlı) Seviye 3 ekran kontrolü (ADB + görme)

---

## 6. Klasör Yapısı (planlanan)

```
YunUSlu/
├── bot/
│   ├── main.py            # giriş noktası
│   ├── telegram_ui.py     # Telegram arayüzü, onay butonları
│   ├── agent/             # ajan çekirdeği, araç çağırma, çoklu ajan
│   ├── tools/             # gmail, calendar, drive, web, browser, phone
│   ├── memory/            # SQLite hafıza
│   ├── scheduler.py       # zamanlanmış/proaktif görevler
│   ├── budget.py          # maliyet takibi ve limitler
│   └── phone_gateway.py   # telefon WebSocket sunucusu
├── phone_bridge/          # Termux'ta çalışan köprü
├── dashboard/             # web panel
├── deploy/                # GCP kurulum betikleri, systemd
├── .env.example
└── PLAN.md
```

---

## 7. Kararlar
1. Telefon: **Android** (Termux köprüsü)
2. Zamanlayıcılar: kullanıcı sesle/yazıyla ("her sabah 8'de...") veya `/zamanla` komutuyla kendisi kurar
3. Botun adı: **YAi**
4. Tüm özellikler tek seferde, sırayla yapıldı
