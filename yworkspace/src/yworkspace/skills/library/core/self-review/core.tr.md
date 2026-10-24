Farkı (diff) başkası yazmış ve ondan sen sorumluymuşsun gibi incele.

1. Doğruluk: değişen her fonksiyonu gerçekçi, boş ve kötü niyetli bir girdiyle takip et.
2. Hatalar: ağ, veritabanı ya da dosya erişilemezse ne olur? Hata kullanıcıya sade bir dille gösteriliyor ve
   geliştirici için kaydediliyor mu?
3. Güvenlik: kullanıcı girdisi SQL'e, kabuğa, HTML'e, dosya yollarına, yönlendirmelere ulaşıyor mu; her uç
   noktada yetkilendirme var mı (sadece kimlik doğrulama değil); gizli bilgiler asla kodda ya da günlüklerde yok.
4. Veri: taşımalar geri alınabilir mi? Kullanıcı verisini silebilecek ya da bozabilecek bir şey var mı?
5. Testler: özellik bozulursa başarısız olan bir test var mı? Kenar durumlar kapsanmış mı?
6. Artıklar: hata ayıklama çıktıları, yoruma alınmış kod, TODO'lar, kullanılmayan dosyalar.
Sadece önemli sorunları bildir; her biri için dosya:satır, sorun ve düzeltme.
