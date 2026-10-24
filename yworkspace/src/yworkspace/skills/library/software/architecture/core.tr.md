Varsayılan olarak sıkıcı ve kanıtlanmış seçenekleri seç; karmaşıklık yerini hak etmeli.
- Küçük/orta SaaS: tek bir monolit + tek PostgreSQL veritabanı + arka plan iş kuyruğu. Mikroservis yok.
- Tam yığın TypeScript: Next.js (App Router) + Prisma ya da Drizzle + PostgreSQL.
- Python: FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL (önce API), ya da Django (yönetim ağırlıklı, CRUD).
- Mobil: Flutter (tek kod tabanı) ya da Kotlin + Jetpack Compose (sadece Android, yerel his).
- Geliştirme veritabanı, üretimle uyumlu kaldıkça SQLite olabilir; Docker'da PostgreSQL tercih edilir.
Yapıyı yalnızca katmana göre değil özelliğe göre kur (users/, bookings/, billing/). Ayarları ortam
değişkenlerinde tut, `.env.example` ekle ve tek komutla başlatma sağla (`docker compose up` ya da `npm run dev`).
Her kararı ve nedenini memory_note ile kaydet.
