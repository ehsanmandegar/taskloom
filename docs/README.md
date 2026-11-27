# مستندات Taskloom

Taskloom یک پلتفرم SDLC محلی است (FastAPI + React) که یک درخواست را از مراحل
**تحلیل ← بک‌اند ← n8n ← فرانت‌اند ← QA** با عامل‌های هوش مصنوعی (Ollama / Codex / Claude Code)
عبور می‌دهد و تصمیم نهایی (تأیید، commit، push، PR) را به انسان می‌سپارد.

| سند | محتوا |
|---|---|
| [architecture.md](architecture.md) | اجزای سیستم، جریان SDLC، ماشین وضعیت، ذخیره‌سازی |
| [api.md](api.md) | Endpointها و اختلاف بین فرانت‌اند و بک‌اند |
| [git-release-flow.md](git-release-flow.md) | استراتژی برنچ (`sandbox` / `develop` / برنچ هر تسک)، تأیید نهایی، مدیریت نسخه (release) — به انگلیسی |
| [design-and-automation.md](design-and-automation.md) | design system (Radix Themes) و خودکارسازی SDLC: ریسک، تأیید خودکار، تلاش مجدد، نسخهٔ خودکار، خط زمانی و آمار — به انگلیسی |
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


## سیستم چند-مدلی AI

TaskLoom از سیستم چند-مدلی مبتنی بر Ollama پشتیبانی می‌کند:

| سند | محتوا |
|---|---|
| [multi-model-ai-guide.md](multi-model-ai-guide.md) | راهنمای کامل سیستم چند-مدلی، نصب Ollama، پیکربندی مدل‌ها، عیب‌یابی |
| [architecture.md](architecture.md#سیستم-چند-مدلی-ai) | معماری سیستم چند-مدلی در بخش پایانی |

### ویژگی‌های کلیدی سیستم چند-مدلی

1. **پشتیبانی از Ollama**: عامل کدنویسی پیش‌فرض با tool calling کامل
2. **کشف پویا مدل‌ها**: دریافت خودکار مدل‌های نصب شده Ollama
3. **پیکربندی پروژه**: هر پروژه تنظیمات مدل مستقل دارد
4. **تخصیص مرحله‌ای**: هر مرحله SDLC می‌تواند مدل متفاوتی داشته باشد
5. **ویرایش فایل واقعی**: Ollama می‌تواند فایل‌ها را واقعاً ویرایش کند
6. **امنیت کامل**: validation مسیرها و محدودیت دستورات
7. **سازگاری عقبرو**: Claude و Codex همچنان پشتیبانی می‌شوند

### شروع سریع با Ollama

```bash
# نصب Ollama (از ollama.com)
# دانلود مدل پیش‌فرض
ollama pull qwen3.5:0.8b

# اجرای TaskLoom (به صورت خودکار با Ollama کار می‌کند)
python main.py
```

برای اطلاعات بیشتر به [راهنمای سیستم چند-مدلی](multi-model-ai-guide.md) مراجعه کنید.