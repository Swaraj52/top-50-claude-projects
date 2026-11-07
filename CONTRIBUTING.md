# Contributing

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/), with the project number as the scope:

```text
feat(project-01): implement dashboard
fix(project-01): handle empty calendar feed
test(project-01): add task API tests
docs(project-01): complete README
chore(repo): update tracker
release(project-01): mark project complete
```

Use the `repo` scope for root-level changes (tracker, recovery files, tooling).

## Branches and tags

- `main` always holds working code. Work on one project at a time. A short-lived
  `project-NN` branch is fine for larger changes.
- Each verified project is tagged `project-NN-v1.0`. Later fixes bump the minor version.
- Never force-push, and never rewrite published history.

## Secrets and personal data

Never commit:

- `.env` files, API keys, tokens, passwords or OAuth client secrets
- Real databases (`*.db`, `*.sqlite`) or exports with personal data
- Logs that may contain request bodies or credentials
- Large model weights or datasets (document how to download them instead)

Before every push, run a secrets scan over the staged changes. At minimum:

```bash
git diff --cached | grep -nEi "(api[_-]?key|secret|token|password|sk-[a-z0-9]{10,})"
```

Every match must be a variable name, a placeholder or test data, never a real value.

## Adding or changing a project

1. Get explicit authorization for that project (see [MASTER_README.md](MASTER_README.md)).
2. Keep all changes inside its `PROJECT_NN/` folder, plus tracker and recovery updates.
3. Update `projects.json` and run `python shared-resources/scripts/render_docs.py`.
4. Make sure the project's tests pass before committing a `release` commit.
