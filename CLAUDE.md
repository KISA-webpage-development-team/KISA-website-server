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
- Never push directly to `main`. Always work on a branch; the automation opens the PR (see "Opening the pull request").
- Never auto-merge. Codex review and the human owner decide.
- Write a clear PR description with: a short summary of the change, the reason, the files
  touched, and the checks you ran with their results.

### Risk level (required on every PR)
Every PR MUST declare a risk level. You declare it by including a line of the exact form
`Risk level: <level>` in the PR body (see "Opening the pull request" below). A workflow reads
that line and applies the matching label automatically, so you do not run `gh label` yourself.
The levels are:

- `simple` — small, low-risk, well-contained change (copy, isolated bug fix) with passing checks.
- `complex` — multi-file or non-trivial logic change. Review more deeply, add or update tests,
  and run all checks before recommending approval.
- `human-required` — touches a sensitive area (see below). Do not present it as safe to
  auto-approve; flag it for human review.

### Opening the pull request
Do NOT run `gh pr create` yourself. After you commit and push your branch, an automated
workflow step opens the PR for you. Hand off the PR title and body by writing two files:

- `/tmp/pr_title.txt` — a single line: the PR title.
- `/tmp/pr_body.md` — the PR description. It MUST contain a line of the exact form
  `Risk level: simple` (or `complex`, or `human-required`), plus a short summary, the reason,
  the files touched, and the checks you ran with results.

If you do not write these files the PR is still opened, but with a generic body and defaulted
to `human-required`.

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
