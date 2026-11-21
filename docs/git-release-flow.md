# Git branching, task integration and release management

One strategy for every workflow (DWS classic tasks, SDLC tasks, releases). All Git logic lives in
`backend/app/git_flow.py` (branching, locking, merges) and `backend/app/releases.py` (release state machine and
store); `sdlc_git.py`, `services.execute_task` and `main.py` call into them instead of re-implementing anything.

## Branches

| Branch | Role |
|---|---|
| `sandbox` | Permanent base. **Every** task branch is created from the latest `sandbox`. Only releases are merged into it. |
| `develop` | Integration branch. Receives a task branch only at final human approval. Nobody develops on it. |
| `<TASK-ID>` (`DWS-1001`, `SDLC-1500`) | One branch per task, named exactly like the task. Never deleted by Taskloom. |
| `release/<version>` | Built from `sandbox` out of selected tasks; merged into `sandbox` after validation and approval. Never deleted by Taskloom. |

Identifiers: SDLC tasks get `SDLC-1001, SDLC-1002, …` (`SDLCTaskManager.next_task_id`; the counter is persisted next
to the tasks and kept above every existing folder). DWS (classic) tasks use the identifier typed in the form
(case is preserved). `sandbox`, `develop`, `main`, `master` and `release/…` are refused as task identifiers.
Branches recorded by older versions (`sdlc/<id>`, `tasks/<id>`) keep working: their recorded name is reused.

## Task creation

`git_flow.create_task_branch(repo, task_id)` (used by DWS `execute_task`, SDLC `prepare_task_branch` and
`POST /api/branches/switch`):

1. takes the repository lock, 2. reuses the branch if it already exists (idempotent, no network),
3. otherwise **fetches** (two attempts; a failed fetch aborts instead of using stale refs),
4. resolves the newest `sandbox` (origin's, or a local one that is ahead; diverged ⇒ error),
5. creates the branch there. A missing `sandbox` raises `SandboxMissingError` — there is no fallback to
   `develop`, `main`, `HEAD` or the current branch.

Repositories Taskloom creates from scratch get `sandbox` automatically (and it is pushed with the new GitHub repo).
For an existing repository, create `sandbox` once yourself.

## Final approval → `develop`

Nothing is merged while a task waits for final approval. When the administrator approves
(`POST /api/sdlc/tasks/{id}/approve`, `POST /api/tasks/{run_id}/approve`):

1. the task's work is committed on its branch (never on a protected branch),
2. `git_flow.integrate_task` takes the repository lock, fetches, checks the branch exists and has no uncommitted work,
3. brings local `develop` up to date by fast-forward (a missing `develop` is created from `sandbox`, and logged),
4. merges the task branch with **`--no-ff`** in `develop`'s own worktree (or a temporary one) — a developer's working
   tree is never touched, and a dirty checkout of `develop` stops the merge,
5. a conflict aborts the merge, leaves `develop` unchanged and reports the files; a failed push rolls the local merge back,
6. only after Git confirmed a real merge commit is it recorded (`TaskRepo.integration` / `TaskState.git_integration`:
   status, merge commit, branch head, files, Git log, history of every merge) and the task becomes `done`.

A failed approval leaves the task in `pending_approval` (SDLC) / `passed` (DWS) and returns 409 with the reason.
Approving twice is idempotent (already-merged branches are recognised), simultaneous approvals are serialised by the lock.
The SDLC flow then pushes the task branch; it no longer opens a pull request into `sandbox` (the manual PR button now
targets `develop`).

## Releases

Dashboard → **مدیریت نسخه** (`frontend/src/release_management.jsx`).

```
draft → preparing → testing → waiting_approval ──(human approval)──▶ approved → merging → released
              └────────────── failed (retry / rebuild / cancel) ◀──────────────┘            cancelled
```

* **Eligible tasks**: every task whose branch was merged into `develop` and that still has changes not held by another
  (non-failed, non-cancelled) release. A task changed and approved again gets a new merge commit and becomes eligible
  again — only its new changes. History of earlier releases is kept.
* **Isolation**: each task entered `develop` through one merge commit. The release branch is created from the current
  `sandbox` in a separate worktree and each selected merge commit is cherry-picked with `-m 1`, which replays exactly
  what that task added to `develop`, nothing else that sits in `develop`. Afterwards the release is compared with
  `sandbox`: any file outside the selected merges aborts the release. Commits that are not Taskloom merge commits or are
  not in `develop` ⇒ the release stops ("cannot be isolated reliably").
* **Validation**: the project's own commands run in a clean worktree of the release commit: each stage's `setup_command`
  and `test_instructions.command` (SDLC) or the task's `test_command` (DWS), resolved again on every (re)build. With no
  command configured the release is flagged "nothing was tested" but can still be approved.
* **Approval**: only `waiting_approval` can be approved. The merge then checks the release branch is unchanged since
  validation and `sandbox` has not moved (otherwise it fails with a *rebuild* hint), merges with `--no-ff`, pushes
  `sandbox` (no force; rolled back on failure), re-reads Git, and only then records `released` + merge SHA.
  The release branch is pushed afterwards (failure is only a warning).
* **Recovery**: a failed preparation leaves no worktree, `sandbox` untouched and the (unpublished) release branch kept;
  `retry` rebuilds it. After a server restart, `preparing`/`testing` releases become `failed` (retry), and
  `approved`/`merging` ones are reconciled with Git (published merge ⇒ `released`, otherwise `failed` ⇒ retry returns to
  `waiting_approval`, never an automatic merge).
* Persistence: `data/releases/<release-id>.json` (atomic writes under a file lock; schema_version 1).

## Safety rules

Per-repository non-blocking lock in the common git dir (`taskloom-git.lock`; a second operation gets 409 "another Git
operation is running"); no force-push anywhere; no branch deletion; no commit on `sandbox`/`develop`/`main`/`master`/
`release/*`; Git output kept in the integration/release logs (tokens redacted); nothing is marked successful before Git
confirmed it.

Authorization: Taskloom has no accounts. Set `TASKLOOM_ADMIN_TOKEN` and every approval/release mutation must send
`X-Taskloom-Admin-Token` (the dashboard keeps it in the browser, "هویت مدیر"); `X-Taskloom-User` names the person for
`created_by` / `approved_by`. Reads stay open.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/sdlc/tasks/{id}/approve` (changed) | merge into `develop`, then `done`; 409 on conflict/failure |
| `POST /api/tasks/{run_id}/approve` (new) | same for DWS tasks (status `passed` → `done`) |
| `POST /api/branches/switch` (changed) | new branches are always created from `sandbox` |
| `GET /api/releases/repositories` | repositories with integrated tasks |
| `GET /api/releases/eligible-tasks?repository_id&q&workflow&status&eligible_only` | tasks + unreleased changes |
| `GET /api/releases/by-task/{task_id}` | versions a task participates in |
| `GET /api/releases?status&repository_id&q`, `GET /api/releases/{id}` | history / details |
| `POST /api/releases` `{version, repository_id, task_ids, start}` | create (422 bad input, 409 conflict) |
| `POST /api/releases/{id}/start | approve | retry | rebuild | cancel` | state transitions |

## Limitations

* Storage is JSON files (the project has no SQL database), so there are no SQL migrations: new fields are defaulted
  Pydantic fields and old task files load unchanged.
* Tasks that depend on each other must be released together (or in order): a cherry-pick that conflicts stops the release.
* Validation runs in a fresh worktree; projects whose tests need installed dependencies must define a `setup_command`.
* A release whose `sandbox` moved after validation must be rebuilt (by design: what was tested is what is merged).
* Final approval of a DWS task requires the work to be committed on its branch or checked out there (it is then committed).
* `sandbox` has to exist in existing repositories; Taskloom only creates it for repositories it initialises itself.
