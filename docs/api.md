# API

مستندات تعاملی هنگام اجرای سرور: `http://localhost:8003/docs`

> **به‌روزرسانی سیستم چند-مدلی AI:** TaskLoom اکنون از Ollama به عنوان عامل کدنویسی پیش‌فرض پشتیبانی می‌کند.
> کاربران می‌توانند مدل‌های مختلف Ollama را برای هر مرحله SDLC تنظیم کنند.

✅ واقعی · 🟡 mock / ساختگی · ❌ وجود ندارد

## مدیریت مدل‌های Ollama (Legacy)

| Endpoint | توضیحات | وضعیت |
|---|---|---|
| `GET /api/ollama/models` | لیست مدل‌های نصب شده Ollama | ✅ |
| `GET /api/ollama/connection` | بررسی اتصال به سرور Ollama | ✅ |
| `GET /api/ollama/models/{model_name}` | اطلاعات جزئی یک مدل خاص | ✅ |
| `GET /api/sdlc/projects/{project_id}/model-settings` | دریافت تنظیمات مدل پروژه (legacy) | ✅ |
| `PUT /api/sdlc/projects/{project_id}/model-settings` | به‌روزرسانی تنظیمات مدل پروژه (legacy) | ✅ |
| `GET /api/sdlc/projects/{project_id}/stage-model/{stage}` | دریافت مدل تنظیم شده برای یک مرحله (legacy) | ✅ |

## مدیریت چند-ارائه‌دهنده AI (جدید)

| Endpoint | توضیحات | وضعیت |
|---|---|---|
| `GET /api/ai/providers` | لیست همه ارائه‌دهندگان با وضعیت دسترس‌پذیری | ✅ |
| `GET /api/ai/providers/{provider}/status` | وضعیت و مدل‌های یک ارائه‌دهنده خاص | ✅ |
| `GET /api/ai/providers/{provider}/models` | لیست مدل‌های یک ارائه‌دهنده | ✅ |
| `POST /api/ai/providers/{provider}/refresh` | بروزرسانی لیست مدل‌ها | ✅ |
| `GET /api/sdlc/projects/{project_id}/ai-settings` | دریافت تنظیمات جدید AI پروژه | ✅ |
| `PUT /api/sdlc/projects/{project_id}/ai-settings` | به‌روزرسانی تنظیمات AI پروژه | ✅ |
| `GET /api/sdlc/projects/{project_id}/stage-config/{stage}` | تنظیمات مؤثر ارائه‌دهنده و مدل برای یک مرحله | ✅ |

### نمونه‌های API چند-ارائه‌دهنده

```bash
# لیست همه ارائه‌دهندگان
curl -X GET http://localhost:8003/api/ai/providers

# وضعیت Ollama
curl -X GET http://localhost:8003/api/ai/providers/ollama/status

# مدل‌های Codex
curl -X GET http://localhost:8003/api/ai/providers/codex/models

# تنظیمات AI یک پروژه
curl -X GET http://localhost:8003/api/sdlc/projects/my-project/ai-settings

# به‌روزرسانی: ارائه‌دهنده پیش‌فرض ollama، بک‌اند از codex
curl -X PUT http://localhost:8003/api/sdlc/projects/my-project/ai-settings \
  -H "Content-Type: application/json" \
  -d '{
    "default_provider": "ollama",
    "default_model": "qwen3.5:0.8b",
    "stage_providers": {
      "backend": {"provider": "codex", "model": "o4-mini", "inherit_from_project": false}
    }
  }'

# تنظیمات مؤثر مرحله بک‌اند
curl -X GET http://localhost:8003/api/sdlc/projects/my-project/stage-config/backend
```

### نمونه‌های API Ollama (Legacy)

```bash
# بررسی اتصال Ollama
curl -X GET http://localhost:8003/api/ollama/connection

# دریافت لیست مدل‌ها
curl -X GET http://localhost:8003/api/ollama/models

# دریافت تنظیمات مدل یک پروژه
curl -X GET http://localhost:8003/api/sdlc/projects/my-project/model-settings
```

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

## برنچ‌بندی و نسخه‌ها

جزئیات و جدول کامل Endpointهای `/api/releases/*` و رفتار جدید `approve` در [git-release-flow.md](git-release-flow.md) است.

## نمونه

```bash
curl -X POST http://localhost:8003/api/sdlc/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Add login","description":"JWT auth","project_id":"dwss","priority":"high"}'
```

## Team Workflow Extension

| Endpoint | Description | Status |
|---|---|---|
| `POST /api/sdlc/tasks/{task_id}/backend-review` | Submit backend result for analyst review | ✅ |
| `POST /api/sdlc/tasks/{task_id}/frontend-review` | Submit frontend result for analyst review | ✅ |
| `POST /api/sdlc/tasks/{task_id}/qa-review` | Submit QA test results for review | ✅ |
| `POST /api/sdlc/tasks/{task_id}/analyst-final-review` | Submit analyst's final assessment before PO approval | ✅ |
| `POST /api/sdlc/tasks/{task_id}/po-approval` | Submit Product Owner's decision on release readiness | ✅ |
| `POST /api/sdlc/tasks/{task_id}/release-ready` | Mark task as release-ready after PO approval | ✅ |
| `GET /api/sdlc/tasks/{task_id}/workflow-status` | Get detailed workflow status for a task | ✅ |
| `GET /api/sdlc/projects/{project_id}/default-workflow` | Get the default workflow stages for a new project | ✅ |

### Backend Handoff

The Backend agent should produce a structured handoff:

```json
{
  "api_contract": {
    "method": "POST",
    "path": "/api/v1/users",
    "request_schema": {...},
    "response_schema": {...},
    "validation": {...},
    "error_codes": [...],
    "compatibility_notes": "..."
  },
  "config_changes": [...],
  "migrations": [...],
  "changed_files": [...],
  "commits": [...],
  "frontend_handoff": {
    "required": true,
    "endpoint": "/api/v1/users",
    "data_format": "JSON",
    "states": ["loading", "success", "error", "permission_denied"],
    "accessibility": "..."
  }
}
```

### QA Report

The QA agent produces a structured test report:

```json
{
  "test_strategy": "requirements-led, implementation-independent",
  "test_cases": [
    {
      "id": "TC-001",
      "requirements": ["REQ-001", "REQ-002"],
      "description": "...",
      "environment": "...",
      "steps": [...],
      "expected": "...",
      "actual": "...",
      "result": "pass|fail|blocked",
      "evidence": "...",
      "reproducible": true
    }
  ],
  "coverage_gaps": [...],
  "residual_risks": [...],
  "overall_recommendation": "pass|fail|blocked"
}
```

### PO Decision

The Product Owner decision is structured:

```json
{
  "decision": "approve|changes_requested|reject",
  "rationale": "...",
  "affected_requirements": [...],
  "revision_required": true,
  "return_to_stage": "qa|frontend|backend|analyst"
}
```
