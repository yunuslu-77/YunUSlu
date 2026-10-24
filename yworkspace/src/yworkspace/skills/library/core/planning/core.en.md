### Good tasks
- Small: 15-60 minutes for a human. One clear outcome.
- Verifiable: each task names the test or command that proves it (`verify`) and lists acceptance criteria.
- Vertical: prefer "user can sign up (API + UI + test)" over "write all models", so something works early.
- Ordered: the first task creates the skeleton AND a working test command (`pytest`, `npm test`), so every
  later task can be verified the same way.

### Procedure
1. Read the spec. List the user journeys; each journey becomes one or more tasks.
2. Pick the stack (record the decision with `memory_note`, including why).
3. Write tasks in order with `plan_add_tasks`: title, description, acceptance, verify, depends_on, branch.
4. Mark risky tasks `hard: true` (payments, auth, data migrations, concurrency).
5. Add a final task: "Walk through every user journey like a real user and fix what breaks."

### Avoid
- Tasks like "polish", "improve code", "misc" - they cannot be verified.
- Postponing tests to the end.
- More than ~25 tasks for a first version; cut scope instead and list it under "Out of scope".
