- Değiştirmeden önce ölç: yavaş durumu yeniden üret, süresini ölç, profilini çıkar (py-spy, cProfile, Chrome
  DevTools, EXPLAIN ANALYZE).
- Sırasıyla tipik kazançlar: eksik veritabanı indeksi, N+1 sorgular, sayfalanmamış listeler, arka plan işine ait
  senkron işler, eksik HTTP önbelleği, çok büyük görseller/paketler.
- Önbelleği yalnızca net bir geçersiz kılma kuralıyla kullan; kullanıcıya özel veriyi kullanıcı anahtarı olmadan ortak önbellekte tutma.
- İyileşmeyi aynı ölçümle doğrula ve onu koruyan bir test ya da benchmark tut.
