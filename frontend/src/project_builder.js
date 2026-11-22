// Pure helpers of the project builder form (no React, so `node --test` can cover them).

export const MIN_IDEA = 10;
export const MAX_IDEA = 4000;

export const STACK_OPTIONS = [
  {value: 'auto', label: 'تشخیص خودکار از توضیح'},
  {value: 'python', label: 'Python (pytest)'},
  {value: 'node', label: 'Node.js (node:test)'},
  {value: 'web', label: 'سایت ایستا (HTML/CSS/JS)'},
];

export const AUTONOMY_OPTIONS = [
  {value: 'manual', label: 'دستی', hint: 'همهٔ تصمیم‌ها با شماست؛ فقط مراحل خودکار اجرا می‌شوند.'},
  {value: 'balanced', label: 'متعادل (پیشنهادی)', hint: 'تسک‌های کم‌ریسک و آزمون‌شده خودکار تأیید می‌شوند و مرحلهٔ ناموفق یک بار خودکار تکرار می‌شود. تأیید تحلیل و نسخه با شماست.'},
  {value: 'autopilot', label: 'خودکار', hint: 'تحلیل بی‌ایراد و تسک کم‌ریسک خودکار تأیید می‌شود و پیش‌نویس نسخه ساخته می‌شود. ورود به sandbox همیشه با تأیید شماست.'},
];

export const EMPTY_FORM = {idea: '', name: '', stack: 'auto', autonomy: 'balanced', useAi: true, baseDir: ''};

/** '' when the description is acceptable, else the message to show. */
export function ideaProblem(idea) {
  const length = (idea || '').trim().length;
  if (length < MIN_IDEA) return `توضیح پروژه را کمی کامل‌تر بنویسید (حداقل ${MIN_IDEA} نویسه).`;
  if (length > MAX_IDEA) return `توضیح پروژه بیش از حد طولانی است (حداکثر ${MAX_IDEA} نویسه).`;
  return '';
}

/** Request body of POST /api/sdlc/project-builder. Empty optional fields are left out. */
export function buildRequestBody(form, preview) {
  const body = {idea: form.idea.trim(), stack: form.stack, autonomy: form.autonomy, use_ai: !!form.useAi, preview: !!preview};
  if (form.name.trim()) body.name = form.name.trim();
  if (form.baseDir.trim()) body.base_dir = form.baseDir.trim();
  return body;
}

/** One line per stage of a preview: "backend — 7 فایل". */
export function stageSummary(stage) {
  return `${stage.stage} — ${stage.files.length.toLocaleString('fa-IR')} فایل`;
}
