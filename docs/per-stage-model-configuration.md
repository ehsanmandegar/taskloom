# راهنمای تنظیم مدل جداگانه برای هر مرحله

## خلاصه

در TaskLoom می‌تونی برای هر مرحله از SDLC (Analysis، Backend، Frontend، QA) یک مدل و provider متفاوت انتخاب کنی.

## مثال کاربردی

فرض کن می‌خوای:
- **Analysis**: با مدل سریع و سبک Ollama Qwen3 انجام بشه
- **Backend**: با مدل تخصصی کدنویسی DeepSeek Coder V2 کار کنه
- **Frontend**: با مدل قدرتمند Claude Sonnet 4 نوشته بشه
- **QA**: با مدل سبک Ollama Qwen3.5 تست بشه

## نحوه تنظیم از طریق UI

### 1. باز کردن تنظیمات پروژه

1. به داشبورد SDLC برو
2. پروژه رو انتخاب کن
3. روی دکمه "تنظیمات پروژه" کلیک کن

### 2. تنظیم مدل پیش‌فرض

در تب **"تنظیمات کلی پروژه"**:
- **ارائه‌دهنده پیش‌فرض**: Ollama را انتخاب کن
- **مدل پیش‌فرض**: qwen3.5:0.8b را انتخاب کن
- **آدرس Ollama**: `http://localhost:11434`

این تنظیمات برای مراحلی که تنظیمات خاص ندارن استفاده می‌شه.

### 3. تنظیم مدل هر مرحله

در تب **"تنظیمات مراحل"**:

#### مرحله Analysis
1. روی "تحلیل" کلیک کن تا باز بشه
2. گزینه "تنظیمات متفاوت از پروژه" رو فعال کن
3. **ارائه‌دهنده**: Ollama
4. **مدل**: qwen3:latest

#### مرحله Backend
1. روی "بک‌اند" کلیک کن
2. گزینه "تنظیمات متفاوت از پروژه" رو فعال کن
3. **ارائه‌دهنده**: Ollama
4. **مدل**: deepseek-coder-v2:latest

#### مرحله Frontend
1. روی "فرانت‌اند" کلیک کن
2. گزینه "تنظیمات متفاوت از پروژه" رو فعال کن
3. **ارائه‌دهنده**: Claude
4. **مدل**: claude-sonnet-4-20250514

#### مرحله QA
1. روی "تست و کیفیت" کلیک کن
2. اگر می‌خوای از مدل پیش‌فرض استفاده کنه، گزینه "تنظیمات متفاوت از پروژه" رو غیرفعال بذار
3. یا برای مدل خاص، تنظیمات رو مشخص کن

### 4. ذخیره تنظیمات

روی دکمه "ذخیره پروژه" کلیک کن.

## نحوه تنظیم از طریق API

### دریافت تنظیمات فعلی

```bash
GET /api/sdlc/projects/{project_id}/ai-settings
```

### به‌روزرسانی تنظیمات

```bash
PUT /api/sdlc/projects/{project_id}/ai-settings
Content-Type: application/json

{
  "default_provider": "ollama",
  "default_model": "qwen3.5:0.8b",
  "ollama_endpoint": "http://localhost:11434",
  "stage_providers": {
    "analysis": {
      "provider": "ollama",
      "model": "qwen3:latest",
      "inherit_from_project": false
    },
    "backend": {
      "provider": "ollama",
      "model": "deepseek-coder-v2:latest",
      "inherit_from_project": false
    },
    "frontend": {
      "provider": "claude",
      "model": "claude-sonnet-4-20250514",
      "inherit_from_project": false
    },
    "qa": {
      "provider": "ollama",
      "model": "qwen3.5:0.8b",
      "inherit_from_project": true
    }
  }
}
```

### دریافت تنظیمات یک مرحله خاص

```bash
GET /api/sdlc/projects/{project_id}/stage-config/backend
```

پاسخ:
```json
{
  "provider": "ollama",
  "model": "deepseek-coder-v2:latest",
  "inherited": false,
  "stage_has_override": true
}
```

## نکات مهم

### 1. مدل‌های Ollama

قبل از استفاده باید مدل رو pull کنی:

```bash
# مدل Analysis
ollama pull qwen3:latest

# مدل Backend
ollama pull deepseek-coder-v2:latest

# مدل پیش‌فرض
ollama pull qwen3.5:0.8b
```

### 2. مدل‌های Claude

برای استفاده از Claude باید:
- Claude CLI نصب باشه
- API Key تنظیم شده باشه
- اسم مدل دقیق رو وارد کنی (مثل `claude-sonnet-4-20250514`)

### 3. مدل‌های Codex

برای استفاده از Codex CLI:
- Kiro Codex CLI نصب باشه
- Endpoint مشخص شده باشه (اگر از remote استفاده می‌کنی)

### 4. ارث‌بری از تنظیمات پروژه

اگر `inherit_from_project: true` باشه، اون مرحله از مدل و provider پیش‌فرض پروژه استفاده می‌کنه.

### 5. بررسی دسترسی مدل‌ها

در UI، کنار هر provider و مدل یک علامت وضعیت نشون داده می‌شه:
- ✅ = در دسترس است
- ❌ = در دسترس نیست

### 6. بروزرسانی لیست مدل‌ها

با کلیک روی دکمه ↻ (Refresh) می‌تونی لیست مدل‌های موجود رو به‌روزرسانی کنی.

## مثال‌های کاربردی

### پروژه کوچک و سریع
```
همه مراحل: Ollama Qwen3.5 (سریع، محلی، رایگان)
```

### پروژه متوسط با بودجه محدود
```
Analysis: Ollama Qwen3
Backend: Ollama DeepSeek Coder V2
Frontend: Ollama Qwen3
QA: Ollama Qwen3.5
```

### پروژه بزرگ با بودجه کافی
```
Analysis: Ollama Qwen3 (سریع)
Backend: Claude Sonnet 4 (کیفیت بالا)
Frontend: Claude Sonnet 4 (کیفیت بالا)
QA: Ollama DeepSeek Coder V2 (تخصصی)
```

### پروژه تخصصی
```
Analysis: Ollama Qwen3
Backend: Ollama DeepSeek Coder V2 (متخصص کدنویسی)
Frontend: Claude Sonnet 4 (UI/UX عالی)
QA: Ollama Qwen3.5 (سریع برای تست‌های زیاد)
```

## عیب‌یابی

### مدل پیدا نمی‌شه

1. بررسی کن که مدل در Ollama نصب شده:
   ```bash
   ollama list
   ```

2. اگر نیست، نصبش کن:
   ```bash
   ollama pull model-name
   ```

3. روی دکمه Refresh در UI کلیک کن

### Provider در دسترس نیست

- **Ollama**: بررسی کن که Ollama service در حال اجرا باشه
  ```bash
  systemctl status ollama  # Linux
  # یا
  ollama serve  # Manual
  ```

- **Claude**: بررسی کن که Claude CLI نصب و پیکربندی شده باشه

- **Codex**: بررسی کن که Kiro Codex App در حال اجرا باشه

### مدل اشتباه استفاده می‌شه

1. بررسی کن که `inherit_from_project` برای اون stage روی `false` باشه
2. مطمئن شو که تنظیمات رو ذخیره کردی
3. پروژه رو ریلود کن

## خلاصه

با این قابلیت می‌تونی:
- ✅ برای هر مرحله provider متفاوت انتخاب کنی (Ollama، Claude، Codex)
- ✅ برای هر مرحله مدل متفاوت انتخاب کنی (Qwen3، DeepSeek، Sonnet، ...)
- ✅ هزینه و کیفیت رو بهینه کنی (محلی برای سرعت، cloud برای کیفیت)
- ✅ از تخصص هر مدل استفاده کنی (DeepSeek برای کد، Sonnet برای UI)
- ✅ تنظیمات پیش‌فرض داشته باشی و فقط موارد خاص رو override کنی

این به تو انعطاف کامل می‌ده تا با توجه به نیاز، بودجه و منابع موجود، بهترین ترکیب مدل‌ها رو برای پروژه‌ات انتخاب کنی! 🎯
