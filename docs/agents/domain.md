# Domain docs

## Layout

Use a single context:

- `GLOSSARY.md` at the repository root for domain vocabulary.
- `docs/adr/NNNN-<decision>.md` for architecture decision records.

Create glossary entries and ADRs lazily when terms or decisions are
resolved during authorized work. Setup creates no placeholder glossary,
ADR, or multi-context map.

## Before exploring

Follow the session entry process in `../../AGENTS.md`.

Read `../../GLOSSARY.md` if present and relevant ADRs in `../adr/`.
If these optional domain documents do not exist, proceed silently.

For product behavior or engine-boundary work, consult the existing
`../android/SCOPE.md` and `../android/ARCHITECTURE.md`.

## Consumer rules

Use established glossary terms in issues, hypotheses, proposals and tests.

When a term is missing, check existing project usage before proposing
a new definition through domain modeling.

Surface conflicts with an ADR or the existing architecture explicitly;
resolve them through the project's decision process.

Keep existing architecture decisions in place. A later ADR should
link to the relevant source decision rather than duplicate it.

Task state, acceptance and verification evidence retain their existing
owners. Follow `../android/DEVELOPMENT.md` and
`../android/LOCAL-VERIFICATION.md` for evidence requirements.
