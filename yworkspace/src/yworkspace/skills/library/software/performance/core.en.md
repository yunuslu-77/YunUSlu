- Measure before changing: reproduce the slow case, time it, profile it (py-spy, cProfile, Chrome DevTools,
  EXPLAIN ANALYZE).
- Typical wins in order: missing database index, N+1 queries, unpaginated lists, synchronous work that belongs
  in a background job, missing HTTP caching, oversized images/bundles.
- Cache only with a clear invalidation rule; never cache per-user data in shared caches without the user key.
- Verify the improvement with the same measurement and keep a test or benchmark that guards it.
