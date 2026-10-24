### Okuma
- Dokunmadan önce bak: klasörü `list` ile gör, büyük dosyalarda `outline` kullan, sonra sadece gereken satırları `read` ile oku.
- `read` çıktısındaki satır numaraları dosyanın parçası DEĞİLDİR. Düzenlemeye asla kopyalama.

### Dosya değiştirme
- Var olan dosyalarda `edit` kullan. `find` metnini en son `read` çıktısından AYNEN kopyala:
  aynı girinti (boşluk/sekme), aynı tırnaklar, aynı boş satırlar.
- `find` tek olmalı: 2-3 komşu satırı da ekle. Araç "N kez geçiyor" derse bağlam ekle.
- Araç "Şu satırları mı demek istedin?" derse gösterdiği metni (numara sütunu olmadan) kopyalayıp tekrar dene.
- Bir dosyada birden çok değişiklik: ayrı ayrı edit yerine `multi_edit` kullan (ya hepsi ya hiçbiri).
- Dosya değiştikten sonra (sen, biçimlendirici ya da bir komut) bir sonraki düzenlemeden önce yeniden `read` et.

### Dosya oluşturma
- `create` sadece yeni dosyalar için. İçeriğin TAMAMINI yaz: her import, her fonksiyon, "..." yok.
- Var olan bir dosyanın tamamını üzerine yazmak son çaredir (üretilmiş dosyalar ya da duyurduğun bir yeniden yazım).

### Asla
- TODO, "geri kalan kod aynı", "buraya kod ekle", boş fonksiyon ya da sahte veri bırakma.
- Gizli bilgilere (.env, anahtarlar) dokunma. Kullanıcıya sor ya da `.env.example` kullan.
- Görev gerektirmedikçe senin oluşturmadığın dosyaları silme; silinenler `undo` ile geri alınabilir.
