- Dockerfile: küçük resmi temel imaj, root olmayan kullanıcı, çok aşamalı derleme, sabitlenmiş sürümler,
  `.dockerignore`, HEALTHCHECK. Geliştirmede uygulama + veritabanı + önbellek için docker-compose.
- CI (GitHub Actions): her push/PR'da kur → lint → tip kontrolü → test → derleme; bağımlılıkları önbelleğe al.
- Ayarlar ortam değişkenlerinden; on iki faktör tarzı; yerelde tek komutla başlatma.
- Günlükler: istek kimlikli yapılandırılmış (JSON) günlükler; hatalar bir hata takip aracına (Sentry uyumlu, kendi sunucunda olabilir).
- Sağlık: `/health` (süreç ayakta) ve `/ready` (veritabanına ulaşılıyor).
- Yedekler: otomatik günlük veritabanı yedekleri, sunucunun dışında saklanır ve geri yükleme yöntemi TEST EDİLMİŞTİR.
- Kesintisiz yayın: trafiği değiştirmeden önce taşımaları çalıştır; geri dönmek için önceki sürümü tut.
