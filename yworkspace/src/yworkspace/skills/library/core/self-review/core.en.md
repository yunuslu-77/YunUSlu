Review the diff as if someone else wrote it and you will be on call for it.

1. Correctness: trace each changed function with a realistic input, an empty input and a hostile input.
2. Errors: what happens when the network, the database or a file is unavailable? Is the error shown to the
   user in plain words and logged for the developer?
3. Security: user input reaching SQL, shell, HTML, file paths, redirects; authorization on every endpoint
   (not only authentication); secrets never in code or logs.
4. Data: migrations reversible? Anything that could delete or corrupt user data?
5. Tests: does a test fail if the feature breaks? Are edge cases covered?
6. Leftovers: debug prints, commented-out code, TODOs, unused files.
Report only issues that matter, each with file:line, the problem, and the fix.
