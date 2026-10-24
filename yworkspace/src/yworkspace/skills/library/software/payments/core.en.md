- ALWAYS develop and test in the provider's test/sandbox mode with test cards. Never use real money.
- Use the provider's hosted checkout / payment form (Stripe Checkout, iyzico checkout form, PayTR iframe):
  card data must never touch your server (PCI scope).
- The source of truth is the provider's WEBHOOK, not the browser redirect. Verify webhook signatures,
  make handlers idempotent (store processed event ids), and return 2xx quickly.
- Store: customer id, subscription id, plan, status, current_period_end. Gate features by status.
- Handle: trial, upgrade/downgrade (proration), cancel at period end, failed payment (dunning), refund.
- Prices and currency explicit (TRY/EUR/USD); amounts as integers in minor units.
- Turkey: iyzico/PayTR need merchant approval; e-invoice (e-Arşiv) is usually through an accounting
  integration - list it as a follow-up if out of scope.
- Tests: simulate webhook events (Stripe CLI `stripe trigger`, or signed test payloads).
