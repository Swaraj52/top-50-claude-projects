# Shared Resources

Utilities and tooling used across the repository.

## Policy

- A component is added here only when **at least two projects** need it.
- Each component documents its interface, its dependencies and which projects use it.
- Projects copy or vendor what they use, so each stays independently runnable. Nothing here
  is needed to run a project.

## Contents

| Path | Purpose | Dependencies | Used by |
|---|---|---|---|
| [`scripts/render_docs.py`](scripts/render_docs.py) | Regenerates the tracker, index, README project tables and placeholder project READMEs from `projects.json`. `--check` reports stale files | Python 3.9+ stdlib | Repository docs |
