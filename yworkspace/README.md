# yWorkspace

**Her yapay zekâya tam bir geliştirme ortamı.** DeepSeek, Gemini, Claude, ChatGPT, Qwen, Mistral, Grok, Kimi ya da
bilgisayarındaki Ollama modeli fark etmez. yWorkspace her birine dosya okuma, oluşturma ve sadece gereken yeri
değiştirme araçları verir. Ayrıca güvenli bir çalışma ortamı, uzman skill'ler ve **bitti kapıları** sunar. Bitti
kapıları, yapay zekânın işi gerçekten bitirmeden "bitti" diyememesini yazılımla sağlar.

Tamamen **senin bilgisayarında** çalışır. Bulut yok, hesap yok. Bir YunUSlu projesidir.

> English below ↓

---

## Neler yapabilir

| Alan | Ne sağlar |
|---|---|
| **Dosya motoru** | Okuma, oluşturma, kesin düzenleme. Bulunamayan metin için "şunu mu demek istedin" önerisi, okunmadan yazmaya ve eskimiş okumaya karşı koruma, geri alma geçmişi |
| **Sandbox** | Komutlar Docker'da çalışır. İstenirse bu bilgisayarda da çalışabilir. Arka plan sunucuları, günlükler ve port yönlendirme desteklenir |
| **Her model** | Araç çağırabilen modeller (API) ve çağıramayanlar (metin protokolü) için ayrı yollar. Kopyala-yapıştır elle mod da var |
| **Derin Çalışma Motoru** | Roller: analist, mimar, geliştirici, testçi, inceleyici, hata ayıklayıcı. Ayrıca görev ağacı, hafıza, bütçe ve **bitti kapıları** (testler, kanıt, yarım kod taraması…) |
| **Bağlantı yolları** | API, MCP (Claude Desktop, Cursor, VS Code), tarayıcı eklentisi (web sohbetleri), Masaüstü Köprüsü (pano + Ctrl+V), elle mod |
| **Web arayüzü** | Basit ve detaylı görünüm, TR/EN, canlı ilerleme, onay kartları, önizleme |
| **Telefon** | QR ile eşleştirme. Telefondan iş verilir, ilerleme izlenir, onay verilir (`/m/`, ana ekrana eklenebilir) |
| **Kurulum sihirbazı** | Windows, macOS ve Linux. Docker, modeller, MCP, eklenti, medya ve ilk deneme adım adım kurulur. Yeniden başlatmadan sonra kalınan yerden devam eder |
| **Skill kütüphanesi** | 47 skill, TR + EN, modele özel notlar. Kategoriler: çekirdek, yazılım/SaaS, iş-pazarlama, belge-içerik, eğitim-araştırma, günlük yaşam. Claude, ChatGPT, Gemini ve DeepSeek biçimlerine dışa aktarılır |
| **Kendini geliştiren skill'ler** | Tekrarlanan hatalardan ders önerir. Ders Bench'te kanıtlanırsa uygulanır |
| **yWorkspace Bench** | Gizli testlerle, aynı model yWorkspace ile ve onsuz karşılaştırılır |
| **Akıllı yönlendirici ve paralel çalışma** | Her rol için uygun model seçilir, zorlanınca daha güçlü modele geçilir. Bağımsız işler git worktree'lerde paralel yürür |
| **SaaS Kiti ve yayına alma** | Test edilmiş FastAPI SaaS şablonu. Hedefler: VPS, Vercel, Netlify, Railway, Render, Fly, Cloudflare |
| **Güvenlik Laboratuvarı** | Gizli bilgi, kod, ayar ve bağımlılık taraması, dinamik test. Kritik bulgu varken yayına alma engellenir |
| **Bakım ve izleme** | İzleme, olay kaydı, düzeltme döngüsü, sunucu ajanı |
| **Derleme Fabrikası** | 52 tarif: APK/AAB, IPA, EXE/MSI, DMG, DEB/RPM/AppImage, ISO, Docker, paketler… Ayrıca doğrulama, imzalama ve mağazalar |
| **İnsan gibi kullanım** | Web (Playwright), Android (adb), iOS (Appium), masaüstü ve sanal makine ekranlarını kişilerle (persona) kullanma |
| **Medya Stüdyosu** | HTML/SVG çizim, grafik, diyagram, sahnelerden altyazılı ve müzikli video, seslendirme, kodla müzik, ikon setleri, 3B. Medya denetim kapısı da var |
| **Var olan projeyi devralma** | Keşif, harita, çalıştırma, karakterizasyon (golden master) testleri, sağlık raporu, belgeler, taşıma planı |
| **Lansman Kiti** | SEO'lu açılış sayfası, mağaza sayfaları, sosyal medya takvimi, e-postalar, fiyat analizi, yasal taslaklar (KVKK dahil), kontrol listesi |
| **Veri Laboratuvarı** | CSV/Excel/JSON/SQLite, temizleme, sorgu, grafik, gösterge paneli, defter, basit modeller. **Rapordaki her sayı hesaplanmış olmak zorunda** |
| **Otomasyonlar** | Zamanlanmış, olaya bağlı ve zincirleme görevler. Dış adımlar onay bekler. Kaçırılan görevler yakalanır |
| **Ofis dosyaları** | Word, Excel ve PowerPoint okuma ve oluşturma. Biçimi bozmadan düzenleme, formül hesaplatma, sayfa görüntüsü. yOffice'te açma |

## Kurulum

En kolay yol: kurulum programını (Windows `.exe`, macOS `.dmg`, Linux `.deb` / `.AppImage`) çalıştırıp sihirbazı izlemek.

Geliştiriciler için:

```bash
cd yworkspace
pip install -e ".[web,claude,data,office]"   # Python 3.10+
yw setup        # kurulum sihirbazı (Docker, model anahtarı, MCP, eklenti…)
yw doctor       # her şey hazır mı?
```

Windows'ta Docker'sız (yerel) modda komutlar Git for Windows'un bash'iyle çalışır, bu yüzden Git kurulu olmalıdır.
`yw doctor` (ve web arayüzündeki sağlık listesi) bunu kontrol eder. İsteğe bağlı ekler: `mcp`, `bridge` (masaüstü köprüsü), `dev` (testler). Medya için FFmpeg, ofis dönüştürme için
LibreOffice önerilir. Sihirbaz bunları kurar.

## Kullanım

```bash
yw web                       # web arayüzü (yalnızca bu bilgisayardan erişilir)
yw web --lan                 # telefondan da bağlan: terminalde çıkan QR'ı kamerayla okut
yw key DEEPSEEK_API_KEY sk-…  # anahtarı güvenle kaydet
yw do "Kuaförler için randevu sistemi yap" -p randevum --quality balanced
yw manual "README yaz" -p proje         # API'siz: herhangi bir sohbet botuyla kopyala-yapıştır
yw mcp-config                # Claude Desktop / Cursor ayarını yazdırır
yw bridge-web                # tarayıcı eklentisi için köprü (ChatGPT, Gemini, DeepSeek web sohbetleri)
yw bridge-desktop            # masaüstü sohbet uygulamaları için köprü
yw skills export ./skills-chatgpt --format chatgpt   # skill'leri başka yapay zekâlara aktar
yw automations daemon --project proje   # otomasyonları zamanında çalıştır
yw bench --models deepseek-chat,gemini-flash   # ölçüm (anahtarların kullanılır, ücretlidir)
```

Özerklik modları: `steps` (her adımda onay), `milestones` (önemli aşamalarda), `auto`.
Kalite modları: `economy`, `balanced`, `max`.

## Durum: neler test edildi, neler edilmedi

Bu bölüm dürüst bir özettir.

**Bu depoda otomatik testlerle doğrulananlar:** 141 test geçiyor (Linux). Dosya motoru, Docker sandbox,
metin protokolü, motor ve kapılar sahte modellerle test edildi. MCP sunucusu resmî MCP istemcisiyle denendi. Tarayıcı
eklentisi gerçek Chromium'da, web arayüzü ve telefon sayfası Playwright ile denendi. Ayrıca şunlar da çalıştırılarak
denendi: Go çapraz derleme ve `.deb`, Docker imajı, medya üretimi (FFmpeg), veri raporları, otomasyonlar, QR kodları
(OpenCV ile çözüldü), ofis dosyaları (LibreOffice ile).

**Donanım, hesap ya da anahtar gerektirdiği için denenemeyenler:**
- Gerçek model API'leri. Anahtar olmadığından yalnızca istek ve yanıt biçimleri sahte sunucularla denendi. Claude dışı
  model adları ve fiyatları zamanla değişebilir. Bütçe sınırı yalnızca fiyatı bilinen modellerde etkilidir.
- Android emülatörü ve cihazı, iOS/Appium, macOS ve Windows derlemeleri, QEMU sanal makineleri, masaüstü GUI kontrolü.
  Bunların kodu yazıldı, ancak sahte ortamlarla ya da hiç denenemedi.
- Yayına alma platformları (Vercel, Fly…), mağazalara yükleme, iyzico. Bunlar belgelerine göre yazıldı.
- Tarayıcı eklentisinin site seçicileri sitelerin tasarımı değiştikçe güncellenmeli.
- Telefon uygulaması bir PWA'dır. Yerel ağda (http) hizmet çalışanı ve tam kurulum kısıtlıdır. Tam kurulum için
  HTTPS gerekir (ör. Tailscale `tailscale serve`). Yerel bir Kotlin uygulaması henüz yok.

## Lisans

Kod: PolyForm Noncommercial 1.0.0. Skill'ler: CC BY-NC-SA 4.0. Bireylerin ticari kullanımı için ek izin vardır.
Ayrıntılar ve katkı kuralı (katkılar sahibine bildirilir) için depo kökündeki `LICENSE` ve `LICENSING.md`
dosyalarına bakın.

---

# yWorkspace (English)

**A complete development environment for any AI.** yWorkspace gives every model the same tools: reading, creating
and precisely editing files, a sandbox to run commands, expert skills and **done gates**. It works with DeepSeek,
Gemini, Claude, ChatGPT, Qwen, Mistral, Grok, Kimi, or a local Ollama model. The done gates are software checks: the
AI cannot claim it is done until the tests, evidence and checks really pass. Everything runs **locally on your
computer**, with no cloud and no account.

**Features:** a file engine with exact, safe edits and undo, and a Docker sandbox. Models connect through the API, MCP,
the browser extension, the desktop bridge or manual copy-paste. The Deep Work Engine runs roles and done gates. A
model router and parallel work pick the right model for each job. You also get:

- a web UI in Turkish and English, and phone pairing
- a setup wizard for Windows, macOS and Linux
- 47 bilingual skills that improve themselves, measured by yWorkspace Bench
- a SaaS kit with deploy targets, a Security Lab, monitoring, and a Build Factory with 52 recipes
- human-like app testing and a Media Studio
- adoption of existing projects, a Launch Kit and a Data Lab where every number must come from code
- automations and Office files (docx, xlsx, pptx) that open in yOffice

**Install:** run the installer, or `pip install -e ".[web,claude,data,office]"`, then `yw setup`.

**Use:** `yw web` opens the UI. `yw web --lan` lets your phone connect. `yw do "goal"` runs a whole project. `yw manual`
works with any chat bot. `yw mcp-config` sets up Claude Desktop or Cursor. `yw bench` measures models.

**Status:** 141 automated tests pass on Linux. Some parts could not be tested here because they need real
API keys, Android, iOS or macOS devices, Windows, virtual machines or hosting accounts. See the Turkish section above
for the exact list.

**License:** PolyForm Noncommercial 1.0.0 for code, CC BY-NC-SA 4.0 for skills, with an extra permission for
individuals' commercial use. See `LICENSE` and `LICENSING.md`.
