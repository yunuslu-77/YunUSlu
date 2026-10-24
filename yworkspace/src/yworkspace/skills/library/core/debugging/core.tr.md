1. Yeniden üret: başarısız testi ya da komutu çalıştır ve hatayı aynen al. Yeniden üretim yoksa düzeltme de yok.
2. Hatayı aşağıdan yukarı oku: hata izindeki SENİN kodundan gelen ilk satır genelde başlangıç noktasıdır.
3. Her seferinde tek bir hipotez kur ve ucuz yoldan test et (bir print, küçük bir betik, daha dar bir test).
4. Kök nedeni bul: koddaki yanlış karara ulaşana kadar "neden?" diye sor.
5. Nedeni düzelt. Bu hatayı yakalayacak bir test ekle ya da düzelt.
6. Önce başarısız olan kontrolü, sonra tüm test paketini çalıştır.

Kurallar:
- Test yanlış olmadıkça, geçsin diye bir testi asla zayıflatma ya da silme (yanlışsa nedenini açıkla).
- Hatayı gizlemek için kodu geniş bir try/except ile asla sarma.
- Dış bir hizmet başarısızsa (ağ, API sınırı) bunu söyle; sonucu taklit etme.
