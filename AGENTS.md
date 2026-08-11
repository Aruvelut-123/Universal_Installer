# Repository Instructions

## Local-only files

- Treat `build.py`, `metadata.json`, and `pack/items.json` as local/private files.
- They may be edited and tested when the user requests it, but never stage their contents, commit their changes, force-add, or push them.
- Removing a previously tracked copy from the Git index is allowed only to establish this local-only policy; keep the working copy intact.
- Keep their ignore rules in `.gitignore`; committed documentation and examples must use `metadata_example.json` and `pack/items_example.json` instead.

## Commit messages

- Every commit must use a Conventional Commits subject that the repository's default `git cliff` invocation can categorize.
- Use an appropriate prefix such as `feat:`, `fix:`, `docs:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:`, or `revert:`; an optional scope is allowed.
- Keep the subject concise, imperative, and specific to the committed change.
