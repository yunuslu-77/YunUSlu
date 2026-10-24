- Resources as nouns (`/bookings/{id}`), standard methods, correct status codes (201 create, 204 delete,
  400 validation, 401 unauthenticated, 403 forbidden, 404, 409 conflict, 422, 429).
- One error shape everywhere: `{ "error": { "code": "email_taken", "message": "..." } }`.
- Pagination (`?limit=&cursor=`), filtering and sorting are explicit and bounded.
- Idempotency keys for payment-like POSTs; webhooks are signed and retried.
- Version from the start (`/v1`). Document with OpenAPI (FastAPI generates it; for Node use zod-to-openapi).
- Every endpoint: who may call it, what it validates, what it returns - and a test for each.
