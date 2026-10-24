---
name: code-review
description: Review source code for bugs, security issues, performance problems and readability. Use when the user pastes code or a diff and asks to "review", "check", "find bugs in" or "improve" it.
---

# Code Review

## Goal
Find the problems that would actually hurt users or maintainers, explain each one briefly, and show how to fix it. A short list of real issues beats a long list of nitpicks.

## Steps
1. Work out what the code is meant to do. If it is unclear, state your assumption.
2. Trace the main paths with realistic inputs, including empty, null, very large and malformed ones.
3. Check, in this order:
   - **Correctness:** wrong results, crashes, off-by-one errors, unhandled errors, race conditions.
   - **Security:** injection, unvalidated input, secrets in code, unsafe storage of passwords or tokens, missing permission checks.
   - **Performance:** needless work inside loops, repeated I/O, memory leaks.
   - **Readability:** unclear names, duplicated code, functions doing too much.
4. Only report an issue you can point to a concrete line and scenario for.

## Output format
```
## Summary
<one or two sentences: overall state and the most important fix>

## Findings
### 1. [Critical|High|Medium|Low] <short title> — `file:line`
**Problem:** <what goes wrong, with the input that triggers it>
**Fix:**
<corrected code>
```
End with anything that looked fine but deserves a test.

## Rules
- Order findings from most to least severe.
- Do not rewrite the whole file; show only the changed lines.
- If the code has no real problems, say so plainly.
