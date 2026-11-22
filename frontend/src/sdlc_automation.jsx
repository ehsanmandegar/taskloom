import React, {useCallback, useEffect, useState} from 'react';
import {Badge, Callout, Card, Flex, Grid, Select, Switch, Text, TextField} from '@radix-ui/themes';
import {Activity, AlertTriangle, Bot, CheckCircle2, Gauge, RefreshCw, ShieldCheck, Timer, User} from 'lucide-react';
import {
  EVENT_LABELS, RISK_LABELS, formatDuration, formatPercent, riskTone,
} from './sdlc_automation.js';

const API = import.meta.env.VITE_API_URL || '';

/** Project form section: which decisions Taskloom may take by itself. Every switch defaults to "a human decides". */
export function AutonomyFields({workflow, onChange}) {
  const rows = [
    ['auto_analysis_approval', 'تأیید خودکار تحلیل', 'اگر تحلیل کامل باشد و مسئلهٔ باز یا پرسش بی‌پاسخ نداشته باشد، بدون انتظار برای انسان ادامه می‌دهد (نیازمند «تأیید تحلیل توسط انسان»).'],
    ['auto_final_approval', 'تأیید نهایی خودکار برای تسک‌های کم‌ریسک', 'تسک کوچک و آزمون‌شده که به فایل‌های حساس دست نزده، خودکار تأیید و در develop ادغام می‌شود؛ بقیه منتظر انسان می‌مانند.'],
    ['auto_release', 'ساخت خودکار پیش‌نویس نسخه', 'وقتی تعداد کافی تسک ادغام‌شده جمع شد، برنچ release ساخته و آزمون می‌شود. ادغام در sandbox همیشه با تأیید انسان است.'],
  ];
  return (
    <Card className="sdlc-autonomy" variant="surface" mt="3">
      <Flex align="center" gap="2" mb="2"><Bot size={16} /><Text weight="bold" size="2">خودکارسازی و نقش انسان</Text></Flex>
      <Text size="1" color="gray" as="p" mb="3">هر گزینه یک تصمیم را به Taskloom می‌سپارد. هر جا که اطمینان کافی نباشد، تسک با دلیل روشن به انسان ارجاع می‌شود.</Text>
      {rows.map(([key, label, hint]) => (
        <Flex key={key} align="start" gap="3" mb="3">
          <Switch checked={!!workflow[key]} onCheckedChange={checked => onChange({[key]: checked})} aria-label={label} />
          <div><Text size="2" weight="medium">{label}</Text><Text size="1" color="gray" as="p">{hint}</Text></div>
        </Flex>
      ))}
      <Grid columns={{initial: '1', sm: '3'}} gap="3">
        <label><Text size="1" color="gray">بیشترین ریسک برای تأیید خودکار</Text>
          <Select.Root value={workflow.auto_approval_max_risk || 'low'} onValueChange={value => onChange({auto_approval_max_risk: value})} disabled={!workflow.auto_final_approval}>
            <Select.Trigger style={{width: '100%'}} aria-label="بیشترین ریسک" />
            <Select.Content><Select.Item value="low">کم</Select.Item><Select.Item value="medium">متوسط</Select.Item></Select.Content>
          </Select.Root>
        </label>
        <label><Text size="1" color="gray">تلاش مجدد خودکار مرحلهٔ ناموفق</Text>
          <TextField.Root type="number" min="0" max="5" value={workflow.auto_retry_failed_stages ?? 0}
            onChange={event => onChange({auto_retry_failed_stages: Math.max(0, Math.min(5, parseInt(event.target.value, 10) || 0))})} aria-label="تعداد تلاش مجدد خودکار" />
        </label>
        <label><Text size="1" color="gray">حداقل تسک برای نسخهٔ خودکار</Text>
          <TextField.Root type="number" min="1" max="50" value={workflow.auto_release_min_tasks ?? 2} disabled={!workflow.auto_release}
            onChange={event => onChange({auto_release_min_tasks: Math.max(1, parseInt(event.target.value, 10) || 1)})} aria-label="حداقل تسک برای نسخه" />
        </label>
      </Grid>
    </Card>
  );
}

/** Risk of a finished task and why: shown in the task details. */
export function RiskBadge({risk}) {
  if (!risk) return null;
  return (
    <Callout.Root color={riskTone(risk.level)} size="1" className="sdlc-risk" role="status">
      <Callout.Icon><Gauge size={16} /></Callout.Icon>
      <Callout.Text>
        ریسک {RISK_LABELS[risk.level] || risk.level} (امتیاز {risk.score})
        {risk.reasons.length === 0
          ? ' — تغییر کوچک و آزمون‌شده'
          : <ul className="sdlc-risk-reasons">{risk.reasons.map(reason => <li key={reason} dir="auto">{reason}</li>)}</ul>}
      </Callout.Text>
    </Callout.Root>
  );
}

/** Audit trail of a task: what the pipeline did on its own and where a human decided. */
export function Timeline({events}) {
  if (!events?.length) return null;
  return (
    <section className="sdlc-timeline" aria-label="خط زمانی تسک">
      <h4><Activity size={14} /> خط زمانی ({events.length})</h4>
      <ol>
        {events.map((event, index) => {
          const meta = EVENT_LABELS[event.kind] || {label: event.kind, tone: 'gray'};
          return (
            <li key={`${event.at}-${index}`}>
              <Badge color={meta.tone} size="1">{meta.label}</Badge>
              <Text size="1" as="span" dir="auto">{event.message}</Text>
              <small>
                {event.actor === 'human' ? <User size={11} /> : <Bot size={11} />} {event.actor}
                {event.duration_seconds != null && <> · <Timer size={11} /> {formatDuration(event.duration_seconds)}</>}
                {' · '}{new Date(event.at).toLocaleTimeString('fa-IR')}
              </small>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Delivery and automation metrics. */
export function MetricsPanel({project}) {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/sdlc/metrics${project ? `?project=${encodeURIComponent(project)}` : ''}`);
      if (!response.ok) throw new Error(`خطای سرور (${response.status})`);
      setMetrics(await response.json()); setError('');
    } catch (err) { setError(err.message); }
  }, [project]);
  useEffect(() => { load(); }, [load]);

  const cards = metrics ? [
    ['تسک‌ها', metrics.total, `${metrics.done} انجام‌شده`, <CheckCircle2 size={16} key="i1" />],
    ['نرخ موفقیت', formatPercent(metrics.success_rate), 'انجام‌شده از کل', <ShieldCheck size={16} key="i2" />],
    ['میانگین زمان چرخه', formatDuration(metrics.avg_cycle_seconds), 'از ایجاد تا تأیید', <Timer size={16} key="i3" />],
    ['موفقیت در اولین تلاش', formatPercent(metrics.first_pass_rate), 'بدون بازبینی و تلاش مجدد', <Gauge size={16} key="i4" />],
    ['نرخ خودکارسازی', formatPercent(metrics.automation_rate), 'تأیید بدون انسان', <Bot size={16} key="i5" />],
    ['تلاش مجدد خودکار', metrics.auto_retries, `${metrics.escalations} ارجاع به انسان`, <RefreshCw size={16} key="i6" />],
  ] : [];
  return (
    <section className="sdlc-metrics" aria-label="آمار و خودکارسازی">
      <Flex align="center" justify="between" mb="3">
        <Text size="4" weight="bold">آمار و خودکارسازی</Text>
        <button type="button" className="sdlc-btn sdlc-btn-secondary" onClick={load}><RefreshCw size={14} /> به‌روزرسانی</button>
      </Flex>
      {error && <Callout.Root color="red" mb="3"><Callout.Icon><AlertTriangle size={16} /></Callout.Icon><Callout.Text>{error}</Callout.Text></Callout.Root>}
      {metrics && metrics.total === 0 && <Text color="gray" as="p">هنوز تسکی برای محاسبهٔ آمار وجود ندارد.</Text>}
      {metrics && metrics.total > 0 && (
        <>
          <Grid columns={{initial: '2', md: '3'}} gap="3" mb="4">
            {cards.map(([label, value, hint, icon]) => (
              <Card key={label} variant="surface"><Flex align="center" gap="2" mb="1">{icon}<Text size="1" color="gray">{label}</Text></Flex>
                <Text size="6" weight="bold" as="div">{value}</Text><Text size="1" color="gray">{hint}</Text></Card>
            ))}
          </Grid>
          <Grid columns={{initial: '1', md: '2'}} gap="3">
            <Card variant="surface"><Text weight="bold" size="2" as="p" mb="2">توزیع ریسک تسک‌ها</Text>
              {['low', 'medium', 'high'].map(level => (
                <Flex key={level} align="center" gap="2" mb="1"><Badge color={riskTone(level)}>{RISK_LABELS[level]}</Badge><Text size="2">{metrics.risk[level] || 0}</Text></Flex>
              ))}
            </Card>
            <Card variant="surface"><Text weight="bold" size="2" as="p" mb="2">میانگین زمان هر مرحله</Text>
              {Object.keys(metrics.stage_avg_seconds).length === 0 && <Text size="2" color="gray">دادهای ثبت نشده است.</Text>}
              {Object.entries(metrics.stage_avg_seconds).map(([stage, seconds]) => (
                <Flex key={stage} justify="between" mb="1"><code dir="ltr">{stage}</code><Text size="2">{formatDuration(seconds)}</Text></Flex>
              ))}
            </Card>
          </Grid>
        </>
      )}
    </section>
  );
}
