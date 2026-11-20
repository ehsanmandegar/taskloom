# معماری Taskloom

## نمای کلی

```mermaid
flowchart LR
    UI["Frontend<br/>React + Vite :5173<br/>main.jsx / sdlc_dashboard.jsx"]
    API["Backend API<br/>FastAPI :8003<br/>backend/app/main.py"]
    SVC["services.py<br/>SDLCProjectManager<br/>SDLCTaskManager<br/>OllamaAgentRunner / BackendAgent"]
    OLL["Ollama<br/>:11434 /api/chat"]
    CLI["Codex / Claude Code CLI<br/>(حالت تسک کلاسیک)"]
    FS[("فایل‌های JSON<br/>data/projects/*.json<br/>data/tasks/&lt;id&gt;/task.json<br/>data/human-inbox/")]
    GIT[("Git repo هدف")]
    MCP["guide_mcp.py<br/>MCP server راهنماها"]

    UI -- HTTP/JSON --> API --> SVC
    SVC --> OLL
    SVC --> CLI --> GIT
    SVC --> FS
    CLI -. MCP stdio .-> MCP
```

سیستم دو حالت دارد که در یک کد کنار هم زندگی می‌کنند:

1. **حالت تسک کلاسیک** (`TaskState`, `execute_task`, `continue_task`): یک عامل CLI (Codex یا Claude Code)
   روی برنچ `tasks/<id>` در repo هدف کار می‌کند، تست‌ها اجرا می‌شوند و کاربر commit/push/MR را انجام می‌دهد.
   UI آن در `frontend/src/main.jsx` است.
2. **حالت SDLC** (`SDLCTask`, `SDLCTaskManager`): یک خط لولهٔ چندمرحله‌ای با عامل‌های Ollama.
   UI آن در `frontend/src/sdlc_dashboard.jsx` است.

## ماژول‌ها

| فایل | مسئولیت |
|---|---|
| `main.py` (ریشه) | نقطهٔ ورود: `python main.py [--port 8003] [--no-browser] [--data-dir]`؛ UI build‌شده را هم سرو می‌کند |
| `backend/app/main.py` | تعریف FastAPI app، CORS و routeها |
| `backend/app/models.py` | مدل‌های Pydantic: `TaskState`, `SDLCTask`, `SDLCProjectConfig`, `AgentResult`, `HumanIntervention`, ... |
| `backend/app/services.py` | منطق اصلی: اجرای CLI عامل، git، workspace، event streamها، مدیریت پروژه/تسک SDLC، فراخوانی Ollama |
| `backend/app/guide_mcp.py` | یک MCP server روی stdio که فایل‌های Markdown راهنما را به عامل ارائه می‌دهد |
| `backend/app/config.py` | تنظیمات از متغیرهای محیطی: `OLLAMA_BASE_URL`، `OLLAMA_MODEL` (پیش‌فرض `qwen3.5:0.8b`) |
| `frontend/src/main.jsx` | UI تسک کلاسیک + workspace explorer |
| `frontend/src/sdlc_dashboard.jsx` | داشبورد کانبان SDLC، پروژه‌ها، inbox انسانی، GitHub |

## جریان SDLC

```mermaid
sequenceDiagram
    participant U as کاربر
    participant API as FastAPI
    participant TM as SDLCTaskManager
    participant R as OllamaAgentRunner / BackendAgent
    participant D as data/tasks

    U->>API: POST /api/sdlc/tasks
    API->>TM: create_task(request, project)
    TM->>D: save task.json (created)
    TM->>TM: enqueue_task → status=analyzing
    TM->>TM: execute_stage("analysis")
    TM-->>R: asyncio.create_task(_run_agent_async)
    API-->>U: task (فوراً برمی‌گردد)
    R->>R: Ollama /api/chat (در executor)
    R-->>TM: AgentResult
    TM->>D: agent_results[stage] = result
    alt completed
        TM->>TM: _advance_or_complete → مرحلهٔ فعال بعدی
    else needs_human
        TM->>D: status = human_review
    else blocked / failed
        TM->>D: status = failed
    end
```

### ماشین وضعیت (`SDLCStatus`)

```mermaid
stateDiagram-v2
    [*] --> created
    created --> analyzing
    analyzing --> human_review: require_analysis_approval / needs_human
    human_review --> analysis_approved: پاسخ انسان
    analyzing --> backend_running
    analysis_approved --> backend_running
    backend_running --> n8n_running
    n8n_running --> frontend_running
    frontend_running --> testing
    testing --> pending_approval: همهٔ مراحل تمام شد
    pending_approval --> done: تأیید انسان
    analyzing --> failed
    backend_running --> failed
    n8n_running --> failed
    frontend_running --> failed
    testing --> failed
    note right of pending_approval
      POST /api/sdlc/tasks/{id}/approve
    end note
```

`revision`, `human_qa`, `blocked` در enum هستند ولی هیچ مسیری در کد به آن‌ها نمی‌رسد.

مراحل از `project.workflow.stages` خوانده می‌شوند و عامل‌هایی که `enabled=false` دارند رد می‌شوند.

### عامل‌ها (اجراکنندهٔ هر مرحله)

هر مرحله با فیلد `runner` در `AgentConfig` اجرا می‌شود (`backend/app/sdlc_runner.py`):

| `runner` | رفتار |
|---|---|
| `auto` (پیش‌فرض) | اگر مرحله `project_path` دارد و Claude Code (یا Codex) نصب است ← عامل CLI؛ وگرنه Ollama |
| `claude` / `codex` | عامل CLI واقعی در پوشهٔ `project_path` |
| `ollama` | فقط گزارش متنی؛ فایلی نوشته نمی‌شود. فایل‌هایی که مدل «پیشنهاد» می‌دهد در `recommendations.proposed_changes` ثبت می‌شوند، نه در `changes` |

اجرای یک مرحله با عامل CLI:

```mermaid
flowchart TD
    A[ساخت prompt: system_prompt + تسک + knowledge_path + نتایج مراحل قبل + قوانین] --> B[snapshot پوشه]
    B --> C[Claude Code / Codex در project_path<br/>prompt از stdin، حالت acceptEdits]
    C --> D[snapshot دوباره ← changes واقعی]
    D --> E[خواندن بلوک JSON پایانی عامل<br/>status / summary / issues / ...]
    E --> F{test_instructions.command؟}
    F -- بله --> G[Taskloom خودش تست را اجرا می‌کند<br/>شکست تست ← stage failed]
    F -- خیر --> H[AgentResult]
    G --> H
```

- مراحل `analysis` و `qa` فقط گزارش می‌دهند؛ `backend`، `n8n` و `frontend` کد می‌نویسند.
- `changes` را Taskloom از روی دیسک تعیین می‌کند، نه از ادعای مدل.
- وضعیت‌های عامل: `completed` ← مرحلهٔ بعد؛ `needs_human` ← یک HumanIntervention در inbox و `human_review`؛
  `needs_revision` ← `human_review` با `transition_reason` (حلقهٔ بازگشت خودکار: مرحلهٔ ۴)؛ `blocked`/`failed` ← `failed` با دلیل.
- تنظیمات هر مرحله: `project_path`، `knowledge_path`، `system_prompt`، `test_instructions: {"command": "...", "working_directory": "..."}`،
  `cli_timeout_seconds` (پیش‌فرض 3600) و `timeout_seconds` (فقط Ollama).

## ذخیره‌سازی

همه‌چیز فایل JSON است، بدون دیتابیس و بدون قفل:

- `data/projects/<project_id>.json` — `SDLCProjectConfig`
- `data/tasks/<task_id>/task.json` — `SDLCTask` (نوشتن اتمیک با فایل `.tmp` و `replace`)
- `data/human-inbox/pending|resolved/<INT-id>.json` — `HumanIntervention`
- `~/.taskloom/role-knowledge.json` — مسیرهای دانش نقش‌ها (حالت کلاسیک)

مسیرها نسبی هستند (`Path("data/...")`)، پس محل ذخیره به **پوشهٔ جاری هنگام اجرای سرور** بستگی دارد —
به همین دلیل `backend/data/` جدا از `data/` به وجود آمده است.
