# Design system and SDLC automation

## Design system: Radix Themes

**Why.** Surveys of 2026 React UI options rank shadcn/ui first for new apps and Ant Design for data-heavy admin tools
([UXPin](https://www.uxpin.com/studio/blog/top-react-component-libraries/),
[Builder.io](https://www.builder.io/blog/react-component-libraries-2026),
[AdminLTE comparison](https://adminlte.io/blog/shadcn-ui-vs-mui-vs-ant-design/)). Most of the accessible ones are built on
Radix primitives. None of those sources confirms RTL behaviour, which Taskloom needs (Persian UI), so the choice was made on
fit instead: shadcn/ui requires Tailwind and a rewrite of every component's markup; Ant Design is large and has its own
visual language. **Radix Themes** gives the same accessible Radix primitives plus a token-based design system, light/dark
appearance and RTL direction support, with no Tailwind and no markup rewrite.

**How it is applied.**

* `main.jsx` wraps the app in `<Theme accentColor="green" grayColor="sage" appearance={theme}>` and a Radix
  `DirectionProvider dir="rtl"`; the existing theme toggle drives `appearance`. Vazirmatn is bundled (`@fontsource`), so the UI no
  longer needs Google Fonts.
* `frontend/scripts/tokenize_css.py` is the migration tool that was run on `styles.css`: it removed the 525 hand-written
  `html[data-theme="dark"]` selectors and replaced all ~1,300 hard-coded colours with Radix scale tokens (`--gray-6`,
  `--accent-9`, …) chosen by hue, lightness and use (background / text / border). Every existing page, form and table therefore
  follows the theme in both modes; the code viewer keeps its fixed editor palette. Re-run it on a fresh copy if you import old CSS.
* `design.css` holds the thin layer on top (fonts, overlays, new components).
* `ui.jsx`: `ModalShell` (Radix Dialog) replaced the five hand-made overlays: focus trap and restore, Esc, outside click,
  scroll lock, ARIA labels. `confirmDialog()` / `promptDialog()` replace every `window.confirm/prompt`.

## Project builder: "I want project X"

SDLC → پروژه‌ها → **ساخت خودکار پروژه** (`POST /api/sdlc/project-builder`). The user describes the project in a few
sentences (10–4000 characters; optional name, stack and parent folder) and picks how automatic it should be. Taskloom then:

1. **Decides the stages** from the idea (analysis + backend/frontend/n8n as needed + qa) and the stack (Python, Node.js or a
   static site); both can be overridden. The project id is derived from the name, or from the idea, and never collides: a
   derived id gets `-2`, `-3` … while an id the user typed that already exists is refused (409).
2. **Creates the folders** under `<parent>/<id>/` (default parent `~/taskloom-projects`): one folder per stage, each its own Git
   repository, plus `knowledge/` (PROJECT, ARCHITECTURE, CONVENTIONS, DEFINITION_OF_DONE) that every stage is told to read.
   A non-empty destination is refused and left untouched; a failed build removes what it created.
3. **Writes each stage's system prompt** (role, project goal, stack, rules, how to report) into the project configuration and
   into the stage's `CLAUDE.md`, plus a README, `.gitignore` and a starter skeleton whose own test command passes
   (`python -m pytest -q`, `node --test`). Analysis gets `docs/requirements.md` and open questions, QA gets `test-plan.md`.
4. **Makes the repositories task-ready**: initial commit on `main` and the `sandbox` branch that task branches start from.
   Nothing is sent to GitHub; each stage's private repository is created on its first push as for any from-scratch stage.
5. **Saves the project** with the chosen autonomy preset. Human gates stay on in every preset: *manual* (all decisions human),
   *balanced* (low-risk tasks approved automatically, one automatic retry), *autopilot* (clean analyses and low-risk tasks
   approved automatically, release drafts built automatically; merging into `sandbox` is still always a human decision).

With "AI enrichment" on, Claude Code (non-interactive, in an empty temporary folder) or a local Ollama model also writes the
description, initial requirements, open questions, architecture and project-specific guidance per stage; its answer is
validated and size-limited before use. If no AI answers, the templates alone already make a complete project.
**Preview** shows the plan (folders, files, prompts) without writing anything or calling the AI.

## SDLC automation: more autonomy, with a human where it matters

Survey of agentic-SDLC platforms (GitLab Duo Agent Platform, Devin, Copilot coding agent, Factory and others) shows the same
themes: governance and audit trails, human approval for risky changes while routine work is supervised rather than approved
step by step, and automatic quality gates
([GitLab](https://about.gitlab.com/gitlab-duo/workflow), [vmblog overview](https://vmblog.com/bylines/the-7-best-agentic-sdlc-tools-for-engineering-teams-in-2026/)).
Taskloom already ran the stages, revision loop and analyst consults automatically. Added in `backend/app/sdlc_policy.py`
(pure functions, all defaults keep the old behaviour: a human decides):

| Policy (project workflow) | What Taskloom does by itself | When a human is pulled back in |
|---|---|---|
| `auto_analysis_approval` | Starts development when the analysis completed with no open issues and no open stage questions | Any issue/question: the gate asks, and says why automation declined |
| `auto_final_approval` + `auto_approval_max_risk` | Approves and merges into `develop` a finished task whose **risk** is within the ceiling | Medium/high risk, failing tests, a pending intervention, a merge conflict or any Git error |
| `auto_retry_failed_stages` | Re-runs a failed stage up to N times (with back-off) | Budget used up: the task fails and is escalated |
| `auto_release` + `auto_release_min_tasks` | Drafts, builds and validates a release when enough tasks sit unreleased in `develop` (one open release per repository) | **Always**: merging a release into `sandbox` still needs the administrator's approval |

With the project's *human final approval* switched off, Taskloom approves every task whose tests did not fail.

**Human opinion back to the analyst** (task dialog, section `M3-A` Status): a human who sees a problem clicks
"مشکل دارد؛ ارجاع به تحلیل", writes what is wrong and sends it. `POST /api/sdlc/tasks/{id}/send-back` `{feedback}` records
it as a revision request from `human` to `analysis` (it appears in the timeline), closes any open question for that task in the
inbox, and runs the analyst again with the text as binding input in its prompt. The new analysis always goes to a human for
approval, even when `auto_analysis_approval` is on. Allowed unless a stage is running or the task is already merged into
`develop` (409); the opinion is 1–4000 characters. It does not count against the automatic revision limit.

**Risk assessment** (`assess_risk`): size of the change, deletions, sensitive paths (auth/secrets, migrations, CI/deploy,
dependency manifests, payments), failing or missing tests, revision rounds, automatic retries and open issues. Result
`low / medium / high` with the reasons, stored on the task and shown in its details. Failing tests are *blocking*.

**Audit trail**: every task has a `timeline` (created, stage started/completed/failed with durations, automatic retries,
escalations, human responses, approvals, merges) shown in the task details. **Metrics**: `GET /api/sdlc/metrics?project=`
returns throughput, success rate, average cycle time, first-pass rate, automation rate, retries/escalations, stage timings and
risk mix; the SDLC page has an "آمار و خودکارسازی" tab.

Dashboard: the project wizard's *Workflow* step has the "خودکارسازی و نقش انسان" section; the review step summarises it.
