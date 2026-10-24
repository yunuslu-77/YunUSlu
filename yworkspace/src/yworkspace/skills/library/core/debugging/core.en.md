1. Reproduce: run the failing test or command and capture the exact error. No reproduction, no fix.
2. Read the error bottom-up: the first line from YOUR code in the traceback is usually where to start.
3. Form one hypothesis at a time and test it cheaply (a print, a small script, a narrower test).
4. Find the root cause: ask "why?" until you reach the decision in the code that is wrong.
5. Fix the cause. Add or adjust a test that would have caught it.
6. Run the original failing check AND the whole suite.

Rules:
- Never weaken or delete a test to make it pass unless the test itself is wrong (then explain why).
- Never wrap code in a broad try/except to hide an error.
- If an external service fails (network, API limit), say so; do not fake the result.
