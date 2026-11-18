import React from 'react';
import {BarChart3, ClipboardList, RefreshCw, Users} from 'lucide-react';

export const stages=[
  {id:'analyst',label:'تحلیلگر',hint:'بررسی و تحلیل نیازمندی‌ها'},
  {id:'developer',label:'توسعه‌دهنده',hint:'پیاده‌سازی و توسعه'},
  {id:'tester',label:'آزمونگر',hint:'بررسی کیفیت و آزمون'},
  {id:'product_owner',label:'صاحب محصول',hint:'بازبینی و تأیید نهایی'},
];

const taskTitle=task=>task.session_name||task.task_id||'تسک بدون نام';
const statusLabel=status=>({queued:'در صف',running:'در حال اجرا',testing:'در حال آزمون',passed:'موفق',failed:'ناموفق',blocked:'متوقف‌شده',stopped:'متوقف‌شده'})[status]||status||'نامشخص';

export default function DashboardPages({view,tasks,assignments,onMove,loading,error,onRefresh,roleKnowledge={},onRoleKnowledgeChange,onSaveRoleKnowledge,roleKnowledgeSaving=false,roleKnowledgeNotice=''}){
  const counts=stages.map(stage=>tasks.filter(task=>(assignments[task.id]||task.role||'analyst')===stage.id).length);
  const maximum=Math.max(1,...counts);
  const heading=view==='overview'?'نمای کلی':'نقش‌ها';
  return <main className="dashboard-page" aria-label={heading}>
    <div className="dashboard-heading"><div><span className="dashboard-kicker">TASKLOOM / {view==='overview'?'OVERVIEW':'ROLES'}</span><h1>{heading}</h1><p>{view==='overview'?'وضعیت تسک‌ها در مسیر نقش‌های تیم':'مراحل گردش کار بر اساس نقش‌های تیم'}</p></div><button type="button" className="dashboard-refresh" onClick={onRefresh} disabled={loading}><RefreshCw size={16} className={loading?'spin':''}/>{loading?'در حال دریافت…':'به‌روزرسانی'}</button></div>
    {error&&<p className="dashboard-error" role="alert">{error}</p>}
    {view==='roles'&&<div className="role-knowledge-toolbar"><p>ریشهٔ پوشهٔ فایل‌های دانش هر نقش را وارد کنید. فایل‌های Markdown این پوشه هنگام اجرای تسک همان نقش به عامل معرفی می‌شوند.</p><button type="button" onClick={onSaveRoleKnowledge} disabled={roleKnowledgeSaving}>{roleKnowledgeSaving?'در حال ذخیره…':'ذخیره مسیرها'}</button></div>}
    {view==='roles'&&roleKnowledgeNotice&&<p className="role-knowledge-notice" role="status">{roleKnowledgeNotice}</p>}
    {view==='overview'&&<>
      <div className="dashboard-stats"><article><ClipboardList size={19}/><div><span>کل تسک‌ها</span><strong>{tasks.length.toLocaleString('fa-IR')}</strong></div></article><article><BarChart3 size={19}/><div><span>در حال اجرا</span><strong>{tasks.filter(task=>['queued','running','testing'].includes(task.status)).length.toLocaleString('fa-IR')}</strong></div></article><article><Users size={19}/><div><span>مراحل نقش‌ها</span><strong>{stages.length.toLocaleString('fa-IR')}</strong></div></article></div>
      <section className="dashboard-chart" aria-label="نمودار تعداد تسک‌ها در هر نقش"><div className="dashboard-section-heading"><div><h2>توزیع تسک‌ها</h2><p>تعداد تسک‌ها در هر مرحله</p></div><BarChart3 size={19}/></div><div className="dashboard-chart-bars">{stages.map((stage,index)=><div className="dashboard-chart-row" key={stage.id}><span>{stage.label}</span><div className="dashboard-chart-track"><div style={{width:`${counts[index]?Math.max(7,counts[index]/maximum*100):0}%`}}/></div><strong>{counts[index].toLocaleString('fa-IR')}</strong></div>)}</div></section>
      <section className="dashboard-board-section" aria-label="برد کانبان"><div className="dashboard-section-heading"><div><h2>برد کانبان</h2><p>تسک‌ها را میان نقش‌ها بکشید یا مرحله را از روی کارت تغییر دهید.</p></div></div><div className="dashboard-board">{stages.map((stage,index)=><section className={`dashboard-lane lane-${stage.id}`} key={stage.id} aria-label={stage.label} onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();const taskId=event.dataTransfer.getData('text/plain');if(taskId&&tasks.some(task=>task.id===taskId))onMove(taskId,stage.id)}}><div className="dashboard-lane-heading"><span className="dashboard-lane-dot"/><h3>{stage.label}</h3><b>{counts[index].toLocaleString('fa-IR')}</b></div><div className="dashboard-lane-cards">{tasks.filter(task=>(assignments[task.id]||'analyst')===stage.id).map(task=><article className="dashboard-task-card" key={task.id} draggable onDragStart={event=>{event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',task.id)}}><div className="dashboard-task-top"><span dir="auto">{task.task_id}</span><small className={`dashboard-task-status status-${task.status}`}>{statusLabel(task.status)}</small></div><h4 dir="auto">{taskTitle(task)}</h4><p dir="auto">{task.project_path?.split(/[\\/]/).filter(Boolean).pop()||'پروژه نامشخص'}</p><label>مرحله<select aria-label={`مرحلهٔ ${taskTitle(task)}`} value={stage.id} onChange={event=>onMove(task.id,event.target.value)}>{stages.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}</select></label></article>)}{!counts[index]&&<div className="dashboard-lane-empty">تسکی در این مرحله نیست</div>}</div></section>)}</div></section>
    </>}
    {view==='roles'&&<div className="dashboard-roles">{stages.map((stage,index)=><article key={stage.id}><div className="dashboard-role-header"><div className="dashboard-role-number">{String(index+1).padStart(2,'0')}</div><div><h2>{stage.label}</h2><p>{stage.hint}</p></div><b>{counts[index].toLocaleString('fa-IR')} تسک</b></div><label className="role-knowledge-label" htmlFor={`role-knowledge-${stage.id}`}>ریشهٔ فایل‌های دانش<input id={`role-knowledge-${stage.id}`} type="text" dir="ltr" value={roleKnowledge[stage.id]||''} onChange={event=>onRoleKnowledgeChange(stage.id,event.target.value)} placeholder={stage.id==='developer'?'D:\\dws\\docs':'C:\\Users\\name\\docs'} autoComplete="off"/></label></article>)}</div>}
  </main>;
}
