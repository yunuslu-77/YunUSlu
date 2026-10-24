- Yayına alma her zaman kullanıcının açık onayını ister. Neyin oluşturulacağını/değişeceğini ve maliyetini göster.
- VPS: güvenlik duvarı (ufw: sadece 22, 80, 443) arkasında Docker Compose + Caddy (otomatik HTTPS), root olmayan
  yayın kullanıcısı, yalnızca SSH anahtarı, otomatik güvenlik güncellemeleri.
- Platformlar: Vercel/Netlify (ön yüzler, Next.js), Railway/Render/Fly.io (konteynerler + yönetilen Postgres).
- Gizli bilgiler platformun gizli bilgi deposuna ya da sunucuda 600 izinli bir `.env`'e gider - asla git'e değil.
- Veritabanı: yönetilen Postgres (Neon, Supabase) ya da sunucu dışı otomatik yedekli VPS'te Postgres.
- Yayından sonra: canlı adresi aç, ana yolculuğu yürü, günlükleri ve `/health`'i kontrol et.
- Geri dönüş planı tut: önceki imaj etiketi / önceki yayın ve geri alınabilir taşımalar.
