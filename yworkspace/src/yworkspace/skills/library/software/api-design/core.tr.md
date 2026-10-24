- Kaynaklar isimdir (`/bookings/{id}`), standart metotlar, doğru durum kodları (201 oluşturma, 204 silme,
  400 doğrulama, 401 kimliksiz, 403 yasak, 404, 409 çakışma, 422, 429).
- Her yerde tek hata biçimi: `{ "error": { "code": "email_taken", "message": "..." } }`.
- Sayfalama (`?limit=&cursor=`), filtreleme ve sıralama açık ve sınırlı.
- Ödeme benzeri POST'lar için idempotency anahtarı; webhook'lar imzalı ve yeniden denenir.
- Baştan sürümle (`/v1`). OpenAPI ile belgele (FastAPI üretir; Node için zod-to-openapi).
- Her uç nokta: kim çağırabilir, neyi doğrular, ne döndürür - ve her biri için bir test.
