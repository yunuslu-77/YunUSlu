- Yapı: `app/main.py` (create_app), `app/api/<özellik>.py` (router'lar), `app/models.py`, `app/schemas.py`,
  `app/db.py` (engine + oturum bağımlılığı), `app/settings.py` (pydantic-settings), `tests/`.
- Girdi/çıktı için Pydantic v2 şemaları; gizli alanlı ORM nesnelerini (parola özetleri) asla döndürme.
- SQLAlchemy 2.0 tarzı (`select()`, `Session.execute`), her şema değişikliği için Alembic taşıması.
- Veritabanı oturumu ve mevcut kullanıcı için bağımlılıklar; yetkiyi her uç noktanın içinde kontrol et.
- Parolalar: passlib/argon2-cffi ile `argon2` ya da `bcrypt`. Token'lar: kısa ömürlü JWT ya da sunucu oturumu.
- Hatalar: açık mesajlı `HTTPException`; beklenmeyen hatalar için kaydeden bir işleyici ekle.
- Testler: `TestClient` (ya da httpx AsyncClient), test başına geçici veritabanı, veri için fabrikalar.
- Çalıştırma: start_process ile `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
