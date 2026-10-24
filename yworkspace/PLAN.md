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
| Ortam eksik | Dosya, terminal, test, git, veritabanı, tarayıcı, yayına alma ve derleme (APK, EXE, IPA, ISO...) araçları olan, Docker içinde güvenli bir **tam geliştirme ortamı** |
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
| Lisans | **PolyForm Noncommercial 1.0.0** (kod) + **CC BY-NC-SA 4.0** (skill/belge) + bireylere ticari kullanım izni, bkz. bölüm 16 |

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
│  Bağlantı yolları: API │ MCP │ Tarayıcı eklentisi │ Masaüstü Köprüsü    │
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
5. **Bağlantı yolları (isteğe bağlı):** Kullanıcı Claude Desktop gibi MCP destekli uygulamalar kullanıyorsa MCP kaydını yapar. Tarayıcı eklentisini kurdurur. Masaüstü Köprüsü için gerekli işletim sistemi izinlerini (macOS Erişilebilirlik gibi) adım adım verdirir ve bir deneme mesajıyla test eder.
6. **Çalışma klasörü:** Projelerin duracağı klasörü seçtirir.
7. **Varsayılan ayarlar:** Özerklik modu, kalite modu, bütçe sınırı.
8. **Deneme projesi:** Küçük bir örnek projeyi uçtan uca yaptırır. Böylece kurulumun gerçekten çalıştığı kanıtlanır.
9. **Bitiş:** Masaüstü kısayolu, otomatik başlatma (isteğe bağlı), tarayıcıda arayüzü açar.

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
| `package` / `sign` | APK, EXE, IPA, ISO ve diğer çıktıları derleme ve imzalama (bkz. bölüm 11) |
| `emulate` | Derlenen çıktıyı emülatörde, Wine'da ya da sanal makinede deneme |

### 5.6 İnsan gibi kullanım araçları

| Araç | Görev |
|---|---|
| `screen_view` | Ekran görüntüsü + numaralı öğeler + metin haritası |
| `tap` / `click` / `double_click` / `long_press` | Dokunma ve tıklama (öğe numarasıyla ya da koordinatla) |
| `type` / `key` | İnsan hızında yazma, tuş ve kısayollar |
| `scroll` / `swipe` / `drag` | Kaydırma, kaydırma hareketi, sürükle-bırak |
| `wait_for` | Bir öğe görünene ya da yükleme bitene kadar bekleme |
| `device` | Döndürme, geri/ana ekran tuşu, ağ hızı, konum, dil, karanlık mod |
| `record` | Video ve adım kaydı |

Ayrıntılar: bölüm 12.
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

### 6.1 Dört bağlantı yolu

Hiçbir yapay zekâ dışarıda kalmaz. Her biri en az bir yolla bağlanır:

| Yol | Hangi yapay zekâlar | Nasıl |
|---|---|---|
| **1. API** (en güçlüsü) | API'si olan her model: DeepSeek, Gemini, Claude, OpenAI, Qwen, Mistral, Grok, Kimi, Ollama ile yerel modeller, OpenAI uyumlu her API | Araç tanımları modelin kendi formatına çevrilir, motor döngüyü yönetir. Araç çağıramayan modellerde metin protokolüne geçilir |
| **2. MCP** | MCP destekleyen uygulamalar: Claude Desktop, Cursor, VS Code, Windsurf, Gemini CLI, ChatGPT | yWorkspace araçları MCP üzerinden sunulur. ChatGPT yalnızca internetten erişilebilen sunuculara bağlandığı için sihirbaz bir tünel kurulumunda yardım eder |
| **3. Tarayıcı eklentisi** | Web sohbetleri: DeepSeek, Gemini, ChatGPT, Claude ve diğerlerinin web sürümleri | Eklenti sohbet sayfasına metin protokolüyle mesaj yazar, cevabı okur, yWorkspace uygular (bkz. 6.3) |
| **4. Masaüstü Köprüsü** | MCP desteği olmayan masaüstü uygulamaları (ör. DeepSeek ve Gemini uygulamaları) | Pano + Ctrl+V ile mesaj gönderir, cevabı kopyala butonundan alır (bkz. 6.4) |

Ek olarak her durumda çalışan **elle mod** vardır: Kullanıcı cevabı yWorkspace'e yapıştırır, yWorkspace sonucu panoya kopyalar.

> MCP desteği uygulamadan uygulamaya değişir ve zamanla güncellenir. Uygulama profilleri bu tabloya göre değil, güncel duruma göre tutulur.

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
- Metin protokolünü tarayıcı eklentisi, Masaüstü Köprüsü ve elle mod ortak kullanır. Derin Çalışma Motoru ve bitti kapıları bu yollarda da aynen geçerlidir.
- **Tarayıcı eklentisi:** Chrome, Edge ve Firefox için. Her sohbet sitesi için ayrı ve kolay güncellenebilir bir site profili tutulur (mesaj kutusu, gönder butonu, cevap alanı, cevabın bittiğini gösteren işaret).
- ⚠️ Bazı sitelerin ve uygulamaların kullanım koşulları otomasyonu yasaklayabilir. Eklenti ve Köprü, kullanıcının bilgilendirilip açıkça onay verdiği isteğe bağlı özelliklerdir.

### 6.4 Masaüstü Köprüsü

MCP desteği olmayan masaüstü sohbet uygulamalarını, insan gibi pano ve klavye kullanarak yWorkspace'e bağlar.

**Döngü:**

```
yWorkspace                              Masaüstü uygulaması
  1. Mesajı panoya kopyalar
  2. Uygulama penceresini öne getirir,
     doğru pencere olduğunu doğrular
  3. Ctrl+V (macOS: Cmd+V) + Enter  ──────▶  Mesaj gönderildi
                                              Yapay zekâ cevap yazıyor...
  4. Cevabın bittiğini algılar
  5. Cevabı alır  ◀─────────────────────────  yw:… blokları
  6. Uygular, testleri çalıştırır
  7. Sonucu panoya koyar → 2. adıma dön (iş bitene kadar)
```

**Cevabı alma yöntemleri (öncelik sırasıyla):**
1. **Kopyala butonu:** İşletim sisteminin erişilebilirlik altyapısıyla (Windows UI Automation, macOS Accessibility, Linux AT-SPI) son cevabın kopyala butonu bulunup basılır, cevap panodan okunur. Kod biçimi bozulmaz.
2. **Erişilebilirlik ağacından metin okuma:** Buton bulunamazsa pencere içeriği doğrudan okunur.
3. **Ekran görüntüsü + OCR:** Son çare. Kod için güvenilirliği düşük olduğundan kullanıcı uyarılır.

**Cevabın bittiğini algılama:** "Durdur" butonunun kaybolması, "gönder" butonunun yeniden etkinleşmesi ya da cevap metninin belirli bir süre değişmemesi.

**Uygulama profilleri:** Her uygulama için pencere adı, mesaj kutusu, kopyala butonu, bitti işareti ve mesaj uzunluğu sınırı bir profil dosyasında tutulur. Uygulama tasarımı değişince sadece profil güncellenir. Topluluk yeni profil ekleyebilir.

**Güvenlik ve kullanım kolaylığı:**
- **Pano koruması:** Kullanıcının panodaki eski içeriği saklanır ve iş bitince geri konur.
- **Pencere doğrulama:** Her yapıştırmadan önce önde doğru pencerenin olduğu kontrol edilir. Değilse yapıştırma yapılmaz.
- **Acil durdurma:** Tek tuş kombinasyonuyla (varsayılan Ctrl+Shift+Q) köprü anında durur. Fare ekranın köşesine götürülünce de durur.
- **Kullanıcı müdahalesi algılama:** Kullanıcı fare ya da klavyeyi kullanmaya başlarsa köprü duraklar, bekler ve devam etmeden önce sorar.
- **Ayrı masaüstü modu:** Bilgisayar meşgul olmasın diye uygulama ayrı bir sanal masaüstünde (Linux'ta sanal ekran, Windows ve macOS'ta ayrı masaüstü ya da sanal makine) çalıştırılabilir.
- **Uzun mesajlar:** Uygulamanın sınırını aşan mesajlar numaralı parçalara bölünür. Model tüm parçalar gelene kadar cevap vermemesi için yönlendirilir.

**İşletim sistemi notları:**
- **Windows:** Ek izin gerekmez.
- **macOS:** Kullanıcının "Erişilebilirlik" ve gerekirse "Ekran Kaydı" izni vermesi gerekir. Sihirbaz adım adım gösterir.
- **Linux:** X11'de doğrudan çalışır. Wayland otomasyonu kısıtlar. Desteklenen masaüstlerinde ilgili portal izinleri kullanılır, desteklenmiyorsa sihirbaz kullanıcıyı bilgilendirir.

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
- [ ] Tüm kullanıcı yolculukları **insan gibi** baştan sona yapıldı, ekran görüntüsü kanıtları var (bkz. bölüm 12)

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
| **Test kullanıcısı** | Uygulamayı farklı persona'larla gerçek bir insan gibi kullanır, hata ve kullanılabilirlik raporu yazar |

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

## 11. Derleme Fabrikası

Yapay zekâ sadece kod yazmakla kalmaz, projeyi **kurulabilir ve dağıtılabilir dosyalara** dönüştürür: APK, EXE, IPA, ISO ve daha fazlası. Her derleme ortamı hazır bir Docker imajıdır. Kullanıcı hiçbir SDK'yı elle kurmaz, gereken imaj ilk kullanımda otomatik indirilir.

### 11.1 Desteklenecek çıktılar

**📱 Mobil**

| Çıktı | Platform | Araçlar | Not |
|---|---|---|---|
| **APK** | Android (telefon, tablet, Android TV, Wear OS) | Gradle + Android SDK/NDK, Flutter, React Native, Capacitor | Docker'da tam destek |
| **AAB** | Google Play mağazası | Gradle, Flutter | Play yüklemesi için zorunlu biçim |
| **IPA** | iOS, iPadOS | Xcode, Flutter, React Native, Capacitor | ⚠️ **Mac gerektirir** (bkz. 11.3) |
| **HAP** | HarmonyOS (Huawei) | DevEco / hvigor | Linux'ta komut satırı araçlarıyla |

**🖥️ Windows**

| Çıktı | Açıklama | Araçlar |
|---|---|---|
| **EXE** (tek dosya) | Kurulumsuz çalışan program | PyInstaller, Nuitka, Go, Rust, .NET, Electron, Tauri, Flutter |
| **EXE kurulum sihirbazı** | "İleri, İleri" kurulumu | Inno Setup, NSIS |
| **MSI** | Kurumsal kurulum paketi | WiX Toolset |
| **MSIX** | Microsoft Store paketi | MSIX Packaging Tool, makeappx |
| **winget / Chocolatey / Scoop** | Paket yöneticisi bildirimleri | Bildirim dosyaları |

Windows çıktıları Linux Docker içinde çapraz derleme (MinGW, Wine) ile üretilebilir. Tam uyumluluk gereken durumlarda kullanıcının Windows bilgisayarı kullanılır.

**🍎 macOS**

| Çıktı | Açıklama | Not |
|---|---|---|
| **.app** | Mac uygulaması | ⚠️ Mac gerektirir |
| **DMG** | Sürükle-bırak kurulum görüntüsü | ⚠️ Mac gerektirir |
| **PKG** | Kurulum paketi | ⚠️ Mac gerektirir |
| **Homebrew** | `brew install` formülü | Her yerde yazılabilir |

**🐧 Linux**

| Çıktı | Açıklama |
|---|---|
| **AppImage** | Her dağıtımda çalışan tek dosya |
| **DEB** | Debian, Ubuntu, Pardus, Linux Mint |
| **RPM** | Fedora, RHEL, openSUSE |
| **Flatpak** | Flathub mağazası |
| **Snap** | Snap Store |
| **tar.gz** | Taşınabilir arşiv |
| **AUR (PKGBUILD)** | Arch Linux |

**💿 İşletim sistemi ve sanal makine imajları**

| Çıktı | Açıklama | Araçlar |
|---|---|---|
| **ISO** | Önyüklenebilir özel Linux dağıtımı (canlı + kurulum), ör. "YunUSlu OS" | live-build, archiso, debootstrap, mkosi |
| **IMG** | Raspberry Pi ve gömülü cihaz disk imajı | pi-gen, Buildroot, Yocto |
| **USB imajı** | Önyüklenebilir USB | Hibrit ISO |
| **QCOW2 / VMDK / VDI / VHD(X)** | QEMU/KVM, VMware, VirtualBox, Hyper-V sanal diskleri | Packer, qemu-img |
| **OVA** | Hazır sanal makine paketi | Packer |
| **Bulut imajı** | AWS AMI, Google Cloud, Azure | Packer |

Windows ISO'ları yalnızca Microsoft'un kendi araçları ve lisans koşulları çerçevesinde (ör. otomatik kurulum dosyası eklemek) özelleştirilir. Lisanssız Windows dağıtımı yapılmaz.

**🐳 Konteyner**

| Çıktı | Açıklama |
|---|---|
| **Docker / OCI imajı** | Çok mimarili (amd64 + arm64) imajlar, Docker Hub ve GHCR'ye yayın |
| **Docker Compose / Helm** | Çok servisli kurulum ve Kubernetes paketleri |

**🌐 Web**

| Çıktı | Açıklama |
|---|---|
| **Statik site** | HTML/CSS/JS paketi |
| **PWA** | Telefona kurulabilen web uygulaması |
| **WebAssembly** | Tarayıcıda çalışan C/C++/Rust/Go kodu |

**🧩 Eklentiler**

| Çıktı | Platform |
|---|---|
| **ZIP / CRX** | Chrome, Edge, Opera, Brave |
| **XPI** | Firefox |
| **Safari eklentisi** | ⚠️ Mac gerektirir |
| **VSIX** | VS Code |
| **JetBrains eklentisi (ZIP)** | IntelliJ, PyCharm, Android Studio |
| **WordPress eklentisi (ZIP)** | WordPress |

**📦 Kütüphane ve paketler**

| Çıktı | Ekosistem |
|---|---|
| **Wheel / sdist** | Python (PyPI) |
| **npm paketi** | JavaScript (npm) |
| **JAR / AAR** | Java, Kotlin, Android (Maven Central) |
| **NuGet** | .NET |
| **Crate** | Rust (crates.io) |
| **Go modülü / ikili dosyası** | Go |
| **Dart paketi** | Flutter (pub.dev) |

**🎮 Oyun**

| Çıktı | Araçlar | Not |
|---|---|---|
| Windows, Linux, Android, Web | Godot (komut satırından dışa aktarma) | Docker'da tam destek |
| Tüm platformlar | Unity | Kullanıcının Unity lisansı gerekir |
| macOS, iOS | Godot, Unity | ⚠️ Mac gerektirir |

**🔌 Gömülü sistemler ve IoT**

| Çıktı | Platform | Araçlar |
|---|---|---|
| **BIN / HEX / UF2** | Arduino, ESP32, ESP8266, STM32, Raspberry Pi Pico | PlatformIO, Arduino CLI, ESP-IDF |
| **Cihaza yükleme** | USB ile bağlı kart | esptool, avrdude (kullanıcı onayıyla) |

**📺 Akıllı TV ve saatler**

| Çıktı | Platform | Not |
|---|---|---|
| **APK** | Android TV, Google TV, Wear OS | Docker'da tam destek |
| **WGT** | Samsung Tizen | Tizen CLI |
| **IPK** | LG webOS | webOS CLI |
| Apple TV, Apple Watch | tvOS, watchOS | ⚠️ Mac gerektirir |

**📄 Belgeler** (ileride yOffice ile birlikte)

PDF, EPUB, DOCX ve kullanım kılavuzları (Pandoc, LaTeX).

### 11.2 Fabrikanın parçaları

- **Derleyici imajları:** Her araç zinciri için hazır, sürümü sabitlenmiş Docker imajı (`yw-builder-android`, `yw-builder-flutter`, `yw-builder-windows`, `yw-builder-linux-pkg`, `yw-builder-iso`, `yw-builder-embedded` ...). Önbellek sayesinde ikinci derleme çok daha hızlıdır.
- **Derleme tarifleri:** Her çıktı türü için yapay zekânın izleyeceği hazır tarif ve skill (ör. "Flutter → APK + AAB + IPA"). Tarif, proje türünü otomatik tanır.
- **Derleme matrisi:** Tek komutla birden çok çıktı. Örneğin bir Flutter uygulamasından APK, AAB, EXE, DEB ve PWA aynı anda üretilir.
- **İmzalama yöneticisi:** Android keystore, Windows kod imzalama sertifikası ve Apple sertifikaları güvenli depoda tutulur. Anahtarlar modele asla gösterilmez. Kaybedilirse uygulama güncellenemeyeceği için yedekleme konusunda uyarır.
- **Doğrulama (bitti kapısı):** Derlenen dosya gerçekten denenir:
  - APK → Android emülatöründe kurulur, açılır, ekran görüntüsü alınır (bilgisayarda donanım sanallaştırma gerekir).
  - EXE → Wine'da ya da Windows bilgisayarda çalıştırılır.
  - ISO / IMG → QEMU ile önyüklenir, açılış ekranının görüntüsü alınır.
  - DEB / RPM / AppImage → Temiz bir konteynerde kurulup çalıştırılır.
  - Docker imajı → Ayağa kaldırılır, sağlık kontrolü yapılır.
- **Sürüm ve dağıtım:** Sürüm numarası, değişiklik günlüğü, GitHub Releases. Mağaza yüklemeleri (Google Play, App Store, Microsoft Store, Flathub, Snap Store) her zaman **kullanıcı onayıyla** yapılır.

### 11.3 Mac gerektiren çıktılar

Apple'ın lisans koşulları gereği iOS, macOS, tvOS, watchOS ve Safari çıktıları **yalnızca Apple donanımında, Xcode ile** derlenebilir. yWorkspace bu konuda kullanıcıya üç yol sunar:

1. **Kullanıcının kendi Mac'i:** yWorkspace Mac'te kuruluysa doğrudan derler. Başka bir bilgisayardaysa, ağdaki Mac'i "derleme makinesi" olarak bağlar.
2. **Kullanıcının kendi CI hesabı:** GitHub Actions gibi macOS sunucusu sunan bir CI hizmeti kullanıcının kendi hesabıyla bağlanır.
3. **Kiralık Mac:** Kullanıcının kendi seçtiği kiralık Mac hizmeti.

Ayrıca App Store'a yükleme ve iPhone'a kurulum için **Apple Developer hesabı** (yıllık ücretli) gerekir. Sihirbaz bunu baştan açıkça söyler.

### 11.4 Lisans ve maliyet uyarıları

Bazı çıktılar ücretli hesap ya da sertifika gerektirir: Apple Developer, Google Play geliştirici hesabı, Windows kod imzalama sertifikası (imzasız EXE'ler SmartScreen uyarısı verir), Unity lisansı. yWorkspace bunları derlemeden önce listeler ve ücretsiz alternatif varsa önerir.

---

## 12. İnsan Gibi Kullanım

Yapay zekâ yaptığı uygulamayı sadece test kodlarıyla denemez, **gerçek bir insan gibi kullanır:** ekrana bakar, butonlara dokunur, kaydırır, form doldurur, hata mesajlarını okur ve "bir kullanıcı burada takılır mı?" diye düşünür. Bulduğu sorunları kendisi düzeltir.

### 12.1 Neleri kullanabilir?

| Platform | Nerede çalışır | Nasıl kontrol eder |
|---|---|---|
| **Web uygulaması** | Docker içindeki tarayıcı (Chromium, Firefox, WebKit) | Playwright: tıklama, yazma, kaydırma, sürükle-bırak, dosya yükleme |
| **Android** | Android emülatörü (telefon, tablet, TV, saat profilleri) | ADB + UI Automator / Appium: dokunma, kaydırma, uzun basma, geri tuşu, bildirimler, izin pencereleri |
| **iOS** | iOS Simülatörü | XCUITest / Appium. ⚠️ Mac gerektirir |
| **Windows uygulaması** | Windows sanal makinesi ya da kullanıcının Windows bilgisayarı (onayla) | Windows UI Automation |
| **Linux uygulaması** | Docker içinde sanal ekran (Xvfb) | AT-SPI + xdotool |
| **macOS uygulaması** | Mac | macOS Accessibility. ⚠️ Mac gerektirir |
| **Oyunlar** | Emülatör, sanal ekran ya da tarayıcı | Ekran görüntüsü + görsel anlama, klavye/fare/dokunma |
| **ISO / işletim sistemi** | QEMU sanal makinesi | VNC üzerinden ekran görüntüsü, klavye ve fare. Kurulum sihirbazını baştan sona geçer |
| **API / komut satırı programı** | Docker | Gerçek kullanıcının yazacağı komutlar ve istekler |

### 12.2 Ekranı nasıl "görür"?

Her adımda yapay zekâya iki bilgi birden verilir:
1. **Ekran görüntüsü:** Görsel anlayabilen modeller için (Claude, GPT, Gemini, Qwen-VL...). Tıklanabilir öğeler numaralanarak işaretlenir. Böylece model "7 numaralı butona bas" diyebilir, koordinat tahmin etmek zorunda kalmaz.
2. **Ekranın metin haritası:** Erişilebilirlik ağacından çıkarılan liste. Örneğin `[7] Buton "Kayıt Ol"` ya da `[8] Metin kutusu "E-posta" (boş)`.

**Görsel anlayamayan modeller (ör. DeepSeek'in metin modelleri) de kullanabilir.** Bunlar metin haritasıyla çalışır. İstenirse ekranı yorumlamak için yardımcı olarak ayrı bir görsel model (ör. yerel bir görsel model) atanır, sonuç metin olarak ana modele aktarılır.

### 12.3 Gerçek insan gibi davranış

- **Gerçekçi etkileşim:** İnsan hızında yazma, tıklamalar arası doğal bekleme, kaydırarak arama, klavye kısayolları. Bunlar zamanlama ve yükleme hatalarını ortaya çıkarır.
- **Persona'lar (kullanıcı tipleri):** Aynı uygulama farklı gözlerle kullanılır:
  - 🙂 **İlk kez kullanan:** Hiçbir şey bilmeden kayıt olur, yolunu bulmaya çalışır.
  - 👵 **Teknolojiye uzak kullanıcı:** Küçük yazılar, karışık menüler ve belirsiz mesajlarda zorlanır.
  - ⚡ **Sabırsız kullanıcı:** Butona iki kez basar, işlem bitmeden geri döner, sayfayı yeniler.
  - ♿ **Erişilebilirlik:** Ekran okuyucuyla gezer, sadece klavye kullanır, renk körlüğü filtresiyle bakar.
  - 😈 **Kötü niyetli test:** Formlara çok uzun metin, özel karakter ve saldırı denemeleri yazar (yalnızca kendi uygulamamızda).
  - 🌍 **Farklı dil ve cihaz:** Türkçe, İngilizce, Arapça (sağdan sola), küçük ekran, yatay ekran, yavaş internet, çevrimdışı.
- **Keşif testi:** Model kendisine verilen senaryonun dışına da çıkar ve uygulamayı merakla kurcalayarak beklenmedik hataları arar.

### 12.4 Kullanıcı yolculukları

SPEC.md'deki her önemli iş bir **kullanıcı yolculuğu** olarak yazılır. Örneğin "Kayıt ol → e-postayı doğrula → ücretli plana geç (test ödemesi) → ilk projeyi oluştur → çıkış yap". Yapay zekâ her yolculuğu insan gibi baştan sona yapar ve her adımın ekran görüntüsünü kanıt olarak kaydeder.

### 12.5 Çıktılar

- **Hata raporu:** Adım adım tekrar etme yolu, ekran görüntüsü ve video, konsol ve sistem günlükleri. Rapor doğrudan "Hata ayıklayıcı" rolüne gider, düzeltilir ve aynı yolculuk yeniden denenir.
- **Kullanılabilirlik raporu:** "Kayıt butonu ilk ekranda görünmüyor", "hata mesajı ne yapılacağını söylemiyor" gibi kullanıcı deneyimi bulguları.
- **Erişilebilirlik raporu:** Kontrast, ekran okuyucu etiketleri, dokunma alanı boyutu.
- **Otomatik teste dönüştürme:** Başarılı her yolculuk kalıcı bir otomatik teste çevrilir (Playwright, Maestro, Appium). Böylece ileride aynı hata geri gelirse hemen yakalanır.
- **Video kaydı:** Kullanıcı, yapay zekânın uygulamayı nasıl kullandığını sonradan izleyebilir. Web arayüzünde canlı da izlenebilir.

### 12.6 Güvenlik

- Tüm kullanım varsayılan olarak **izole ortamda** (Docker, emülatör, sanal makine) yapılır, kullanıcının gerçek masaüstünde yapılmaz. Gerçek bilgisayarda kullanım ayrı izin ister.
- **Ödemeler her zaman test modunda** yapılır (Stripe test kartları, iyzico sandbox). Gerçek para hareketi yasaktır.
- **Gerçek kişilere** e-posta, SMS ya da bildirim gönderilmez. Bunun yerine test posta kutusu (ör. Mailpit) kullanılır.
- **Gerçek hesaplara giriş yapılmaz.** Yalnızca test hesapları kullanılır.
- Kötü niyetli test persona'sı yalnızca kullanıcının kendi projesine uygulanır.

---

## 13. Web Arayüzü

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

## 14. Android uzaktan kumanda

Bulut olmadığı için Android uygulaması, **kullanıcının kendi bilgisayarındaki** yWorkspace'e bağlanır:
- Aynı Wi-Fi ağında: QR kod ile eşleşme.
- Dışarıdan: Kullanıcının kendi kuracağı güvenli tünel (ör. Tailscale). Sihirbaz bunun kurulumunda da yardım eder.

Telefondan iş verilebilir, ilerleme izlenebilir, onay kartları yanıtlanabilir ve önizleme görülebilir. YunUSlu uygulama ailesinin tasarım diliyle uyumlu olur.

---

## 15. Güvenlik

- **Docker sandbox:** Tüm komutlar konteynerde çalışır. Konteyner sadece proje klasörünü görür.
- **Çalışma alanı sınırı:** Dosya araçları proje klasörünün dışına çıkamaz (`../` ve sembolik bağlantılar engellenir).
- **Yasak dosyalar:** `.env`, özel anahtarlar ve şifre dosyaları varsayılan olarak modele gösterilmez. Gerekirse değerleri değil, sadece isimleri gösterilir.
- **Riskli işlem onayı:** Silme, yayına alma, veritabanı şeması değişikliği ve dışarıya istek her modda listelenir. Hangilerinin onay gerektireceği özerklik moduna göre belirlenir.
- **Komut enjeksiyonu koruması:** Dosya ve web içerikleri modele her zaman "veri" olarak işaretlenmiş verilir. İçlerindeki talimatlar uygulanmaz.
- **Otomasyon güvenliği:** Tarayıcı eklentisi ve Masaüstü Köprüsü yalnızca kullanıcı açıkça açtığında çalışır. Pano koruması, pencere doğrulama ve acil durdurma her zaman etkindir (bkz. 6.4).
- **Anahtar güvenliği:** API anahtarları işletim sisteminin güvenli deposunda tutulur, günlüklere ve modele yazılmaz.
- **Yerel ağ güvenliği:** Web arayüzü varsayılan olarak yalnızca bu bilgisayardan erişilebilir. Telefon eşleşmesi şifreli ve token'lıdır.

---

## 16. Lisans — ✅ Karar verildi

Ayrıntılar: [LICENSE](../LICENSE) ve [LICENSING.md](../LICENSING.md).

- **Kod:** PolyForm Noncommercial 1.0.0. Bireyler ve kâr amacı gütmeyen kurumlar serbestçe kullanır, şirketler kullanamaz.
- **Skill'ler ve belgeler:** CC BY-NC-SA 4.0.
- **Ek izin:** Bireyler yWorkspace'i kendi ticari işleri için de kullanabilir (ör. kendi SaaS'ını yapıp satmak). Yazılımın kendisini satmak ya da şirketlere sunmak hariç.
- **Üretilen işler:** yWorkspace ile yapılan projeler tamamen kullanıcının.
- **Katkılar:** Pull request ile gelir, her katkıdan haberdar olunur. Fork yapanlardan haber vermeleri rica edilir.
- **Ticari lisans:** Şirketler ayrı ücretli lisans alabilir.
- Bu yazılım resmi tanımıyla "açık kaynak" değil, **kaynağı açık** (source-available) yazılımdır.

---

## 17. Ölçüm: yWorkspace Bench

"Zayıf modellerden vay dedirttik" iddiasını kanıtlamak için ölçmemiz gerekiyor:

- **Görev seti:** Küçük (hata düzeltme) → orta (özellik ekleme) → büyük (sıfırdan SaaS: giriş + ödeme + panel) görevler.
- **Karşılaştırma:** Her model için **yWorkspace olmadan** (çıplak model) ve **yWorkspace ile** (her kalite modunda) sonuçlar.
- **Ölçütler:** Testlerin geçme oranı, bitti kapıları, süre, maliyet, insan müdahalesi sayısı.
- Sonuçlar herkese açık bir tabloda yayınlanır.

---

## 18. Depo yapısı

```
yworkspace/
├── PLAN.md                 # bu belge
├── core/                   # dosya motoru, akıllı düzenleme, geçmiş
├── sandbox/                # Docker yönetimi, süreçler
├── tools/                  # tüm araç tanımları (tek kaynak)
├── models/                 # model adaptörleri ve profilleri
├── protocol/               # format çeviricileri, metin protokolü, MCP
├── bridge/                 # Masaüstü Köprüsü + uygulama profilleri
├── extension/              # tarayıcı eklentisi + site profilleri
├── engine/                 # derin çalışma motoru: döngü, roller, kapılar, hafıza
├── deploy/                 # yayına alma hedefleri
├── factory/                # Derleme Fabrikası: derleyici imajları, tarifler, imzalama
├── operator/               # İnsan Gibi Kullanım: ekran, emülatör ve sanal makine kontrolü
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

## 19. Yol haritası

Her aşama, kendi bitti kriteri sağlanmadan kapanmaz.

| # | Aşama | Bitti kriteri |
|---|---|---|
| 0 | **Temel:** depo yapısı, lisans, kod standartları, CI | CI yeşil, lisans dosyaları yerinde |
| 1 | **Dosya motoru:** tüm dosya araçları + akıllı düzenleme + geçmiş | Kapsamlı testler geçiyor, kenar durumlar dahil |
| 2 | **Sandbox:** Docker yönetimi, terminal ve süreç araçları | Konteynerde komut, arka plan sunucusu ve günlük okuma çalışıyor |
| 3 | **Model katmanı + metin protokolü:** adaptörler (önce DeepSeek, Gemini, Ollama, sonra diğerleri), metin protokolü ayrıştırıcısı, elle mod, geliştirici CLI | DeepSeek ve Gemini hem API'den hem elle moddan dosya okuyup düzenleyip test çalıştırabiliyor 🎯 |
| 4 | **Derin Çalışma Motoru:** döngü, görev ağacı, roller, bitti kapıları, hafıza, kalite modları | Küçük bir web uygulaması, insan müdahalesi olmadan uçtan uca yapılabiliyor |
| 5 | **Tüm bağlantı yolları:** MCP sunucusu, tarayıcı eklentisi, Masaüstü Köprüsü | Claude Desktop'tan (MCP), bir web sohbetinden (eklenti) ve bir masaüstü uygulamasından (Köprü) aynı görev tamamlanabiliyor 🎯 |
| 6 | **Doğrulama araçları + İnsan Gibi Kullanım (web):** test, tarayıcıda insan gibi kullanım (Playwright), HTTP, git, veritabanı | Model web uygulamasını insan gibi kullanıp hatayı görüp düzeltebiliyor |
| 7 | **Web Arayüzü:** basit ve detaylı görünüm, TR/EN | Yazılım bilmeyen bir test kullanıcısı bir proje yaptırabiliyor |
| 8 | **Kurulum Sihirbazı:** Windows, macOS, Linux yükleyicileri | Temiz bir bilgisayarda sıfırdan kurulum başarılı (3 işletim sisteminde) |
| 9 | **Skill Kütüphanesi v1:** çekirdek + yazılım/SaaS skill'leri + dışa aktarma | Bench'te skill'li sonuçlar skill'sizden belirgin şekilde iyi |
| 10 | **SaaS Kiti + Yayına alma** | Giriş + ödeme + panel içeren SaaS yapılıp bir VPS'e ve bir platforma yayınlanabiliyor |
| 11 | **Derleme Fabrikası v1:** APK/AAB, EXE/MSI/kurulum sihirbazı, Linux paketleri, Docker imajları, web/PWA, imzalama yöneticisi | Aynı uygulamadan APK, EXE ve DEB üretilip emülatörde, Wine'da ve temiz konteynerde açıldığı kanıtlanıyor |
| 12 | **Derleme Fabrikası v2:** IPA ve macOS (Mac derleme makinesi), ISO/IMG/sanal makine imajları, eklentiler, kütüphane paketleri, oyun, gömülü sistemler, TV/saat, mağaza yüklemeleri | Bir özel Linux ISO'su QEMU'da açılıyor, bir IPA Mac üzerinden derleniyor |
| 13 | **İnsan Gibi Kullanım:** web, Android, Linux ve Windows uygulamaları, ISO kurulumları, iOS ve macOS (Mac ile); persona'lar, kullanıcı yolculukları, raporlar, otomatik teste dönüştürme | Yapay zekâ bir SaaS'a kayıt olup test ödemesi yapıyor, bir APK'yı emülatörde baştan sona kullanıyor ve bulduğu hatayı kendisi düzeltiyor |
| 14 | **Bench yayını + diğer skill kategorileri** | Sonuç tablosu yayında |
| 15 | **Android uzaktan kumanda** | Telefondan iş verilip onaylanabiliyor |
| 16 | **Ofis dosyaları (yOffice ile birleşme)** | docx, xlsx ve pptx okunup düzenlenebiliyor |

---

## 20. Açık sorular

1. **Test için API anahtarları:** Aşama 3'te DeepSeek ve Gemini için gerçek anahtarlar gerekecek.
2. **Logo ve tasarım:** yWorkspace ikonu, diğer y-uygulamalarının mavi tasarım diliyle mi olsun?
3. **Var olan uygulamalar:** 20 YunUSlu uygulamasının kodu geldiğinde yWorkspace ile ilişkisi (ör. yWorkspace'in ilk gerçek test projeleri olabilirler).
