# Issue tracker: GitHub

The tracker for this project is GitHub Issues in `Sussic/Pyfa-android`:
https://github.com/Sussic/Pyfa-android/issues

Use the `gh` CLI with explicit `--repo Sussic/Pyfa-android`.
For API calls, use the explicit `repos/Sussic/Pyfa-android/` path.
This local working copy intentionally has no remote; remote inference
is not a reliable way to select its tracker.

Before using the tracker, verify that Issues are enabled.
If disabled or inaccessible, report the blocker. Enabling Issues,
changing the tracker or adding a remote requires applicable user
authorization.

## Relationship to project documents

Follow the existing ownership in `../android/STATUS.md` and
`../android/ROADMAP.md`.

GitHub issues track requests and link to the relevant roadmap task,
accepted task brief and evidence. Preserve existing task IDs.

Acceptance remains in the existing task brief. Issues and generated
specs should link to it rather than maintain competing acceptance text.
A genuinely new spec may be drafted in an issue; reconcile its accepted
scope with the existing task documentation before implementation.

Issue readiness and labels do not authorize implementation or delivery.
Apply the session and project authorization rules in `../../AGENTS.md`.

## Duplicate check before ticket creation

Before creating any ticket, search both open and closed issues in
`Sussic/Pyfa-android` for its task ID and relevant behavior or domain terms:

```powershell
gh issue list --repo Sussic/Pyfa-android --state all --search "<task ID or relevant terms>" --limit 100 --json number,title,state,url
```

Use separate searches for the task ID and relevant terms where appropriate.
If results reach the limit, narrow the searches or retrieve further results
before concluding there is no duplicate. Read plausible matches, including
their comments and linked task documents. Reuse the existing issue when it
already covers the request. If a closed match needs renewed work, explain
the changed scope or evidence before proposing a follow-up or reopening it.
Create a new issue only after recording the duplicate-check result in its
body and confirming that no existing issue covers the same work.

## Conventions

- Read an issue:
  `gh issue view <number> --repo Sussic/Pyfa-android --json number,title,body,labels,comments`
- List issues:
  `gh issue list --repo Sussic/Pyfa-android --state open --json number,title,body,labels`
- When authorized to create an issue, complete the duplicate check first, then use:
  `gh issue create --repo Sussic/Pyfa-android --title "..." --body-file <path>`
- For multiline descriptions and comments, use a body file containing
  the exact text.
- Apply the mappings in `triage-labels.md` when a skill names a
  canonical triage role.
- Resolve ambiguous issue/PR numbers before taking action.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill instructions

When a skill says "publish to the issue tracker", create or update
the relevant GitHub issue within the user's authorized scope.
Complete the duplicate check before any new issue is created.

When a skill says "fetch the relevant ticket", read the issue and
its linked project task documents.

## Wayfinding operations

When wayfinding is explicitly invoked:

- Use a single map issue and linked child issues. Complete the duplicate
  check before creating either kind of issue.
- Link existing roadmap tasks instead of duplicating their work.
- Use native sub-issues and dependencies when available.
- Otherwise, use a map task list and child-body lines:
  `Part of #<map>` and `Blocked by: #<number>`.
- Select ready children only after checking actual dependencies and
  the authorization recorded by the current project control point.
- Claim by assigning the issue to the driving developer when authorized.
- Resolve by recording the answer and evidence, closing the child,
  and adding a concise decision pointer to the map.

Create missing wayfinding labels only when needed and authorized;
they are outside the initial triage-label setup.
