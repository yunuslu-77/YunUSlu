---
name: code-review-tr
description: Kaynak kodu hatalar, güvenlik açıkları, performans sorunları ve okunabilirlik açısından inceler. Kullanıcı kod ya da diff yapıştırıp "incele", "kontrol et", "hata bul", "iyileştir" dediğinde kullan.
---

# Kod İnceleme

## Amaç
Kullanıcıya ya da kodu bakımını yapan kişiye gerçekten zarar verecek sorunları bul, her birini kısaca açıkla ve nasıl düzeltileceğini göster. Gerçek sorunlardan oluşan kısa bir liste, uzun bir kılı kırk yarma listesinden iyidir.

## Adımlar
1. Kodun ne yapması gerektiğini anla. Belirsizse varsayımını açıkça yaz.
2. Ana akışları gerçekçi girdilerle takip et: boş, null, çok büyük ve bozuk girdiler dahil.
3. Şu sırayla kontrol et:
   - **Doğruluk:** Yanlış sonuç, çökme, sınır (off-by-one) hataları, yakalanmayan hatalar, yarış durumları.
   - **Güvenlik:** Enjeksiyon, doğrulanmayan girdi, koda gömülü şifre ve anahtarlar, parola veya token'ların güvensiz saklanması, eksik yetki kontrolü.
   - **Performans:** Döngü içinde gereksiz iş, tekrarlanan dosya/ağ işlemleri, bellek sızıntıları.
   - **Okunabilirlik:** Anlaşılmaz isimler, tekrarlanan kod, çok fazla iş yapan fonksiyonlar.
4. Yalnızca somut bir satır ve senaryo gösterebildiğin sorunları bildir.

## Çıktı biçimi
```
## Özet
<bir iki cümle: genel durum ve en önemli düzeltme>

## Bulgular
### 1. [Kritik|Yüksek|Orta|Düşük] <kısa başlık> — `dosya:satır`
**Sorun:** <neyin, hangi girdiyle bozulduğu>
**Düzeltme:**
<düzeltilmiş kod>
```
Sonunda sorunsuz görünen ama test edilmesi gereken yerleri belirt.

## Kurallar
- Kullanıcıya Türkçe cevap ver; kod ve teknik terimler orijinal kalabilir.
- Bulguları en ciddiden en hafife doğru sırala.
- Tüm dosyayı yeniden yazma; sadece değişen satırları göster.
- Kodda gerçek bir sorun yoksa bunu açıkça söyle.
