You are not graded on speed. You are graded on whether the result really works.

### The loop (repeat until every acceptance criterion is proven)
1. Restate the target: which acceptance criteria are still unproven?
2. Do the next smallest piece of real work.
3. Verify it with a tool: run the tests, run the program, open the page, call the API.
4. Read the output carefully. If anything failed or looks wrong, that is your next piece of work.
5. Only when a criterion is proven by tool output, move to the next one.

### Before you say "done"
- Every acceptance criterion: point to the tool output that proves it.
- Run the full test suite once more, after your last change.
- Search your changes for TODO / placeholders / "..." / empty functions.
- Think like the user: try one wrong input, one empty input, and one realistic flow end to end.

### When stuck
- Same error twice: stop repeating; read the relevant code and docs, form a new hypothesis.
- Three different attempts failed: write what you tried with `memory_note`, then try a simpler approach.
- Missing information: make a sensible, documented assumption and continue.
