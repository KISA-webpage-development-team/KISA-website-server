# CLAUDE.md

Operational rules for Claude Code when working in this repository.

## Architecture Overview

KISA website backend: a Flask application (entry point `application.py`) using MySQL
(`Flask-MySQLdb`) and websockets (`Flask-SocketIO`), deployed to AWS Elastic Beanstalk
(`.ebextensions/`). SQL lives under `queries/`. Tests live alongside the code (e.g.
`test_internship_logic.py`).

## GitHub Automation (when triggered by `@claude`)

These rules apply when you are invoked from a GitHub issue or pull request (the `@claude`
trigger).

Being invoked via `@claude` is explicit authorization to commit to a working branch and open
a pull request. It is never authorization to push to `main` or to merge.

### Working style
- Create small, focused pull requests. One concern per PR.
- Never push directly to `main`. Always work on a branch and open a PR.
- Never auto-merge. Codex review and the human owner decide.
- Write a clear PR description with: a short summary of the change, the reason, the files
  touched, and the checks you ran with their results.

### Risk level (required on every PR)
Every PR you open MUST declare a risk level, both as a label and in the PR body:

- `simple` — small, low-risk, well-contained change (copy, isolated bug fix) with passing checks.
- `complex` — multi-file or non-trivial logic change. Review more deeply, add or update tests,
  and run all checks before recommending approval.
- `human-required` — touches a sensitive area (see below). Do not present it as safe to
  auto-approve; flag it for human review.

Apply the label with `gh pr edit <number> --add-label <risk>`. Create the label first with
`gh label create <risk>` if it does not exist.

### Always mark `human-required`
Mark the PR `human-required` if it touches any of:
- payments / Stripe / Pocha order state
- auth / JWT / admin permissions
- database migrations or schema changes (`queries/`, MySQL schema)
- secrets, credentials, or environment variables (including `secret_key.txt`)
- deployment config or GitHub Actions workflows (`.ebextensions/`, `.github/`)
- dependency upgrades (`requirements.txt`)
- anything security-sensitive

### Checks before opening or updating a PR
Run the available tests and report their output in the PR body:

```bash
python -m pytest            # if pytest is configured
python test_internship_logic.py   # otherwise run the existing test scripts directly
```

If no automated test covers the change, describe the manual verification you performed
(for example: which endpoint you exercised and the expected response). Do not leave the
app in a broken state.

## No Emojis in Markdown

Never use emojis in markdown documents, comments, or code.
