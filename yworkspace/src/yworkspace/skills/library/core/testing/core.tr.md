- Uygulamayı değil davranışı test et: girdi → çıktı, istek → yanıt, kullanıcı eylemi → ekran.
- Her özellik için: bir başarılı akış, ana hata yolları ve kenar durumlar (boş, en uzun, "çğıöşü" gibi
  unicode, tekrar eden kayıt, yetkisiz kullanıcı, gerektiğinde eşzamanlı istekler).
- Testler hızlı ve bağımsız olsun: ortak durum yok, gerçek ağ yok; geçici veritabanı kullan.
- Piramit: çok sayıda birim testi, bir miktar API/entegrasyon testi, birkaç uçtan uca yolculuk (Playwright).
- Özellik bozulduğunda test başarısız olmalı. Bunu bir kez kodu bilerek bozarak kontrol et.
- Python: pytest, fixture'lar, `tmp_path`. JS/TS: vitest ya da jest; tarayıcı yolculukları için Playwright.
- Testlere davranışın adını ver: `test_signup_rejects_duplicate_email`.
