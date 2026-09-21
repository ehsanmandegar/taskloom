# قرارداد عملیاتی DWS Portal و Taskloom

این سند قرارداد همکاری میان repository چندبخشی DWS Portal، عامل Codex و
orchestrator محلی Taskloom است. هدف آن این است که هر نتیجهٔ «آمادهٔ commit» به
یک نسخهٔ دقیق از کد، مجموعه‌ای معلوم از آزمون‌ها و شواهد قابل بازبینی متصل باشد.

این سند هم راهنمای پروژه برای Codex است و هم specification مورد انتظار از
Taskloom. واژه‌های «باید»، «نباید» و «بهتر است» به‌ترتیب معادل MUST، MUST NOT و
SHOULD هستند.

## ۱. محدوده و مسیرها

DWS Portal یک repository چندبخشی است:

```text
<repo-root>/
├── backend/       FastAPI، مدل‌ها، migrationها، pytest و مستندات
├── frontend/      React، TypeScript و Vite
├── admin/         اجزای مدیریتی
└── database_admin/
```

- Taskloom باید مسیر دریافت‌شده را با `git rev-parse --show-toplevel` به ریشهٔ
  واقعی Git تبدیل کند. lock، branch، fingerprint و diff باید نسبت به همین ریشه
  محاسبه شوند، نه صرفاً پوشهٔ `backend`.
- working directory فرمان‌های این سند `<repo-root>/backend` است، مگر آنکه کنار
  فرمان صریحاً مسیر دیگری نوشته شده باشد.
- sandbox عامل باید حداقل کل `<repo-root>` را پوشش دهد تا مصرف‌کننده‌های frontend
  قابل بررسی باشند. نوشتن بیرون از repository مجاز نیست.
- branch هر تسک باید فقط از الگوی `tasks/podw-<task_number>` پیروی کند؛ یعنی
  مقدار نهایی باید با `^tasks/podw-[0-9]+$` منطبق باشد. Taskloom پیش از ساخت
  branch باید شمارهٔ task را validate کند و از تزریق option یا path جلوگیری کند.

## ۲. ترتیب منابع معتبر

در صورت اختلاف، ترتیب اعتبار چنین است:

1. کد فعال و migrationها؛
2. schemaها، مدل‌ها و OpenAPI زنده؛
3. تست‌های سناریویی فعال زیر `tests_v2/`؛
4. مستندات canonical زیر `backend/docs/`؛
5. suite قدیمی `backend/tests/` و راهنماهای سازگاری قدیمی.

اختلاف میان این منابع نباید نادیده گرفته شود. عامل باید اختلاف را گزارش کند و
اگر در محدودهٔ تسک است آن را اصلاح کند؛ در غیر این صورت آن را در بخش ریسک‌های
باقی‌مانده ثبت کند.

## ۳. مرز مسئولیت‌ها

### مسئولیت Codex

Codex باید اثر مستقیم و غیرمستقیم تغییر را تحلیل کند، کد و تست لازم را بنویسد،
مستندات مرتبط را بازبینی کند و نتیجهٔ واقعی کار خود را گزارش دهد. عامل نباید:

- commit، push یا Merge Request ایجاد کند؛
- branch را عوض کند یا تغییرات کاربر را reset، checkout، stash یا حذف کند؛
- assertion، validation یا snapshot را فقط برای سبزشدن تست ضعیف کند؛
- موفقیت تستی را که اجرا نشده، ناقص مانده، timeout شده یا exit code ناموفق دارد
  اعلام کند؛
- secret، JWT، password، connection string کامل یا محتوای `.env` را در پاسخ و
  log منتشر کند.

### مسئولیت Taskloom

Taskloom مرجع نهایی Git state، process state، exit code و آمادگی commit است.
Taskloom نباید عبارت‌های پاسخ عامل مانند «همهٔ تست‌ها پاس شدند» را به‌عنوان
شاهد قبول کند. فقط نتیجهٔ commandی که خودش اجرا و ثبت کرده می‌تواند یک gate را
سبز کند.

### مسئولیت کاربر

کاربر تأیید نهایی تغییر قرارداد API، migration مخرب، بازسازی snapshot، اجرای
ابزارهای stateful، commit، push و ایجاد Merge Request را انجام می‌دهد.

## ۴. شروع هر تسک

Taskloom باید پیش از شروع:

1. Git root، branch جاری، `HEAD` و وضعیت tracked/untracked را ثبت کند.
2. مطمئن شود repository برای همان Git root توسط تسک دیگری قفل نشده است.
3. در صورت dirty بودن repository، به‌طور پیش‌فرض تسک را شروع نکند. پذیرش تغییرات
   موجود فقط با انتخاب صریح کاربر مجاز است و baseline آن تغییرات باید ثبت شود.
4. branch `tasks/podw-<task_number>` را از base انتخاب‌شده بسازد و base SHA را
   ذخیره کند.
5. مسیر راهنماها را canonicalize کند و پس از resolve کردن symlink/junction نیز
   اجازه ندهد فایل از rootهای مجاز خارج شود.
6. نسخه و capabilityهای Codex CLI را بررسی و command نهایی، sandbox و policyهای
   مؤثر را بدون secret ثبت کند.

Codex در ابتدای turn باید `git status`، فایل‌های راهنما، کد مرتبط، تست‌های موجود
و مصرف‌کننده‌های داخلی را بررسی کند. تغییر موجود متعلق به کاربر است مگر اینکه
Taskloom صریحاً آن را به همان سشن نسبت داده باشد.

## ۵. fingerprint و تغییرات هم‌زمان

هر نتیجهٔ آزمون باید به `tested_fingerprint` متصل باشد. fingerprint باید حداقل
این داده‌ها را پوشش دهد:

- SHA فعلی `HEAD`؛
- diff باینری staged و unstaged؛
- نام و محتوای فایل‌های untracked غیرignored؛
- وجود submodule و SHA آن، در صورت استفادهٔ repository.

Taskloom باید fingerprint را در این نقاط محاسبه کند:

1. پیش از اجرای Codex؛
2. پس از پایان turn عامل؛
3. بلافاصله پیش از شروع تست؛
4. بلافاصله پس از پایان تست؛
5. پیش از فعال‌کردن commit؛
6. بلافاصله پس از commit.

اگر fingerprint حین یا بعد از تست تغییر کند، نتیجه باید `STALE` شود و commit
غیرفعال بماند تا همهٔ gateهای لازم روی fingerprint جدید دوباره اجرا شوند. این
قاعده حتی وقتی تغییر توسط خود کاربر یا یک process دیگر ایجاد شده باشد برقرار
است.

Taskloom بهتر است برای هر Git root فقط یک عملیات تغییردهنده فعال داشته باشد.
عملیات read-only می‌توانند هم‌زمان اجرا شوند، ولی نباید نتیجهٔ آن‌ها جایگزین
شواهد مربوط به fingerprint جدید شود.

## ۶. نصب و اجرای backend

پیش‌نیاز معمول پروژه Python 3.11 و PostgreSQL است. Redis، ZooKeeper، SSO و n8n
بسته به مسیر مورد آزمایش لازم می‌شوند. Taskloom نباید محیط مجازی را با activate
کردن shell حدس بزند؛ مسیر interpreter باید در profile پروژه ذخیره شود.

راه‌اندازی اولیه روی ویندوز، از `<repo-root>/backend`:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pip install -r requirements-test.txt
```

راه‌اندازی backend برای تست محلی:

```powershell
.\venv\Scripts\python.exe run.py --host 127.0.0.1 --port 8000
```

- Taskloom باید process آزمون را خودش ایجاد و PID/process tree آن را نگه‌داری
  کند. وجود یک process تصادفی روی port 8000 به معنای معتبر بودن server نیست.
- بعد از تغییر source، dependency، config یا `TEST_DATABASE_URL` باید server
  تحت مالکیت Taskloom restart شود.
- readiness باید پیش از تست بررسی شود. صرف بازبودن TCP port کافی نیست.
- bind پیش‌فرض automation باید `127.0.0.1` باشد، نه `0.0.0.0`.
- توقف یا لغو تسک باید کل process tree متعلق به همان اجرا را متوقف کند، نه هر
  process دیگری که از همان نام یا port استفاده می‌کند.

## ۷. دیتابیس تست و داده‌های حساس

تست‌های سناریویی به `TEST_DATABASE_URL` و artifact محلی JWT در
`backend/.test-artifacts/sso_tokens.json` نیاز دارند.

آماده‌سازی یک‌باره:

```powershell
.\venv\Scripts\python.exe scripts/seed_local_test_database.py --reset-public
.\venv\Scripts\python.exe scripts/bootstrap_sso_tokens.py
.\venv\Scripts\python.exe scripts/grant_local_test_admin.py
```

قواعد ایمنی:

- `--reset-public` مخرب است و فقط برای PostgreSQL محلی و disposable مجاز است.
  Taskloom فقط پس از opt-in صریح کاربر در گزینهٔ setup خودکار یا تأیید دکمهٔ «Setup
  تست» آن را اجرا می‌کند، و پیش از اجرا hostname پارس‌شدهٔ `TEST_DATABASE_URL` باید
  یکی از `localhost`، `127.0.0.1` یا `::1` باشد.
- `bootstrap_sso_tokens.py` ممکن است مرورگر تعاملی باز کند؛ Taskloom باید آن را
  setup کاربر بداند، نه تستی که Codex پنهانی اجرا می‌کند.
- پیش از هر عملیات stateful، hostname دیتابیس مقصد باید پس از parse کامل یکی از
  `localhost`، `127.0.0.1` یا `::1` باشد. صرف جست‌وجوی متنی `localhost` در URL
  کافی نیست.
- مقدار JWT، password، cookie، authorization header و database URL باید در log
  redact شود. فقط نام متغیر و وضعیت configured/not-configured نمایش داده شود.
- فایل‌های `.env` و `.test-artifacts/` نباید وارد diff، artifact اشتراکی، prompt
  یا commit شوند.
- setup خودکار، reset را یک‌بار پیش از شروع Codex و بار دیگر بلافاصله پیش از gate
  تست نهایی انجام می‌دهد. `bootstrap_sso_tokens.py` در هر setup حداکثر سه بار اجرا
  می‌شود و `scripts/grant_local_test_admin.py` با interpreter محیط مجازی اجرا
  می‌شود؛ در صورت شکست، Taskloom تست را اجرا نمی‌کند و وضعیت خطا را گزارش می‌کند.
  خروجی خام اسکریپت‌ها ذخیره یا نمایش داده نمی‌شود تا token، password و URL افشا نشود.

### نام‌گذاری فایل تغییر دیتابیس

فایل‌های تغییر دیتابیس این پروژه SQL هستند و باید در
`backend/alembic/versions/` با قالب دقیق زیر ساخته شوند:

```text
<incremental_number>_podw-<task_number>.sql
```

قواعد تولید نام:

1. `task_number` باید فقط از branch جاری با regex
   `^tasks/podw-([0-9]+)$` استخراج شود. مقدار فرم یا متن prompt منبع معتبر شماره
   تسک نیست.
2. `incremental_number` با خواندن prefix عددی فایل‌های migration معتبر، تبدیل
   آن‌ها به عدد و افزودن یک به بیشترین مقدار محاسبه می‌شود. مرتب‌سازی رشته‌ای
   برای این کار مجاز نیست.
3. شمارهٔ ترتیبی باید با صفر ابتدایی و مطابق عرض عددی جاری repository نوشته شود؛
   عرض حداقل چهار رقم است و با بزرگ‌ترشدن عدد محدود نمی‌شود.
4. نام نهایی نباید description، timestamp یا جداکنندهٔ دیگری داشته باشد و باید
   دقیقاً به `.sql` ختم شود.
5. Taskloom باید شماره را بلافاصله پیش از ساخت فایل دوباره محاسبه کند، وجود فایل
   هم‌نام را بررسی کند و هرگز migration موجود را overwrite نکند.
6. پیش از commit و بعد از rebase/ادغام base branch باید تکراری‌نبودن شماره دوباره
   بررسی شود. در صورت collision وضعیت `BLOCKED` است تا migration جدید با شمارهٔ
   آزاد بعدی rename و دوباره بازبینی و تست شود.

نمونه: اگر branch برابر `tasks/podw-261` و بیشترین شمارهٔ موجود `0018` باشد، نام
فایل جدید چنین است:

```text
0019_podw-261.sql
```

regex اعتبارسنجی فایل جدید:

```regex
^[0-9]{4,}_podw-[0-9]+\.sql$
```

فایل قدیمی `0016_podw_245.sql` از این قرارداد پیروی نمی‌کند و یک استثنای legacy
است. Taskloom باید قرارداد را برای فایل‌های جدید enforce و استثنای قدیمی را
گزارش کند، اما بدون درخواست صریح کاربر حق rename کردن migration تاریخی را ندارد.

## ۸. قرارداد آزمون‌ها

### gate اصلی backend

مرجع regression روزمره API این فرمان است:

```powershell
.\venv\Scripts\python.exe -m pytest -c pytest-v2.ini
```

این suite با API محلی در حال اجرا صحبت می‌کند و برای قراردادهای عمومی و
سناریوهای stateful cleanup دارد. محدودکردن matrix با `TEST_CONTRACT_LIMIT` فقط
برای feedback سریع مجاز است و نتیجهٔ آن `PARTIAL` است؛ چنین نتیجه‌ای commit را
فعال نمی‌کند.

### کنترل مستندات

فرمان زیر ارزان و غیرمخرب است و Taskloom باید پس از هر تغییر route، schema،
model، config، error code یا Markdown اجرا کند:

```powershell
.\venv\Scripts\python.exe scripts/check_docs.py
```

### MCP مستقل پروژه

اگر `backend/project_mcp/` تغییر کرد، این فرمان نیز gate اجباری است:

```powershell
.\venv\Scripts\python.exe -m pytest project_mcp/tests/test_server.py
```

### frontend

اگر frontend تغییر کرد یا تغییر API نیازمند هماهنگی type/client frontend بود، از
`<repo-root>/frontend` اجرا شود:

```powershell
npm.cmd run build
```

Taskloom باید command را بدون interpolation ناامن shell اجرا کند. در صورت نبود
dependencyها، نصب آن‌ها یک مرحلهٔ setup جداگانه است و نباید با نتیجهٔ تست مخلوط
شود.

### suite قدیمی

`pytest.ini` و پوشهٔ `backend/tests/` در حال حاضر fixtureها و چند قرارداد قدیمی
دارند و gate اصلی روزمره نیستند. اجرای `pytest` بدون `-c pytest-v2.ini` فقط وقتی
مجاز است که profile محیط isolated مناسب را مشخص کرده باشد. شکست آن باید با
برچسب `LEGACY_OR_ENVIRONMENT_FAILURE` و همراه شواهد گزارش شود؛ نه مخفی شود و نه
خودکار به regression تسک نسبت داده شود.

### Locust

برای تغییر routeهای GET یا رفتار performance-sensitive، smoke خواندنی:

```powershell
locust -f tests_v2/load/locustfile.py --host http://127.0.0.1:8000 --headless -u 3 -r 1 -t 10s
```

`tests_v2/load/scenario_locustfile.py` write انجام می‌دهد و فقط با تأیید کاربر و
دیتابیس تست محلی مجاز است. Locust جایگزین assertionهای pytest نیست.

## ۹. ماتریس انتخاب gate

| نوع تغییر | gate اجباری |
|---|---|
| فقط Markdown | `scripts/check_docs.py` |
| Python زیر `app/` | pytest v2 و در صورت اثر مستندی، docs checker |
| router، schema، response، auth یا error | pytest v2 و docs checker |
| OpenAPI یا قرارداد client | pytest v2، بازبینی OpenAPI diff و docs checker |
| MCP مستقل | تست `project_mcp` و docs checker |
| frontend | `npm.cmd run build` |
| frontend و backend با هم | pytest v2، frontend build و docs checker |
| GET یا مسیر حساس به performance | موارد بالا و Locust read-only smoke |
| model یا migration | اعتبارسنجی نام migration، pytest v2، docs checker و upgrade روی دیتابیس disposable |

عامل می‌تواند تست‌های بیشتری انتخاب کند، اما حق حذف gate اجباری را ندارد. اگر
پیش‌نیاز gate فراهم نباشد وضعیت `BLOCKED` یا `PARTIAL` است، نه `PASSED`.

## ۱۰. قرارداد API و frontend

هر تغییر route، method، status، header، envelope، field name، type، format، enum،
required، nullability، default، constraint یا error shape تغییر قرارداد محسوب
می‌شود. افزودن یک field نیز باید بازبینی شود؛ زیرا client strict، type تولیدشده
یا snapshot ممکن است با field اضافه ناسازگار باشد.

`tests_v2/contracts/openapi-contract.json` snapshot بازبینی‌شدهٔ قرارداد است.
هر اختلاف باید ابتدا تست را fail کند. فرمان زیر فقط پس از تأیید صریح کاربر برای
تغییر عمدی قرارداد اجرا می‌شود:

```powershell
.\venv\Scripts\python.exe scripts/update_openapi_contract_snapshot.py
```

Codex و Taskloom نباید این فرمان را به‌عنوان autofix شکست تست اجرا کنند. پیش از
تأیید باید خلاصهٔ semantic diff شامل endpoint، request و response متأثر در UI
نمایش داده شود. در صورت وجود consumer متناظر، فایل‌های `frontend/src/api/`، typeها
و محل‌های استفاده نیز باید بررسی شوند.

برای API جدید علاوه بر matrix عمومی، حداقل یک سناریوی موفق و سه حالت منفی مرتبط
با rule اختصاصی آن لازم است. حالت‌های مرتبط می‌توانند auth، permission، ورودی
نامعتبر، not-found، conflict، مرز مقدار، ownership، retry یا concurrency باشند.

## ۱۱. چرخهٔ کار Codex

عامل در هر turn باید این ترتیب را رعایت کند:

1. وضعیت Git و تغییرات موجود را بخواند.
2. guideهای مرتبط و مستندات دامنه را بخواند.
3. impact map شامل callerها، shared code، API، frontend، DB، auth، cache، task و
   integration بسازد.
4. کمترین تغییر منسجم را اعمال کند و تغییرات نامرتبط را دست نزند.
5. happy path و حالت‌های منفی/مرزی لازم را اضافه یا اصلاح کند.
6. diff نهایی را برای تغییر هم‌زمان و نشت secret بازبینی کند.
7. مستندات مرتبط را به‌روز کند یا دلیل عدم نیاز را گزارش دهد.
8. تست هدفمند را برای feedback اجرا کند؛ Taskloom پس از turn gateهای اجباری را
   مستقل اجرا می‌کند.
9. گزارش ساخت‌یافته و صادقانه تحویل دهد.

تغییر ناگهانی فایلی که Codex ایجاد نکرده است باید حفظ و گزارش شود. اگر همان بخش
با ویرایش عامل overlap دارد، عامل باید ویرایش آن بخش را متوقف و تعارض را اعلام
کند.

## ۱۲. قرارداد اجرای Codex در Taskloom

Taskloom باید خروجی machine-readable را مصرف و شناسهٔ دقیق thread را ذخیره کند.
الگوی مورد انتظار:

```text
codex exec --json --sandbox workspace-write -C <repo-root> --output-schema <schema> <task>
codex exec resume --json --output-schema <schema> <SESSION_ID> <follow-up>
```

- resume باید با `SESSION_ID` همان Taskloom session انجام شود، نه با `--last`.
- `thread.started`، `turn.completed`، `turn.failed`، command execution و errorها
  باید جدا از متن پاسخ ذخیره شوند.
- Taskloom باید در startup با `codex exec --help` سازگاری flagهای نسخهٔ نصب‌شده
  را بررسی کند و در صورت ناسازگاری fail closed باشد.
- final response بهتر است با `--output-schema` ساخت‌یافته شود، اما این JSON فقط
  گزارش عامل است و جای fingerprint و exit code را نمی‌گیرد.
- sandbox و policyهای هر resume باید همان محدودیت‌های مورد انتظار profile را
  حفظ کنند؛ Taskloom نباید فرض کند هر option اجرایی بدون بررسی به resume منتقل
  شده است. برای نمونه، بعضی نسخه‌ها روی `codex exec resume` گزینهٔ مستقیم
  `--sandbox` ندارند. در این حالت Taskloom باید policy مؤثر را با روش پشتیبانی‌شدهٔ
  همان نسخه (profile/config) اعمال و verify کند یا اجرا را متوقف کند.

### MCP دانش پروژه

سرور STDIO این repository در Codex با نام `dws_project` ثبت می‌شود. Taskloom باید
پیش از اولین turn این preflight را اجرا و enabled بودن entry را بررسی کند:

```powershell
codex mcp get dws_project --json
```

- Taskloom نباید `--ignore-user-config` را استفاده کند، مگر اینکه تنظیم معادل
  `dws_project` را از راه دیگری به همان اجرای Codex تزریق کرده باشد.
- در صورت نبود یا initialize نشدن MCP، وضعیت باید با دلیل روشن در UI نمایش داده
  شود. profile می‌تواند تعیین کند این وضعیت `BLOCKED` یا warning است.
- Codex باید برای شناخت معماری و ruleهای پروژه ابتدا از ابزارهای read-only این
  MCP مانند `search_docs`، `read_doc`، `search_code` و `read_file` استفاده کند.
- پاسخ MCP شواهد context است، نه شاهد سبزبودن gateهای Taskloom.
- ابزار `run_tests` فعلی MCP فقط مسیرهای suite قدیمی `backend/tests/` را قبول
  می‌کند. Taskloom باید gate اصلی `pytest-v2.ini` را با test runner خودش اجرا
  کند و نباید اجرای MCP را جایگزین آن بداند.
- session فعال پیش از اضافه‌شدن MCP ممکن است tool جدید را نبیند؛ Taskloom باید
  برای اولین استفاده یک Codex process/session تازه ایجاد کند.

فیلدهای حداقلی گزارش عامل:

```json
{
  "summary": "string",
  "files_changed": ["string"],
  "behavior_impact": ["string"],
  "api_contract_changes": ["string"],
  "tests_added_or_updated": ["string"],
  "commands_attempted": [
    {"command": "string", "result": "passed|failed|blocked|not_run"}
  ],
  "documentation": ["string"],
  "remaining_risks": ["string"],
  "blocked_items": ["string"],
  "user_changes_preserved": ["string"]
}
```

Taskloom باید نتیجهٔ نهایی commandهای خودش را جداگانه به این گزارش اضافه کند.

## ۱۳. state machine و gateهای UI

حداقل stateهای قابل مشاهده:

```text
DRAFT → CODEX_RUNNING → CHANGED → TESTING → TESTED → READY_TO_COMMIT
      → COMMITTED → PUSHED → MR_CREATED

FAILED | STALE | PARTIAL | BLOCKED | CANCELLED
```

دکمهٔ commit فقط وقتی فعال است که:

- همهٔ gateهای اجباری برای `tested_fingerprint` پاس شده باشند؛
- هیچ command یا Codex turn فعال نباشد؛
- fingerprint فعلی با `tested_fingerprint` برابر باشد؛
- تغییر قرارداد یا migration نیازمند تأیید حل‌نشده وجود نداشته باشد.

پس از commit، Taskloom باید پاک‌بودن tree و تطابق محتوای commit با نسخهٔ
تست‌شده را بررسی کند. push فقط برای همان commit SHA و ایجاد MR فقط پس از تأیید
وجود همان SHA روی remote مجاز است.

UI باید حداقل این شواهد را نشان دهد:

- base SHA، branch، current SHA و tested fingerprint؛
- فایل‌های تغییرکرده و تغییرات بعد از تست؛
- command، cwd، start/end time، timeout، exit code و خلاصهٔ log؛
- gateهای skipped/partial/blocked و دلیل آن‌ها؛
- process تحت مالکیت Taskloom و وضعیت readiness؛
- OpenAPI semantic diff و درخواست تأیید snapshot؛
- اخطار وجود تغییر هم‌زمان یا stale شدن نتیجه.

## ۱۴. تغییرات لازم در خود Taskloom

برای اجرای کامل این قرارداد، Taskloom باید این قابلیت‌ها را داشته باشد. اگر
قابلیتی هنوز وجود ندارد، نبود آن باید در UI مشخص باشد و آمادگی commit نباید به
اشتباه اعلام شود.

### الزامی

1. resolve کردن Git root و قفل per-repository؛
2. fingerprint شامل tracked، staged، unstaged و untracked و invalidation خودکار؛
3. اتصال نتیجهٔ هر gate به fingerprint دقیق؛
4. test plan چندفرمانی با `cwd`، timeout، required/optional و exit code مستقل؛
5. ذخیرهٔ session ID دقیق Codex و مصرف stream JSONL؛
6. process manager برای server/test و termination کل process tree متعلق به run؛
7. تشخیص setup تعاملی و عملیات مخرب و گرفتن تأیید صریح کاربر؛
8. redaction مرکزی secretها در prompt، log، history و artifact؛
9. review gate جدا برای OpenAPI snapshot و migration؛
10. بررسی دوبارهٔ fingerprint پیش و پس از commit، push و MR؛
11. اجرای command به‌صورت argument list، بدون ساخت shell string از ورودی کاربر؛
12. validate و canonicalize کردن repository و guide pathها، شامل symlink/junction.
13. validator نام migration که شمارهٔ بعدی را محاسبه، task number را فقط از
    branch استخراج و collision را پیش از commit دوباره بررسی کند.

### پیشنهادی

1. project profile با فیلدهای `repo_root`، `component_cwd`، interpreter، server،
   readiness، required gates، triggerها و sensitive value patterns؛
2. نمایش semantic OpenAPI diff به‌جای diff خام snapshot بزرگ؛
3. نگه‌داری evidence bundle شامل metadata و logهای redacted برای هر fingerprint؛
4. تشخیص تغییر فایل در لحظه با filesystem watcher، در کنار fingerprint قطعی؛
5. تفکیک خطای regression، infrastructure، environment، legacy و cancellation؛
6. pin یا allow-list نسخه‌های آزموده‌شدهٔ Codex CLI؛
7. امکان تعریف setup gateهای دستی مانند SSO login بدون سبز نشان‌دادن خودکار آن‌ها.

## ۱۵. معیار پایان موفق

یک تسک فقط زمانی `READY_TO_COMMIT` است که پیاده‌سازی و تست لازم کامل، مستندات
مرتبط بررسی، contract diffهای عمدی تأیید، همهٔ gateهای لازم موفق و workspace
فعلی دقیقاً برابر workspace تست‌شده باشد. نبود test، نبود dependency، بسته‌بودن
SSO یا دیتابیس، timeout و تغییر هم‌زمان هیچ‌کدام موفقیت محسوب نمی‌شوند.

تصمیم commit، متن commit، push و Merge Request همیشه در اختیار کاربر باقی
می‌ماند.
