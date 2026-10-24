- Test behaviour, not implementation: inputs → outputs, requests → responses, user actions → screen.
- For each feature: one happy path, the main error paths, and edge cases (empty, max length, unicode such as
  "çğıöşü", duplicates, unauthorized user, concurrent requests where relevant).
- Keep tests fast and independent: no shared state, no real network; use a temporary database.
- Pyramid: many unit tests, some API/integration tests, a few end-to-end user journeys (Playwright).
- A test must fail when the feature is broken. Check this once by breaking the code on purpose.
- Python: pytest, fixtures, `tmp_path`. JS/TS: vitest or jest; Playwright for browser journeys.
- Name tests after the behaviour: `test_signup_rejects_duplicate_email`.
