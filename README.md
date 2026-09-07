# Taskloom

پروفایل‌های پروژه از بالای فرم قابل ذخیره و بازیابی‌اند و به‌طور پیش‌فرض در `~/.taskloom/profiles.json` نگهداری می‌شوند. برای تغییر محل فایل، متغیر محیطی `TASKLOOM_PROFILES_PATH` را تنظیم کنید. در بخش راهنما می‌توانید علاوه بر فایل، مسیر پوشه وارد کنید؛ همه فایل‌های `.md` آن پوشه و زیرپوشه‌هایش به‌صورت خودکار استفاده می‌شوند.

داشبورد FastAPI + React برای اجرای کنترل‌شده‌ی تسک‌های مهندسی با Codex.

## راه‌اندازی

پیش‌نیازها: Python 3.10+، Node.js 18+، Git و Codex CLI که قبلاً login شده باشد.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
Set-Location frontend
npm.cmd install
npm.cmd run build
Set-Location ..
.venv\Scripts\uvicorn main:app --reload
```

نسخه build شده روی `http://localhost:8000` در دسترس است. برای توسعه UI، در ترمینال دوم `Set-Location frontend; npm.cmd run dev` را اجرا کنید؛ Vite درخواست‌های `/api` را به FastAPI می‌فرستد.

Taskloom تنها از یک repository تمیز شروع می‌کند، برنچ `task/<task-id>` می‌سازد و Codex را با sandbox محدود به workspace اجرا می‌کند. سپس تست خودکار یا دستور واردشده را اجرا می‌کند. commit فقط پس از پاس‌شدن تست و push فقط بعد از commit فعال می‌شود.

> این ابزار برای اجرای محلی و کاربر مورد اعتماد طراحی شده است؛ آن را بدون احراز هویت روی اینترنت منتشر نکنید.
