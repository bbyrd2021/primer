# Contributing to Primer

Thank you for contributing to Primer! This guide walks you through everything you need to get started, from setup to getting your PR merged.

## Getting Started

### Prerequisites

- Python 3.11+
- git

### Setup

1. **Fork and clone the repo:**
   ```bash
   git clone https://github.com/<your-username>/Primer.git
   cd Primer
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dev dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Set up your environment:**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and add your `ANTHROPIC_API_KEY`.

5. **Verify your setup:**
   ```bash
   uvicorn main:app --reload
   ```
   Visit `http://localhost:8000` — you should see the Primer UI.

## Branching Strategy

```
main (production)
 ↑
 └── dev (integration)
      ↑
      ├── feature/pdf-highlights
      ├── fix/citation-format
      └── chore/update-deps
```

- **`main`** — Always deployable. Only receives merges from `dev`. Railway auto-deploys from this branch.
- **`dev`** — Integration branch. All feature work merges here first for testing.
- **Feature branches** — Short-lived, created from `dev`, merged back into `dev` via PR.

## Working on a Feature

### Step 1: Sync your local `dev`

```bash
git checkout dev
git pull origin dev
```

### Step 2: Create a feature branch

Use this naming convention:

| Prefix       | Use for                        | Example                     |
|--------------|--------------------------------|-----------------------------|
| `feature/`   | New functionality              | `feature/pdf-highlights`    |
| `fix/`       | Bug fixes                      | `fix/citation-format`       |
| `chore/`     | Maintenance, deps, config      | `chore/update-deps`         |

```bash
git checkout -b feature/your-feature-name
```

### Step 3: Make your changes

- Keep commits focused and atomic.
- Follow the [Code Standards](#code-standards) section below.
- Use imperative mood in commit messages, keep under 72 characters, and reference issue numbers:

```bash
git add <files>
git commit -m "Add PDF highlight support (#12)"
```

### Step 4: Keep your branch up to date

Regularly pull changes from `dev` to avoid large merge conflicts:

```bash
git checkout dev
git pull origin dev
git checkout feature/your-feature-name
git merge dev
```

Resolve any conflicts, test again, and commit the merge.

### Step 5: Push your branch

```bash
git push -u origin feature/your-feature-name
```

### Step 6: Open a Pull Request

- Open a PR from your feature branch → **`dev`** (not `main`).
- PR title: concise, descriptive (e.g., "Add PDF highlight annotations").
- PR description should include:
  - **What** changed and **why**
  - **How to test** the change
  - **Screenshots** if any UI changed
  - Related issue number (e.g., "Closes #12")
- CI checks (lint, type check, tests) will run automatically.

### Step 7: Code Review

- At least one teammate must approve before merge.
- Respond to review comments and push fixes to the same branch.
- Re-request review after addressing feedback.
- Keep discussions focused and constructive.

### Step 8: Merge

- Once approved and CI passes, use **squash merge** into `dev`.
- Delete the feature branch after merge (GitHub can do this automatically).

## Code Review Guidelines

When reviewing a PR, check for:

- **Correctness** — Does the code do what it claims?
- **Project conventions:**
  - Prompts live in `core/prompts.py` — never inline.
  - All `fetch()` calls go in `static/api.js` — never inline.
  - All styles in `static/primer.css` — no inline CSS.
  - `main.py` is routes only — business logic goes in `core/`.
- **Consistency** — Does it match the existing patterns in the codebase?
- **Security** — No exposed keys, no injection vectors.
- Run the code locally if the change is non-trivial.

## Releasing to Production

1. When `dev` is stable and tested, a maintainer opens a PR from `dev` → `main`.
2. The PR description summarizes all changes since the last release.
3. Use a **regular merge** (not squash) to preserve commit history.
4. After merge, Railway auto-deploys from `main`.

## Code Standards

Run all checks before pushing:

```bash
black . && ruff check . --fix && mypy core/ models/ && pytest tests/ -v
```

| Tool    | Command                  | Purpose           |
|---------|--------------------------|-------------------|
| black   | `black .`                | Format (88 cols)  |
| ruff    | `ruff check . --fix`     | Lint + auto-fix   |
| mypy    | `mypy core/ models/`     | Type check        |
| pytest  | `pytest tests/ -v`       | Run tests         |

### Project rules

- All prompts in `core/prompts.py` — never inline prompt text elsewhere.
- All fetch calls in `static/api.js` — never inline `fetch()` in other JS files.
- All styles in `static/primer.css` — no inline CSS.
- `main.py` is routes only — all business logic goes in `core/`.

## Working with Issues

- Check the **Issues** tab for open tasks before starting work.
- Assign yourself to an issue before starting.
- Reference issue numbers in branch names and commit messages.
- Use "Closes #N" in PR descriptions to auto-close issues on merge.

## Repository Settings (for admins)

Recommended branch protection rules:

**`main`:**
- Require pull request before merging
- Require at least 1 approval
- Require CI status checks to pass
- No force push
- No direct push

**`dev`:**
- Require pull request before merging
- Require CI status checks to pass
- No force push
