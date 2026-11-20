# ایرادهای شناخته‌شده (بازبینی کد — 2026-11-20)

نقطهٔ شروع برای بهبود سیستم. ترتیب بر اساس اولویت است.

## ✅ رفع‌شده در مرحلهٔ ۱ (2026-11-20)

- #1 `main.py` از HEAD بازگردانده شد (نسخهٔ mock در scratchpad نگه داشته شد) — #3 هم با آن رفع شد.
- #2 `pending_approval` به enum اضافه شد + `POST /api/sdlc/tasks/{id}/approve` + ستون و دکمهٔ «تأیید نهایی» در داشبورد.
- #4 `config.py` بازنویسی شد و تنها منبع تنظیمات Ollama است — #14 هم رفع شد.
- مدل پیش‌فرض `qwen2.5:0.5b` نصب نبود، پس همهٔ فراخوانی‌ها fail و خروجی ساختگی جایگزین می‌شد؛ پیش‌فرض اکنون `qwen3.5:0.8b` است.
- `AgentConfig.github_config` با نوع `dict[str, str]` مقادیر bool داشت، پس هر پروژهٔ ذخیره‌شده دوباره load نمی‌شد؛ نوع اصلاح شد.
- MIME نوع `.webp/.avif/.svg` در Windows اشتباه بود (پیش‌نمایش تصویر).
- BOM و کاراکترهای خراب در `services.py` حذف شد.
- تست‌ها: ۱۰۴ تست بک‌اند سبز؛ تست‌های جدید در `tests/test_sdlc_approval.py`.

## ✅ رفع‌شده در مرحلهٔ ۲ (2026-11-20)

- #5 `TASKLOOM.bat` بازنویسی شد: build + `python main.py` روی :8003 (حالت `dev` با Vite)؛ بدون `taskkill`؛ هشدار نبود Ollama.
- علت اصلی «صفحهٔ سفید» پیدا شد: رجیستری ویندوز `.js` را `text/plain` معرفی می‌کرد و مرورگر ماژول را اجرا نمی‌کرد؛ MIME در `main.py` ثابت شد.
- `frontend/.env` (اشاره به mock روی :8000) حذف شد؛ proxy `/api` → :8003 در `vite.config.js` برگشت؛ hack `forceSDLC` از `main.jsx` حذف شد (حلقهٔ بی‌نهایتی دیده نشد: ۴ درخواست polling در ۱۵ ثانیه).
- #18 فایل‌های mock/backup/یادداشت‌ها: فایل‌های untracked به `C:\Users\vira\taskloom-archive-2026-11-20` منتقل شدند؛ فایل‌های tracked (`ARCHITECTURE.md` خراب، راهنماهای Docker/Render بی‌پشتوانه، `START_HERE.*`، اسکریپت‌های `test_sdlc_*.py`، `backend.log`) با `git rm` حذف شدند. `SDLC_PLATFORM_GUIDE.md` به `docs/sdlc-platform-guide.md` منتقل شد.

## ✅ رفع‌شده در مرحلهٔ ۵ (2026-11-20)

- هر تسک در repoهای گیت روی برنچ `sdlc/<task-id>` کار می‌کند؛ `main` دست نمی‌خورد؛ تغییرات commit‌نشدهٔ برنچ دیگر مرحله را با پیام روشن متوقف می‌کند.
- endpointهای `github/validate`، `github/commit-push` و `github/create-pr` که داشبورد صدا می‌زد پیاده‌سازی شدند.
- داشبورد خطاهای واقعی سرور را نشان می‌دهد (قبلاً پاسخ خطا را «موفق» نمایش می‌داد) و برنچ، commit و لینک PR تسک را نشان می‌دهد.
- #15 (بخشی): endpointهای GitHub token را ذخیره نمی‌کنند و در خطاها نمایش نمی‌دهند. فرم پروژه هنوز `github_token` را در `data/projects/*.json` ذخیره می‌کند.
- آزمون واقعی: pipeline با Claude Code روی repo گیت نمونه ← برنچ `sdlc/...` ← commit تمیز با خلاصهٔ مراحل ← push به remote محلی. ساخت PR روی GitHub واقعی با mock تست شده، نه با repo واقعی.

**باقی‌مانده:** بازیابی تسک‌های در حال اجرا پس از restart (#13)؛ قفل فایل (#12)؛ حذف ذخیرهٔ token از فرم پروژه (#15)؛ GitLab.

## ✅ رفع‌شده در مرحلهٔ ۴ (2026-11-20)

- #9 حلقهٔ بازبینی: `needs_revision` و شکست تست‌ها مرحلهٔ هدف را تا `max_revision_attempts` بار دوباره اجرا می‌کنند و بعد از انسان می‌پرسند.
- #10 دروازهٔ تأیید تحلیل واقعاً resume می‌شود؛ بازخورد انسان تحلیل را با همان بازخورد دوباره اجرا می‌کند؛ ذخیرهٔ کهنه در `submit_human_response` حذف شد.
- پاسخ انسان به سؤال عامل در prompt اجرای بعدی همان مرحله قرار می‌گیرد؛ `stop` تسک را متوقف می‌کند.
- `require_final_human_approval` رعایت می‌شود (قبلاً همیشه `pending_approval`).
- inbox مسیرش را از `data_dir` می‌گیرد، نه از پوشهٔ جاری؛ اجرای هم‌زمان دو مرحله برای یک تسک رد می‌شود (409).
- داشبورد: خروجی زندهٔ عامل، دلیل وضعیت و تعداد بازبینی در جزئیات تسک؛ جزئیات باز هر ۵ ثانیه تازه می‌شود؛ راهنمای هر نوع درخواست در inbox.
- آزمون واقعی با Claude Code: analysis ← بازخورد انسان («divide هم اضافه شود») ← analysis دوباره ← approve ← backend که divide را هم پیاده کرد ← qa ← `pending_approval`.

**باقی‌مانده:** برنچ git برای پوشه‌های git؛ endpointهای `github/*` داشبورد؛ بازیابی تسک‌های در حال اجرا پس از restart سرور (#13)؛ قفل فایل (#12)؛ نگهداری امن token (#15).

## ✅ رفع‌شده در مرحلهٔ ۳ (2026-11-20)

- #6، #7، #8: مراحل SDLC اکنون با Claude Code / Codex واقعی در `project_path` اجرا می‌شوند (`sdlc_runner.py`).
  خروجی ساختگی تحلیل و قالب ثابت `BackendAgent` حذف شدند؛ `changes` از روی دیسک و نتایج تست از اجرای واقعی می‌آیند.
- `needs_human` اکنون یک درخواست در inbox انسانی می‌سازد؛ `needs_revision` و `blocked` با دلیل ثبت می‌شوند.
- #13 (بخشی): به اجرای پس‌زمینه reference نگه داشته می‌شود (`task_workers`).
- prompt عامل Claude از stdin فرستاده می‌شود (محدودیت ۳۲K کاراکتر خط فرمان ویندوز).
- `test_plan` دستورهای تست با مسیر داخل کوتیشن را در ویندوز درست اجرا نمی‌کرد؛ رفع شد.
- آزمون واقعی: تسک «Add subtract» روی یک پروژهٔ نمونه از analysis → backend → qa با Claude Code عبور کرد، کد و تست واقعی نوشته شد و تست‌ها پاس شدند.

**محدودیت‌های فعلی:** پوشه‌های غیر git بدون برنچ اجرا می‌شوند (تغییرات مستقیم در پوشه)؛ پاسخ انسان به `needs_human`
هنوز به عامل برگردانده نمی‌شود و `needs_revision` خودکار به مرحلهٔ هدف برنمی‌گردد (مرحلهٔ ۴)؛ داشبورد خروجی زندهٔ عامل را نشان نمی‌دهد.

## 🔴 بحرانی — سیستم را از کار می‌اندازد

1. **`backend/app/main.py` در working copy با نسخهٔ mock جایگزین شده است.**
   نسخهٔ commit‌شده (HEAD، 1136 خط) حدود 45 endpoint واقعی داشت؛ نسخهٔ فعلی (357 خط) بیشتر آن‌ها را
   حذف کرده یا با mock جایگزین کرده است. تست‌ها نیز به همین دلیل fail می‌شوند:
   `ImportError: cannot import name 'load_tasks' from 'backend.app.main'`.
   → پیشنهاد: از `git show HEAD:backend/app/main.py` شروع کنیم و فقط تغییرهای لازم را دوباره اعمال کنیم.

2. **وضعیت `SDLCStatus.pending_approval` وجود ندارد** (`services.py:1904`).
   هر تسکی که آخرین مرحله را تمام کند با `AttributeError` به `failed` می‌رود — یعنی هیچ تسکی هرگز کامل نمی‌شود.

3. **ناسازگاری بین `main.py` و `services.py`** (هر کدام 500 برمی‌گرداند):
   - `sdlc_project_manager.create_project(...)` — این متد وجود ندارد (فقط `save_project` هست).
   - `sdlc_task_manager.create_task(request, project)` — آرگومان اجباری `base_task_state` پاس داده نمی‌شود.
   - `sdlc_task_manager.transition_task(...)` — این متد وجود ندارد (`transition_to_next_stage` هست).
   - `await workspace_tree(repo)` — `workspace_tree` همگام است.

4. **`backend/app/config.py` خراب است.** محتوای آن رونوشت گفتگوی یک عامل دیگر است (`Tool: fs_write ...`)، نه کد Python.
   این فایل commit هم شده است (`c2e0849`).

5. **`TASKLOOM.bat` بک‌اند واقعی را اجرا نمی‌کند**؛ `backend/simple_backend.py` را اجرا می‌کند که سراسر mock است.
   همچنین `taskkill /F /IM python.exe` و `node.exe` **همهٔ** پردازه‌های Python/Node دستگاه را می‌کشد.

## 🟠 مهم — رفتار SDLC واقعی نیست

6. **خروجی ساختگی به‌عنوان موفقیت گزارش می‌شود.**
   - اگر Ollama در دسترس نباشد، تحلیل یک نتیجهٔ ثابت با `status="completed"` و «تست‌های پاس‌شده» برمی‌گرداند.
   - `BackendAgent` اصلاً LLM را صدا نمی‌زند؛ یک قالب ثابت می‌نویسد و نتایج تست را hard-code می‌کند (`"Time: 4.7s"`).
   - n8n / frontend / QA فقط متن JSON تولید می‌کنند و هیچ فایلی نمی‌نویسند و هیچ تستی اجرا نمی‌کنند.
   - همهٔ عامل‌ها همیشه `status="completed"` برمی‌گردانند؛ مسیرهای `needs_revision` و `needs_human` عملاً استفاده نمی‌شوند.

7. **`BackendAgent` روی `<project_path>/backend/app/main.py` بدون بررسی overwrite می‌کند.**
   اگر `project_path` خالی باشد، پیش‌فرض `"."` است — یعنی پوشهٔ جاری سرور، که خود `backend/app/main.py` تسک‌لوم است.

8. **Codex/Claude Code در خط لولهٔ SDLC استفاده نمی‌شوند.** زیرساخت قوی اجرای عامل روی برنچ git
   (`execute_task`, sandbox، تست، commit/MR) فقط در حالت کلاسیک است. ادغام این دو بزرگ‌ترین فرصت بهبود است.

9. **حلقهٔ بازبینی (revision) پیاده‌سازی نشده** — `RevisionRequest`، `max_revision_attempts`، `revision_count`
   تعریف شده‌اند ولی هیچ کدی از آن‌ها استفاده نمی‌کند. QA نمی‌تواند کار را به backend برگرداند.

10. **دروازهٔ تأیید انسانی ناقص است.** بعد از `analysis_approved` هیچ کدی اجرای مرحلهٔ بعد را از سر نمی‌گیرد؛
    در `submit_human_response` شیء `task` بعد از `transition_to_next_stage` دوباره save می‌شود و وضعیت جدید را بازنویسی می‌کند.

## 🟡 کیفیت و نگهداری

11. **مسیرهای نسبی** (`Path("data/tasks")`) — داده بسته به پوشهٔ اجرا در `data/` یا `backend/data/` ذخیره می‌شود.
12. **بدون قفل همزمانی**: `_run_agent_async` تسک را load، تغییر و save می‌کند در حالی که درخواست HTTP هم ممکن است همان فایل را بنویسد.
    هر `execute_stage` یک `SDLCProjectManager()` تازه می‌سازد و کل پوشهٔ پروژه‌ها را دوباره می‌خواند.
13. **`asyncio.create_task` بدون نگه‌داشتن reference** — task ممکن است توسط GC جمع شود؛ بعد از restart سرور، تسک‌های در حال اجرا
    برای همیشه در وضعیت `*_running` می‌مانند (بازیابی/checkpoint پیاده نشده).
14. **تعریف تکراری** `OLLAMA_BASE_URL` / `OLLAMA_MODEL` در `services.py` (مقدار `qwen3.5:0.8b` بلافاصله با `qwen2.5:0.5b` جایگزین می‌شود).
15. **`github_token` به‌صورت متن ساده** در `data/projects/*.json` ذخیره می‌شود.
16. **`print` به‌جای logging**؛ `backend.log` (230KB) در git commit شده است.
17. **نامعتبرسازی مرحله hard-code شده**: `StageTransitionRequest` فقط 5 مرحلهٔ ثابت را می‌پذیرد، با اینکه `workflow.stages` قابل تنظیم است.
18. **شلوغی repo**: حدود 20 فایل `*_SUMMARY.md` / `MODAL_*.md`، `main.py.backup`، `main_complete.py`، `simple_backend.py`،
    `quick_start.py`، `test_server.py` و HTML‌های تستی. وقتی چند «نسخهٔ اصلی» وجود دارد، معلوم نیست کدام اجرا می‌شود.

## پیشنهاد ترتیب کار

1. بازگرداندن `main.py` از HEAD + اصلاح config.py + افزودن `pending_approval` ← تست‌ها سبز شوند.
2. یک launcher درست که بک‌اند واقعی را اجرا کند؛ حذف/بایگانی فایل‌های mock و backup.
3. اتصال مراحل SDLC به اجرای واقعی عامل (Codex/Claude Code روی برنچ git) به‌جای قالب ثابت.
4. حلقهٔ revision از QA به مراحل قبل + دروازه‌های تأیید انسانی که واقعاً resume کنند.
5. بازیابی پس از restart، قفل فایل، logging ساخت‌یافته، نگهداری امن token.
