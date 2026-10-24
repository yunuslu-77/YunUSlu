- Geliştirmeyi ve testi HER ZAMAN sağlayıcının test/sandbox modunda, test kartlarıyla yap. Asla gerçek para kullanma.
- Sağlayıcının barındırılan ödeme sayfasını/formunu kullan (Stripe Checkout, iyzico ödeme formu, PayTR iframe):
  kart verisi asla senin sunucuna değmemeli (PCI kapsamı).
- Doğruluğun kaynağı tarayıcı yönlendirmesi değil sağlayıcının WEBHOOK'udur. Webhook imzalarını doğrula,
  işleyicileri idempotent yap (işlenmiş olay kimliklerini sakla) ve hızlıca 2xx dön.
- Sakla: müşteri kimliği, abonelik kimliği, plan, durum, current_period_end. Özellikleri duruma göre aç.
- Ele al: deneme süresi, yükseltme/düşürme (orantılama), dönem sonunda iptal, başarısız ödeme (tahsilat takibi), iade.
- Fiyatlar ve para birimi açık (TRY/EUR/USD); tutarlar alt birimde tam sayı.
- Türkiye: iyzico/PayTR üye işyeri onayı ister; e-Arşiv fatura genelde bir muhasebe entegrasyonuyla yapılır -
  kapsam dışıysa sonraki iş olarak listele.
- Testler: webhook olaylarını simüle et (Stripe CLI `stripe trigger` ya da imzalı test yükleri).
