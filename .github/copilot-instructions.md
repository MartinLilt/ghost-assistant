# Copilot Instructions for `opp-server`

## Scope
- Keep changes small and focused on the user request.
- Do not rename/move files unless requested.
- Prefer editing existing files before introducing new abstractions.

## Python conventions in this repo
- Use Python 3.11+ features conservatively.
- Keep business logic importable from `src/opp_server/`.
- Expose runnable entry points through `python -m ...` style modules.
- Use standard-library tooling first (`venv`, `unittest`) unless asked otherwise.

## Quality checks before finishing
- Run tests with `python -m unittest discover -s tests -v`.
- If you add runnable code, ensure a simple local run command is documented in `README.md`.
- Keep docs and commands in sync with actual files in the repo.

