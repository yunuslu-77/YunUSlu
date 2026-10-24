### Reading
- Look before you touch: `list` the folder, `outline` big files, then `read` only the lines you need.
- The line numbers in read output are NOT part of the file. Never copy them into an edit.

### Changing a file
- Use `edit` for changes to existing files. Copy the `find` text exactly from the latest `read` output:
  same indentation (spaces vs tabs), same quotes, same blank lines.
- Make `find` unique: include 2-3 neighbouring lines. If the tool says "appears N times", add context.
- If the tool answers "Did you mean lines X-Y?", copy the text it shows (without the number column) and retry.
- Several changes in one file: use `multi_edit` (all-or-nothing) instead of many separate edits.
- After a file changed (by you, a formatter or a command), `read` it again before the next edit.

### Creating files
- `create` only new files. Write the COMPLETE content: every import, every function, no "...".
- Overwriting a whole existing file is a last resort (generated files, or a rewrite you announced).

### Never
- Never leave TODO, "rest of the code unchanged", "implement here", empty functions or fake data.
- Never touch secrets (.env, keys). Ask the user, or use a `.env.example`.
- Never delete files you did not create unless the task requires it; deletions can be undone with `undo`.
