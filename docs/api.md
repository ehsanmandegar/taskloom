# API

مستندات تعاملی هنگام اجرای سرور: `http://localhost:8003/docs`

> **به‌روزرسانی مرحلهٔ ۱:** `main.py` به نسخهٔ HEAD بازگردانده شد، پس ستون «HEAD» اکنون وضعیت فعلی است؛
> ستون «main.py فعلی» نسخهٔ mock قبلی را نشان می‌دهد که کنار گذاشته شد. `POST /api/sdlc/tasks/{id}/approve` هم اضافه شد.
> endpointهای `github/*` در مرحلهٔ ۵ اضافه شدند؛ بدنه: `{agent, repo_url, github_token}` (فیلدهای خالی از `github_config` آن agent یا `GITHUB_TOKEN` پر می‌شوند).

✅ واقعی · 🟡 mock / ساختگی · ❌ وجود ندارد

## SDLC

| Endpoint | فراخوانی از UI | main.py فعلی | HEAD |
|---|---|---|---|
| `GET /api/sdlc` | — | 🟡 اطلاعات ثابت | — |
| `GET /api/sdlc/projects` | ✅ | ✅ | ✅ |
| `GET /api/sdlc/projects/{id}` | ✅ | ✅ | ✅ |
| `POST /api/sdlc/projects` | ✅ | ❌ متد `create_project` وجود ندارد → 500 | ✅ |
| `PUT /api/sdlc/projects/{id}` | ✅ | ❌ | ✅ |
| `DELETE /api/sdlc/projects/{id}` | ✅ | ❌ | ✅ |
| `GET /api/sdlc/tasks?status=&project=` | ✅ | ✅ | ✅ |
| `GET /api/sdlc/tasks/{id}` | ✅ | ✅ | ✅ |
| `POST /api/sdlc/tasks` | ✅ | ❌ آرگومان `base_task_state` پاس داده نمی‌شود → 500 | ✅ |
| `POST /api/sdlc/tasks/{id}/transition` | ✅ | ❌ متد `transition_task` وجود ندارد → 500 | ✅ |
| `POST /api/sdlc/human-intervention/{id}/respond` | ✅ | ❌ | ✅ |
| `GET /api/sdlc/human-inbox/pending` | ✅ | ❌ | ✅ |
| `POST /api/sdlc/tasks/{id}/github/validate` | ✅ | ❌ | ✅ (مرحلهٔ ۵) |
| `POST /api/sdlc/tasks/{id}/github/commit-push` | ✅ | ❌ | ✅ (مرحلهٔ ۵) |
| `POST /api/sdlc/tasks/{id}/github/create-pr` | ✅ | ❌ | ✅ (مرحلهٔ ۵) |

## تسک کلاسیک (Codex / Claude Code)

| Endpoint | main.py فعلی | HEAD |
|---|---|---|
| `GET /api/defaults`, `GET /api/profiles` | 🟡 مقدار ثابت | ✅ |
| `PUT/DELETE /api/profiles/{name}` | ❌ | ✅ |
| `GET /api/tasks` | 🟡 تسک‌های SDLC را برمی‌گرداند (شکل داده با UI نمی‌خواند) | ✅ |
| `POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/{id}` | ❌ | ✅ |
| `GET /api/tasks/{id}/events` (SSE) | ❌ | ✅ |
| `POST /api/tasks/{id}/messages`, `/stop`, `/role` | ❌ | ✅ |
| `POST /api/tasks/{id}/commit`, `/commit-message`, `/push`, `/merge-request` | ❌ | ✅ |
| `POST /api/tasks/{id}/todos`, `DELETE .../todos/{tid}`, `POST .../send` | ❌ | ✅ |
| `GET/PUT /api/role-knowledge` | 🟡 فقط در حافظه | ✅ |
| `GET /api/branches`, `POST /api/branches/switch` | 🟡 / ❌ | ✅ |
| `POST /api/test-setup` | ❌ | ✅ |
| `GET /api/workspace/file|changes|diff` | ✅ | ✅ |
| `GET /api/workspace/tree` | ❌ `workspace_tree` همگام است ولی `await` می‌شود → 500 | ✅ |
| `GET /api/agents/{type}/status` | 🟡 در خطا mock برمی‌گرداند | ✅ |

## نمونه

```bash
curl -X POST http://localhost:8003/api/sdlc/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Add login","description":"JWT auth","project_id":"dwss","priority":"high"}'
```
