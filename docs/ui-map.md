# نقشهٔ نام‌های رابط کاربری

هر مودال و بخش مهم داشبورد یک برچسب کوچک با یک کد دارد (مثل `M3-D · AgentResults`).
برای گزارش مشکل همین کد را بگویید؛ این جدول نشان می‌دهد کد به کدام کد منبع اشاره می‌کند.
برچسب‌ها با کامپوننت `UiTag` (`frontend/src/ui_tag.jsx`) ساخته می‌شوند و در DOM با `data-ui="<کد>"` قابل جست‌وجو هستند.

## مودال‌ها

| کد | نام | کجا باز می‌شود | فایل |
|---|---|---|---|
| `M1` | Todo — کارهای بعدی | دکمهٔ «کارهای بعدی» در نمای کلاسیک | `frontend/src/main.jsx` (`TodoPanel`، `showTodoModal`) |
| `M2` | NewTask — ایجاد تسک جدید | دکمهٔ ایجاد تسک در داشبورد SDLC | `frontend/src/sdlc_dashboard.jsx` (`showTaskForm`) |
| `M3` | TaskDetail — جزئیات تسک | کلیک روی یک کارت تسک | `frontend/src/sdlc_dashboard.jsx` (`selectedTask`) |
| `M4` | ProjectForm — ایجاد/ویرایش پروژه | دکمهٔ پروژهٔ جدید یا ویرایش پروژه | `frontend/src/sdlc_dashboard.jsx` (`showProjectForm`) |

## بخش‌های M3 (جزئیات تسک)

| کد | بخش | داده از بک‌اند |
|---|---|---|
| `M3-A` | Status — وضعیت، اولویت، دکمهٔ تأیید نهایی، ثبت نظر و ارجاع به تحلیل (`/send-back`)، دلیل وضعیت | `sdlc_status`، `transition_reason`، `revision_count` |
| `M3-B` | LiveOutput — خروجی زندهٔ عامل (فقط هنگام اجرا) | `base_task.live_output` |
| `M3-C` | Description — شرح تسک | `description` |
| `M3-D` | AgentResults — نتیجهٔ هر مرحله | `agent_results` |
| `M3-E` | RunInfo — اطلاعات اجرا | `revision_count`، `created_at`، ... |
| `M3-F` | GitHub — برنچ، commit، push و PR؛ برای هر مرحلهٔ دارای ریپو دکمه‌های یک‌کلیکی جدا | `repos`، endpointهای `github/*` |

## مراحل M4 (فرم پروژه)

| کد | مرحله |
|---|---|
| `M4-1` | ProjectInfo — شناسه، نام، توضیحات |
| `M4-2` | Workflow — مراحل، دروازه‌های تأیید، سقف بازبینی |
| `M4-3` | Agents — مسیرها، prompt، تست هر agent |
| `M4-3R` | `<stage>` Repository — ریپوی همان agent: بدون ریپو / ریپوی جدید / ریپوی موجود، token، پوشهٔ محلی، برنچ پایه |
| `M4-4` | Review — تأیید نهایی |

## پیام‌های مرورگر (`alert`)

| کد | پیام |
|---|---|
| `A1` | ProjectInfo — جزئیات پروژه |
| `A2` | ProjectDeleted — حذف پروژه |
| `A3` | GitHubValidate — نتیجهٔ «بررسی دسترسی» در M3-F |
| `A4` | CommitPush — نتیجهٔ «Commit و Push» در M3-F |
| `A5` | PullRequest — نتیجهٔ «Pull Request» در M3-F |
| `A6` | RepoPrepare — نتیجهٔ «آماده‌سازی ریپو» در M4-3R |

اگر مودال یا بخش جدیدی اضافه شد، یک کد تازه (`M5`، `M3-G`، ...) به آن بدهید و این جدول را به‌روز کنید.
