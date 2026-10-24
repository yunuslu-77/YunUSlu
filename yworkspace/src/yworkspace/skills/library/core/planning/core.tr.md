### İyi görev
- Küçük: bir insan için 15-60 dakika. Tek ve net bir sonuç.
- Doğrulanabilir: her görev, onu kanıtlayan testi ya da komutu (`verify`) ve kabul kriterlerini içerir.
- Dikey: "tüm modelleri yaz" yerine "kullanıcı kayıt olabilir (API + arayüz + test)"; böylece erkenden bir şey çalışır.
- Sıralı: ilk görev iskeleti VE çalışan bir test komutunu (`pytest`, `npm test`) kurar; sonraki her görev aynı yolla doğrulanır.

### Yöntem
1. SPEC'i oku. Kullanıcı yolculuklarını listele; her yolculuk bir ya da birkaç görev olur.
2. Teknolojiyi seç (kararı nedeniyle birlikte `memory_note` ile kaydet).
3. Görevleri sırayla `plan_add_tasks` ile yaz: başlık, açıklama, kabul kriterleri, verify, depends_on, branch.
4. Riskli görevleri `hard: true` işaretle (ödeme, kimlik doğrulama, veri taşıma, eşzamanlılık).
5. Son görevi ekle: "Her kullanıcı yolculuğunu gerçek bir kullanıcı gibi yap ve bozulanı düzelt."

### Kaçın
- "Cilala", "kodu iyileştir", "çeşitli" gibi doğrulanamayan görevlerden.
- Testleri sona bırakmaktan.
- İlk sürüm için ~25'ten fazla görevden; bunun yerine kapsamı daralt ve "Kapsam dışı"na yaz.
