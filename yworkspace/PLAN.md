# yWorkspace — Ana Plan

> **Her yapay zekâya, bir SaaS projesini baştan sona yapacak kadar güçlü bir çalışma ortamı.**
> Zayıf modeller bile yWorkspace ile çalıştığında insanlar "vay" desin.

Durum: **Taslak, onay bekliyor** · Sahibi: Yunus Emre USLU · Bir YunUSlu ürünü

---

## 1. Vizyon

Bugün yapay zekâların çoğu üç nedenle büyük işleri yarım bırakır:

1. **Ortam eksik:** Dosya okuyamaz, düzenleyemez, komut çalıştıramaz, test edemez. DeepSeek ve Gemini gibi modellerin web sohbetlerinde bu yeteneklerin çoğu hiç yok.
2. **Acele eder:** Saatlerce düzgün çalışmak yerine hemen kısa bir cevap verip bitirmeye çalışır. Yarım kod, "geri kalanını siz ekleyin" notları, test edilmemiş çözümler bırakır.
3. **Yöntem bilmez:** Planlama, test, hata ayıklama ve inceleme disiplini yoktur.

yWorkspace bu üçünü birden çözer:

| Sorun | Çözüm |
|---|---|
| Ortam eksik | Dosya, terminal, test, git, veritabanı, tarayıcı ve yayına alma araçları olan, Docker içinde güvenli bir **tam geliştirme ortamı** |
| Acele etme | İş gerçekten bitene kadar modeli çalıştıran **Derin Çalışma Motoru**. "Bitti" demesi, yazılım tarafından kontrol edilen kapılara bağlı |
| Yöntem bilmeme | Her alanda derin, her yapay zekâya özel ayarlanmış, Türkçe ve İngilizce **skill kütüphanesi** |

**Yapay zekâya bahane bırakmamak** temel ilkedir. Model "bunu yapamam", "bu ortamda test edemem" ya da "bu kısmı siz tamamlayın" diyememeli.

---

## 2. Alınan kararlar

| Konu | Karar |
|---|---|
| Ürün adı | **yWorkspace** |
| Programlama dili | **Python** (çekirdek ve motor), web arayüzü için TypeScript |
| Çalışma yeri | **Tamamen kullanıcının kendi bilgisayarı.** Bulut hizmeti yok |
| Kurulum | Gerekli her şeyi sırayla kurduran **kurulum sihirbazı** |
| İşletim sistemleri | **Windows, Linux, macOS** |
| Komutların çalıştığı yer | **Docker konteyneri** (izole, bilgisayara zarar veremez) |
| Kullanıcılar | **Herkes.** Yazılım bilmeyenler için basit görünüm, yazılımcılar için detaylı görünüm |
| İlk arayüz | **Web arayüzü** (yerel, tarayıcıda açılır) |
| Arayüz dili | **Türkçe + İngilizce**, sonradan dil eklenebilir yapıda |
| Özerklik | **Kullanıcı seçer:** her adımda onay / önemli aşamalarda onay / tamamen otomatik |
| Kalite ve maliyet | **Ayarlanabilir:** Ekonomik / Dengeli / Maksimum kalite |
| Modeller | **Hepsi:** DeepSeek, Gemini, Claude, ChatGPT, yerel modeller (Ollama), Qwen, Mistral, Grok, Kimi ve OpenAI uyumlu her API |
| Teknoloji uzmanlığı | **Her alanda en iyisi:** teknoloji bağımsız yöntemler + Python, JavaScript/TypeScript, mobil (Kotlin/Flutter) |
| SaaS parçaları | **Hepsi:** giriş ve yetki, ödeme ve abonelik, yönetim paneli ve her türlü altyapı |
| Yayına alma | **Kullanıcının seçtiği yere:** kendi sunucusu (VPS), Vercel, Railway, Render, Fly.io ve diğerleri |
| Skill kapsamı | **Her alan.** Yazılım ve SaaS çekirdektir, pazarlama, iş, belge, eğitim ve araştırma da dahil |
| Skill dili | **Türkçe + İngilizce**, her yapay zekâ için ayrı ayar |
| Geliştirme yeri | Bu depoda, `yworkspace/` klasörü |
| Lisans | **PolyForm Noncommercial 1.0.0** (kod) + **CC BY-NC-SA 4.0** (skill/belge) + bireylere ticari kullanım izni, bkz. bölüm 14 |

---

## 3. Genel mimari

```
┌─────────────────────────────── KULLANICI ────────────────────────────────┐
│   Web Arayüzü (yerel)   ·   Android uzaktan kumanda   ·   CLI (geliştirici) │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
┌───────────────────────── DERİN ÇALIŞMA MOTORU ───────────────────────────┐
│  Anla → Planla → Uygula → Doğrula → İncele → Düzelt → Kaydet → (tekrar)   │
│  Roller · Görev ağacı · Bitti kapıları · Hafıza · Kalite modları          │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
┌──────────────────────────── MODEL KATMANI ───────────────────────────────┐
│  Adaptörler: DeepSeek · Gemini · Claude · OpenAI · Ollama · Qwen ·        │
│              Mistral · Grok · Kimi · OpenAI uyumlu her API                │
│  Araç çağırma yolları: yerel araç çağrısı │ MCP │ metin protokolü        │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
┌───────────────────────────── ARAÇ KATMANI ───────────────────────────────┐
│  Dosya · Terminal · Test · Git · Veritabanı · Tarayıcı · HTTP ·           │
│  Yayına alma · Görev/Hafıza · Kullanıcıya soru                            │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
┌─────────────────────────── GÜVENLİK KATMANI ─────────────────────────────┐
│  Docker sandbox · Çalışma alanı sınırı · Yasak dosyalar · Onaylar ·       │
│  Bütçe/süre sınırları · Geçmiş ve geri alma                               │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                         Proje dosyaları + Docker 📁🐳
```

Bunlara ek olarak iki yan bileşen var: **Kurulum Sihirbazı** ve **Skill Kütüphanesi**.

---

## 4. Kurulum Sihirbazı

Amaç: Yazılım bilmeyen birinin bile "İleri, İleri" diyerek yWorkspace'i çalışır hale getirmesi.

**Dağıtım:** Her işletim sistemi için tek dosyalık yükleyici (Windows `.exe`, macOS `.dmg`, Linux `.AppImage` ve `.deb`). Python içine gömülü olur, kullanıcının ayrıca Python kurmasına gerek kalmaz.

**Adımlar:**

1. **Dil seçimi:** Türkçe / English.
2. **Sistem kontrolü:** İşletim sistemi, RAM, disk, ekran kartı (GPU), internet.
3. **Docker:**
   - Windows: WSL2'yi etkinleştirir, Docker Desktop'ı kurar, gerekirse yeniden başlatmayı yönetir ve kaldığı yerden devam eder.
   - macOS: Docker Desktop (Intel / Apple Silicon ayrımıyla).
   - Linux: Dağıtıma göre Docker Engine kurulumu, kullanıcıyı `docker` grubuna ekleme.
   - Kurulumu "hello-world" konteyneriyle doğrular.
4. **Model seçimi:** Kullanıcıya önerilerle birlikte sorar:
   - **API modelleri:** Anahtar alınacak sayfaya yönlendirir (DeepSeek, Gemini, Claude, OpenAI...). Anahtarı test eder ve güvenli şekilde saklar (işletim sisteminin anahtar deposunda).
   - **Yerel modeller:** Ollama'yı kurar. Donanıma göre model önerir (ör. 8 GB RAM için küçük, güçlü GPU için büyük model) ve indirir.
   - **Ücretsiz başlangıç yolu:** Hiç parası olmayan kullanıcı için ücretsiz katmanları ya da yerel modeli önerir.
5. **Çalışma klasörü:** Projelerin duracağı klasörü seçtirir.
6. **Varsayılan ayarlar:** Özerklik modu, kalite modu, bütçe sınırı.
7. **Deneme projesi:** Küçük bir örnek projeyi uçtan uca yaptırır. Böylece kurulumun gerçekten çalıştığı kanıtlanır.
8. **Bitiş:** Masaüstü kısayolu, otomatik başlatma (isteğe bağlı), tarayıcıda arayüzü açar.

**Sonradan:** Güncelleme kontrolü, "Sistem Sağlığı" ekranı (Docker çalışıyor mu, anahtarlar geçerli mi, disk yeterli mi) ve onarım sihirbazı.

---

## 5. Araç katmanı

Tüm araçlar **tek bir yerde** tanımlanır (JSON şeması + Python fonksiyonu). Model katmanı bu tanımı her modelin araç formatına otomatik çevirir.

### 5.1 Dosya araçları

| Araç | Görev |
|---|---|
| `read` | Satır numaralı okuma, satır aralığı, büyük dosyada parça parça |
| `outline` | Dosyanın iskeleti (sınıflar, fonksiyonlar, başlıklar) |
| `create` | Yeni dosya. Var olan dosyanın üzerine okunmadan yazamaz |
| `edit` | **Akıllı bul-değiştir:** sadece değişen yeri düzenler |
| `multi_edit` | Bir dosyada birden çok düzenleme. Ya hepsi uygulanır ya hiçbiri |
| `move` / `delete` | Taşıma ve silme (silme geri alınabilir, çöp kutusuna gider) |
| `list` / `glob` / `search` | Listeleme, desene göre bulma, içerikte arama (regex) |
| `diff` / `undo` / `history` | Farkı gösterme, geri alma, geçmiş |

**Akıllı düzenleme kuralları:**
1. Aranan metin dosyada **tam bir kez** geçmeli. Birden çok geçiyorsa reddedilir ve "daha fazla bağlam ekle" denir.
2. Tam eşleşme yoksa boşluk ve girinti farkları yok sayılarak **en yakın aday** bulunur ve modele satır numarasıyla gösterilir: "Bunu mu demek istedin?"
3. **Okumadan düzenleme yasak.** Dosya okunduktan sonra değiştiyse düzenleme reddedilir, yeniden okunması istenir.
4. Satır sonları, karakter kodlaması ve girinti korunur.
5. Önce geçici dosyaya yazılır, sonra yer değiştirilir (atomik yazma). Her değişiklik geçmişe kaydedilir.

### 5.2 Terminal araçları (Docker içinde)

| Araç | Görev |
|---|---|
| `run` | Komut çalıştırma, zaman aşımı ve çıktı sınırıyla |
| `start_process` / `logs` / `stop_process` | Arka plan süreçleri (ör. geliştirme sunucusu) ve günlükleri |
| `install` | Paket kurulumu (pip, npm, pnpm, apt, gradle...), önbellekli |

### 5.3 Doğrulama araçları

| Araç | Görev |
|---|---|
| `test` | Projenin test komutunu bulur, çalıştırır, sonuçları yapılandırılmış olarak döndürür |
| `lint` / `typecheck` / `build` | Kalite ve derleme kontrolleri |
| `browser_open` / `browser_screenshot` / `browser_click` / `browser_type` / `browser_console` | Playwright ile çalışan uygulamayı **gerçekten açıp görmek**, tıklamak, form doldurmak, konsol hatalarını okumak |
| `http` | API uç noktalarını test etmek |

### 5.4 Proje araçları

| Araç | Görev |
|---|---|
| `git_*` | status, diff, commit, branch, log, geri dönme |
| `db_query` / `db_migrate` | Veritabanı sorgusu ve şema geçişi (yalnızca geliştirme veritabanında serbest) |
| `deploy` | Seçilen hedefe yayına alma (bkz. bölüm 10) |
| `docs_fetch` / `web_search` | Kütüphane belgelerini okumak (isteğe bağlı, kullanıcı açar) |

### 5.5 Motor araçları

| Araç | Görev |
|---|---|
| `plan_*` | Görev ağacı oluşturma ve güncelleme |
| `memory_*` | Proje hafızasına not yazma ve okuma |
| `ask_user` | Kullanıcıya soru (otomatik modda yalnızca gerçekten gerektiğinde) |
| `finish` | İşi bitirme isteği. **Bitti kapılarından geçmeden kabul edilmez** |

---

## 6. Model katmanı

### 6.1 Üç bağlantı yolu

| Yol | Hangi modeller | Nasıl |
|---|---|---|
| **Yerel araç çağrısı** | API'si araç çağırmayı destekleyen her model (DeepSeek, Gemini, Claude, OpenAI, Qwen, Mistral, Grok, Kimi, çoğu Ollama modeli) | Araç tanımları modelin kendi formatına çevrilir, motor döngüyü yönetir |
| **MCP sunucusu** | Claude Desktop, ChatGPT, Gemini CLI, Cursor, VS Code gibi MCP istemcileri | yWorkspace araçları MCP üzerinden sunulur. Böylece kullanıcı kendi alıştığı uygulamadan da yWorkspace'i kullanabilir |
| **Metin protokolü** | Araç çağıramayan modeller, zayıf yerel modeller, web sohbetleri | Model özel bloklar yazar, yWorkspace bunları ayrıştırıp uygular (bkz. 6.3) |

### 6.2 Model profilleri

Her modelin bir **profili** olur: bağlam penceresi boyutu, araç çağırma güvenilirliği, en iyi talimat biçimi, bilinen zayıflıklar ve maliyet. Motor bu profile göre davranışını ayarlar. Örneğin küçük bağlamlı modelde dosyalar daha küçük parçalarla verilir, araç çağırmada hata yapan modelde metin protokolüne geçilir.

### 6.3 Metin protokolü

```
<<<yw:read path="src/app.py" lines="1-80">>>

<<<yw:edit path="src/app.py">>>
<<<find
def topla(a, b):
    return a - b
===replace
def topla(a, b):
    return a + b
>>>end

<<<yw:run>>>
pytest -q
>>>end
```

- Ayrıştırıcı hataya toleranslıdır: Eksik kapanış ya da küçük biçim hataları düzeltilir, düzeltilemiyorsa modele net bir hata mesajı döner.
- **Yarı otomatik kullanım:** Kullanıcı web sohbetindeki cevabı yWorkspace'e yapıştırır, sonuç panoya kopyalanır.
- **Tarayıcı eklentisi (isteğe bağlı):** Web sohbetlerini otomatik bağlar. ⚠️ Bazı sitelerin kullanım koşulları otomasyonu yasaklayabilir. Bu yüzden ana yol API'dir, eklenti kullanıcının sorumluluğunda bir ek seçenektir.

---

## 7. Derin Çalışma Motoru

yWorkspace'in kalbi burası. Amaç: Modeli **sınırına kadar çalıştırmak** ve acele edip yarım bırakmasını yazılımla engellemek.

### 7.1 Çalışma döngüsü

```
1. ANLA      → İsteği netleştir. Eksik bilgi varsa (onay moduna göre) sor.
               Çıktı: SPEC.md (ne yapılacak, kabul kriterleri)
2. PLANLA    → İşi küçük, doğrulanabilir görevlere böl.
               Çıktı: görev ağacı (her görevin kabul kriteri ve doğrulama yolu var)
3. UYGULA    → Sadece BİR görev üzerinde çalış.
4. DOĞRULA   → Test, lint, derleme, gerekiyorsa tarayıcıda gerçekten aç ve bak.
5. İNCELE    → Ayrı "inceleyici" rolü değişikliği kontrol listesiyle inceler.
6. DÜZELT    → Bulunan sorunlar için 3. adıma dön.
7. KAYDET    → Git commit + ilerleme notu + hafıza güncellemesi.
8. SONRAKİ   → Sıradaki göreve geç. Tüm görevler bitince BİTTİ KAPILARI.
```

### 7.2 Bitti kapıları (Done Gates)

Model `finish` çağırdığında yazılım şunları kontrol eder. Biri bile geçmezse iş bitmiş sayılmaz ve model nedenini görerek çalışmaya devam eder:

- [ ] Görev ağacındaki tüm görevler kapalı
- [ ] Tüm testler geçiyor, derleme başarılı
- [ ] Lint ve tip kontrolü temiz (projede varsa)
- [ ] **Tembellik taraması temiz:** `TODO`, `...`, "geri kalanı aynı", "buraya kod ekleyin", boş fonksiyon gövdeleri, gerçek veri gereken yerde sahte veri yok
- [ ] Her kabul kriteri için kanıt var (test adı, ekran görüntüsü ya da komut çıktısı)
- [ ] İnceleyici rolü onay verdi
- [ ] Uygulama çalışıyor ve arayüz varsa tarayıcıda açılıp kontrol edildi

### 7.3 Tembelliğe karşı önlemler

- **Erken bitirme engeli:** Kapılar geçmeden "tamamladım" mesajı kullanıcıya bitti olarak gösterilmez.
- **Yer tutucu dedektörü:** Yazılan her dosya taranır. Yarım kod bulunursa düzenleme kabul edilir ama görev açık kalır.
- **Otomatik devam:** Model gereksiz yere durursa motor, sıradaki görev ve kalan kriterlerle onu devam ettirir.
- **Gereksiz soru engeli:** Otomatik modda, cevabı projeden ya da makul bir varsayımla bulunabilecek sorular kullanıcıya gitmez. Model varsayımını not edip devam eder.
- **Kanıt zorunluluğu:** "Çalışıyor" iddiası ancak bir araç çıktısıyla kabul edilir.

### 7.4 Roller

Aynı model farklı rollerde, **her rol temiz bir bağlamla** çalıştırılır. Böylece model kendi hatasına kör kalmaz:

| Rol | Görev |
|---|---|
| **Analist** | İsteği anlar, SPEC.md yazar |
| **Mimar** | Teknoloji seçer, yapıyı ve görev ağacını oluşturur |
| **Geliştirici** | Tek bir görevi uygular |
| **Test uzmanı** | Testleri yazar ve çalıştırır, kenar durumları arar |
| **İnceleyici** | Değişikliği kontrol listesiyle inceler (doğruluk, güvenlik, okunabilirlik) |
| **Hata ayıklayıcı** | Başarısız testin kök nedenini bulur |

Kullanıcı isterse rollere farklı modeller atayabilir (ör. geliştirici DeepSeek, inceleyici Claude).

### 7.5 Kalite modları

| Mod | Davranış |
|---|---|
| **Ekonomik** | Tek geçiş + testler + bitti kapıları |
| **Dengeli** | + her görevden sonra inceleyici rolü |
| **Maksimum** | + zor adımlarda birden fazla çözüm üretip en iyisini seçme, birden fazla inceleyici, mimari ve güvenlik için ek inceleme turu |

### 7.6 Hafıza ve bağlam yönetimi

Uzun işlerde modelin bağlam penceresi dolar. Küçük modellerde bu çok çabuk olur. Bunun için:

- **Proje dosyaları:** `.yw/SPEC.md` (hedef), `.yw/tasks.json` (görev ağacı), `.yw/NOTES.md` (kararlar ve öğrenilenler), `.yw/progress.md` (ilerleme günlüğü).
- **Odak penceresi:** Her görevde modele sadece ilgili dosyalar ve özet verilir, tüm proje değil.
- **Sıkıştırma:** Bağlam dolmak üzereyken konuşma özetlenir ve proje dosyalarıyla birlikte yeniden yüklenir.
- **Kaldığı yerden devam:** Bilgisayar kapansa ya da iş durdurulsa bile sonraki açılışta görev ağacından devam edilir.

### 7.7 Sınırlar

Bütçe (para), süre, adım sayısı ve aynı hatada en fazla deneme sayısı ayarlanabilir. Sınıra yaklaşınca kullanıcıya bildirim gider. Aynı hata tekrar tekrar alınırsa model yaklaşımını değiştirmeye zorlanır, sonuç yoksa kullanıcıya net bir rapor sunulur.

---

## 8. Skill Kütüphanesi

### 8.1 Bir skill'in parçaları

Skill sadece bir prompt değildir. Her skill şunlardan oluşur:

```
skills/<kategori>/<skill>/
├── skill.yaml          # ad, açıklama, tetikleyiciler, gerekli araçlar, roller
├── core.tr.md          # ana talimat (Türkçe)
├── core.en.md          # ana talimat (İngilizce)
├── workflow.yaml       # adım adım iş akışı ve her adımın bitti kriteri
├── checklists/         # inceleme ve doğrulama kontrol listeleri
├── templates/          # hazır dosya ve kod şablonları
├── examples/           # iyi örnekler (zayıf modeller örnekten çok iyi öğrenir)
└── models/             # yapay zekâya özel ayarlar
    ├── deepseek.yaml
    ├── gemini.yaml
    ├── claude.yaml
    ├── openai.yaml
    └── small-local.yaml
```

### 8.2 Dışa aktarma

Skill'ler yWorkspace içinde otomatik kullanılır. Ayrıca yWorkspace olmadan kullanmak isteyenler için her yapay zekânın kendi formatına **dışa aktarılır**: Claude `SKILL.md`, ChatGPT Özel GPT talimatı, Gemini Gem talimatı ve düz sistem prompt'u. Hepsi Türkçe ve İngilizce.

### 8.3 Kategoriler

**A. Çekirdek çalışma skill'leri** (her işte kullanılır)
- Dosya okuma, oluşturma ve düzenleme disiplini
- Planlama ve görev bölme
- Derin çalışma (sınırına kadar çalışma, kanıtla bitirme)
- Kendi işini inceleme
- Hata ayıklama (kök neden analizi)
- Test yazma ve test stratejisi

**B. Yazılım ve SaaS**
- Gereksinim analizi ve SPEC yazımı
- Mimari ve teknoloji seçimi
- Backend: Python (FastAPI, Django), JavaScript/TypeScript (Next.js, Node, NestJS)
- Frontend: React, Next.js, Vue, Tailwind, erişilebilirlik, duyarlı tasarım
- Mobil: Kotlin (Android), Flutter
- Veritabanı: PostgreSQL, MySQL, SQLite, MongoDB, Redis, şema tasarımı, geçişler
- Kimlik doğrulama ve yetkilendirme
- Ödeme ve abonelik
- Güvenlik (OWASP Top 10, gizli bilgi yönetimi)
- Performans ve ölçeklenme
- DevOps: Docker, CI/CD, izleme, yedekleme
- Yayına alma (her hedef için ayrı)
- API tasarımı ve belgelendirme
- Var olan bir projeyi anlama ve üzerinde çalışma
- Kod inceleme, yeniden düzenleme (refactoring)

**C. İş ve pazarlama**
- İş planı, pazar araştırması, rakip analizi, fiyatlandırma
- Açılış sayfası metni, reklam metni, SEO
- Sosyal medya, e-posta pazarlaması, marka kimliği

**D. Belge ve içerik**
- Rapor, teklif, sözleşme taslağı, kullanım kılavuzu, teknik belge
- Sunum hazırlama, çeviri, özetleme
- (İleride) yOffice ile ofis dosyaları

**E. Eğitim ve araştırma**
- Konu anlatımı, sınav hazırlığı, ders planı
- Derin araştırma (çok kaynaklı, kaynak gösteren)

**F. Günlük yaşam**
- Bütçe ve harcama planı, seyahat planı, sağlık takibi (tıbbi tavsiye değil)

---

## 9. SaaS Kiti

Yapay zekânın her SaaS'ı sıfırdan icat etmesi yerine, test edilmiş **hazır modüller** ve **başlangıç şablonları** kullanmasını sağlar. Bu hem kaliteyi artırır hem de zayıf modellerin işini çok kolaylaştırır.

**Başlangıç şablonları (yığınlar):**
- Next.js (tam yığın, TypeScript)
- FastAPI + React
- Django (+ HTMX ya da React)
- Node/NestJS + React
- Mobil istemci: Flutter ve Kotlin (SaaS API'sine bağlanan)

**Modüller (her yığın için):**

| Alan | İçerik |
|---|---|
| Kimlik | Kayıt, giriş, e-posta doğrulama, şifre sıfırlama, Google/GitHub/Apple ile giriş, iki adımlı doğrulama, roller ve izinler, ekipler ve davetler, çok kiracılı (multi-tenant) yapı |
| Ödeme | Stripe, iyzico, PayTR, Paddle, Lemon Squeezy; planlar, deneme süresi, abonelik yönetimi, faturalar, webhook'lar |
| Yönetim paneli | Kullanıcı yönetimi, istatistikler, abonelik takibi, içerik yönetimi, denetim kayıtları |
| İletişim | E-posta gönderimi (SMTP, Resend, SendGrid...), bildirimler |
| Altyapı | Veritabanı ve geçişler, önbellek, kuyruk ve arka plan işleri, dosya depolama (S3 uyumlu), loglama, hata takibi, sağlık kontrolü, yedekleme, hız sınırlama |
| Uyumluluk | KVKK ve GDPR için çerez onayı, veri dışa aktarma, hesap silme |
| Çoklu dil | i18n altyapısı |

---

## 10. Yayına alma

yWorkspace kullanıcının bilgisayarında çalışır, ama yapılan SaaS internete çıkar. Desteklenecek hedefler:

| Hedef | Yöntem |
|---|---|
| Kendi sunucusu (VPS) | SSH + Docker Compose, ters vekil sunucu (Caddy) ile otomatik SSL |
| Vercel, Netlify, Cloudflare Pages | Resmi CLI'lar |
| Railway, Render, Fly.io | Resmi CLI'lar ve yapılandırma dosyaları |
| Veritabanı hizmetleri | Neon, Supabase, PlanetScale ya da sunucuda PostgreSQL |

Yayına alma her özerklik modunda **onay gerektirir.** Gizli bilgiler (API anahtarları, veritabanı şifreleri) hedefin gizli değişken sistemine aktarılır, koda asla yazılmaz.

---

## 11. Web Arayüzü

Yerel olarak çalışır (`http://localhost`), tarayıcıda açılır. İki görünümü vardır:

**Basit görünüm (herkes için):**
- Sohbet: "Bana kuaförler için randevu sistemi yap"
- İlerleme çubuğu ve anlaşılır dille ne yapıldığı ("Giriş sayfası hazırlandı ✓")
- Canlı önizleme: Yapılan uygulama yan panelde açık
- Onay kartları: "Şimdi yayına alayım mı?"

**Detaylı görünüm (yazılımcılar için):**
- Dosya ağacı ve düzenleyici
- Her değişikliğin farkı (diff), onayla ya da reddet
- Terminal ve süreç günlükleri
- Görev ağacı ve bitti kapılarının durumu
- Rol, model ve maliyet takibi

**Ayarlar:** Modeller ve anahtarlar, özerklik modu, kalite modu, bütçe, dil, tema (açık/koyu).

---

## 12. Android uzaktan kumanda

Bulut olmadığı için Android uygulaması, **kullanıcının kendi bilgisayarındaki** yWorkspace'e bağlanır:
- Aynı Wi-Fi ağında: QR kod ile eşleşme.
- Dışarıdan: Kullanıcının kendi kuracağı güvenli tünel (ör. Tailscale). Sihirbaz bunun kurulumunda da yardım eder.

Telefondan iş verilebilir, ilerleme izlenebilir, onay kartları yanıtlanabilir ve önizleme görülebilir. YunUSlu uygulama ailesinin tasarım diliyle uyumlu olur.

---

## 13. Güvenlik

- **Docker sandbox:** Tüm komutlar konteynerde çalışır. Konteyner sadece proje klasörünü görür.
- **Çalışma alanı sınırı:** Dosya araçları proje klasörünün dışına çıkamaz (`../` ve sembolik bağlantılar engellenir).
- **Yasak dosyalar:** `.env`, özel anahtarlar ve şifre dosyaları varsayılan olarak modele gösterilmez. Gerekirse değerleri değil, sadece isimleri gösterilir.
- **Riskli işlem onayı:** Silme, yayına alma, veritabanı şeması değişikliği ve dışarıya istek her modda listelenir. Hangilerinin onay gerektireceği özerklik moduna göre belirlenir.
- **Komut enjeksiyonu koruması:** Dosya ve web içerikleri modele her zaman "veri" olarak işaretlenmiş verilir. İçlerindeki talimatlar uygulanmaz.
- **Anahtar güvenliği:** API anahtarları işletim sisteminin güvenli deposunda tutulur, günlüklere ve modele yazılmaz.
- **Yerel ağ güvenliği:** Web arayüzü varsayılan olarak yalnızca bu bilgisayardan erişilebilir. Telefon eşleşmesi şifreli ve token'lıdır.

---

## 14. Lisans — ✅ Karar verildi

Ayrıntılar: [LICENSE](../LICENSE) ve [LICENSING.md](../LICENSING.md).

- **Kod:** PolyForm Noncommercial 1.0.0. Bireyler ve kâr amacı gütmeyen kurumlar serbestçe kullanır, şirketler kullanamaz.
- **Skill'ler ve belgeler:** CC BY-NC-SA 4.0.
- **Ek izin:** Bireyler yWorkspace'i kendi ticari işleri için de kullanabilir (ör. kendi SaaS'ını yapıp satmak). Yazılımın kendisini satmak ya da şirketlere sunmak hariç.
- **Üretilen işler:** yWorkspace ile yapılan projeler tamamen kullanıcının.
- **Katkılar:** Pull request ile gelir, her katkıdan haberdar olunur. Fork yapanlardan haber vermeleri rica edilir.
- **Ticari lisans:** Şirketler ayrı ücretli lisans alabilir.
- Bu yazılım resmi tanımıyla "açık kaynak" değil, **kaynağı açık** (source-available) yazılımdır.

---

## 15. Ölçüm: yWorkspace Bench

"Zayıf modellerden vay dedirttik" iddiasını kanıtlamak için ölçmemiz gerekiyor:

- **Görev seti:** Küçük (hata düzeltme) → orta (özellik ekleme) → büyük (sıfırdan SaaS: giriş + ödeme + panel) görevler.
- **Karşılaştırma:** Her model için **yWorkspace olmadan** (çıplak model) ve **yWorkspace ile** (her kalite modunda) sonuçlar.
- **Ölçütler:** Testlerin geçme oranı, bitti kapıları, süre, maliyet, insan müdahalesi sayısı.
- Sonuçlar herkese açık bir tabloda yayınlanır.

---

## 16. Depo yapısı

```
yworkspace/
├── PLAN.md                 # bu belge
├── core/                   # dosya motoru, akıllı düzenleme, geçmiş
├── sandbox/                # Docker yönetimi, süreçler
├── tools/                  # tüm araç tanımları (tek kaynak)
├── models/                 # model adaptörleri ve profilleri
├── protocol/               # format çeviricileri, metin protokolü, MCP
├── engine/                 # derin çalışma motoru: döngü, roller, kapılar, hafıza
├── deploy/                 # yayına alma hedefleri
├── web/                    # web arayüzü (backend API + frontend)
├── installer/              # kurulum sihirbazı (Windows/macOS/Linux)
├── skills/                 # skill kütüphanesi
├── saas-kit/               # şablonlar ve modüller
├── bench/                  # yWorkspace Bench
├── android/                # uzaktan kumanda uygulaması
├── docs/                   # TR/EN belgeler
└── tests/
```

---

## 17. Yol haritası

Her aşama, kendi bitti kriteri sağlanmadan kapanmaz.

| # | Aşama | Bitti kriteri |
|---|---|---|
| 0 | **Temel:** depo yapısı, lisans, kod standartları, CI | CI yeşil, lisans dosyaları yerinde |
| 1 | **Dosya motoru:** tüm dosya araçları + akıllı düzenleme + geçmiş | Kapsamlı testler geçiyor, kenar durumlar dahil |
| 2 | **Sandbox:** Docker yönetimi, terminal ve süreç araçları | Konteynerde komut, arka plan sunucusu ve günlük okuma çalışıyor |
| 3 | **Model katmanı:** adaptörler (önce DeepSeek, Gemini, Ollama, sonra diğerleri) + geliştirici CLI | DeepSeek ve Gemini, CLI'dan dosya okuyup düzenleyip test çalıştırabiliyor 🎯 |
| 4 | **Derin Çalışma Motoru:** döngü, görev ağacı, roller, bitti kapıları, hafıza, kalite modları | Küçük bir web uygulaması, insan müdahalesi olmadan uçtan uca yapılabiliyor |
| 5 | **Doğrulama araçları:** test, tarayıcı (Playwright), HTTP, git, veritabanı | Model uygulamayı tarayıcıda açıp hatayı görüp düzeltebiliyor |
| 6 | **Web Arayüzü:** basit ve detaylı görünüm, TR/EN | Yazılım bilmeyen bir test kullanıcısı bir proje yaptırabiliyor |
| 7 | **Kurulum Sihirbazı:** Windows, macOS, Linux yükleyicileri | Temiz bir bilgisayarda sıfırdan kurulum başarılı (3 işletim sisteminde) |
| 8 | **Skill Kütüphanesi v1:** çekirdek + yazılım/SaaS skill'leri + dışa aktarma | Bench'te skill'li sonuçlar skill'sizden belirgin şekilde iyi |
| 9 | **SaaS Kiti + Yayına alma** | Giriş + ödeme + panel içeren SaaS yapılıp bir VPS'e ve bir platforma yayınlanabiliyor |
| 10 | **MCP sunucusu + metin protokolü + tarayıcı eklentisi** | Claude Desktop'tan ve bir web sohbetinden yWorkspace kullanılabiliyor |
| 11 | **Bench yayını + diğer skill kategorileri** | Sonuç tablosu yayında |
| 12 | **Android uzaktan kumanda** | Telefondan iş verilip onaylanabiliyor |
| 13 | **Ofis dosyaları (yOffice ile birleşme)** | docx, xlsx ve pptx okunup düzenlenebiliyor |

---

## 18. Açık sorular

1. **Test için API anahtarları:** Aşama 3'te DeepSeek ve Gemini için gerçek anahtarlar gerekecek.
2. **Logo ve tasarım:** yWorkspace ikonu, diğer y-uygulamalarının mavi tasarım diliyle mi olsun?
3. **Var olan uygulamalar:** 20 YunUSlu uygulamasının kodu geldiğinde yWorkspace ile ilişkisi (ör. yWorkspace'in ilk gerçek test projeleri olabilirler).
