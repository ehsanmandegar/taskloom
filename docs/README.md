# مستندات Taskloom

Taskloom یک پلتفرم SDLC محلی است (FastAPI + React) که یک درخواست را از مراحل
**تحلیل ← بک‌اند ← n8n ← فرانت‌اند ← QA** با عامل‌های هوش مصنوعی (Ollama / Codex / Claude Code)
عبور می‌دهد و تصمیم نهایی (تأیید، commit، push، PR) را به انسان می‌سپارد.

| سند | محتوا |
|---|---|
| [architecture.md](architecture.md) | اجزای سیستم، جریان SDLC، ماشین وضعیت، ذخیره‌سازی |
| [api.md](api.md) | Endpointها و اختلاف بین فرانت‌اند و بک‌اند |
| [git-release-flow.md](git-release-flow.md) | استراتژی برنچ (`sandbox` / `develop` / برنچ هر تسک)، تأیید نهایی، مدیریت نسخه (release) — به انگلیسی |
| [known-issues.md](known-issues.md) | ایرادهای پیدا‌شده در بازبینی کد، به ترتیب اولویت — نقطهٔ شروع بهبود |
| [graphify/](graphify/) | گراف دانش کد (ساخته‌شده با graphify) |

## گراف کد (graphify)

خروجی در `docs/graphify/` است:

- `graph.html` — نمای تعاملی گراف؛ در مرورگر باز کنید.
- `GRAPH_REPORT.md` — گزارش: God nodes، community‌ها، ارتباط‌های غیرمنتظره.
- `graph.json` — دادهٔ خام گراف برای پرس‌وجو.

ساخت گراف بدون LLM و فقط با تحلیل AST انجام می‌شود (هزینه‌ای ندارد). فایل‌های نادیده‌گرفته‌شده
(داده‌های runtime، لاگ‌ها، فایل‌های backup و یادداشت‌های MODAL_*) در `.graphifyignore` در ریشهٔ repo تعریف شده‌اند.

```bash
pip install graphifyy

# بازسازی گراف پس از تغییر کد
python -m graphify update .
rm -rf docs/graphify && mv graphify-out docs/graphify && rm -rf docs/graphify/cache

# پرس‌وجو روی گراف
python -m graphify query "SDLC stage transition" --graph docs/graphify/graph.json
python -m graphify explain "SDLCTaskManager" --graph docs/graphify/graph.json
python -m graphify path "create_sdlc_task" "OllamaAgentRunner" --graph docs/graphify/graph.json
```

> برای استخراج معنایی (مستندات و ارتباط مفهومی) می‌توانید با `python -m graphify install --platform claude`
> اسکیل graphify را در Claude Code نصب کنید و `/graphify .` را اجرا کنید.
