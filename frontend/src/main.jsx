import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Bot, GitBranch, GitPullRequest, Play, CheckCircle2, XCircle, FileCode2, Terminal, GitCommit, Upload, Sparkles, Moon, Sun, Save, Trash2, MessageCircle, Send} from 'lucide-react';
import './styles.css';
import {formatTime} from './timer.js';
import {getInitialTheme, nextTheme} from './theme.js';

const API = import.meta.env.VITE_API_URL || '';
const initial = {project_path:'', guide_paths:'', task_id:'podw-205', request:'', test_command:''};
const apiError=(detail,fallback)=>{
  if(typeof detail==='string'&&detail.trim())return detail;
  if(Array.isArray(detail))return detail.map(item=>{const field=Array.isArray(item?.loc)?item.loc.slice(1).join(' / '):'ورودی';return `${field}: ${item?.msg||'مقدار نامعتبر است'}`}).join(' | ')||fallback;
  if(typeof detail?.message==='string')return detail.message;
  return fallback;
};

function Clock(){
  const [now,setNow]=useState(()=>new Date());
  useEffect(()=>{const timer=setInterval(()=>setNow(new Date()),10);return()=>clearInterval(timer)},[]);
  return <time className="clock" dateTime={now.toISOString()} aria-label="زمان فعلی"><small>زمان فعلی</small><b dir="ltr">{formatTime(now)}</b></time>;
}

function App(){
  const [form,setForm]=useState(initial), [task,setTask]=useState(null), [busy,setBusy]=useState(false), [tab,setTab]=useState('changes'), [notice,setNotice]=useState(''), [chatMessage,setChatMessage]=useState('');
  const [profiles,setProfiles]=useState([]), [selectedProfile,setSelectedProfile]=useState(''), [sessions,setSessions]=useState([]);
  const [startupDefaults,setStartupDefaults]=useState(initial);
  const [theme,setTheme]=useState(()=>getInitialTheme(localStorage,window.matchMedia('(prefers-color-scheme: dark)').matches));
  const update=e=>{const {name,value}=e.target;if(name!=='project_path'||!startupDefaults.project_path||value===startupDefaults.project_path){setForm({...form,[name]:value});return}setForm(current=>({...current,project_path:value,guide_paths:current.guide_paths===startupDefaults.guide_paths?'':current.guide_paths,test_command:current.test_command===startupDefaults.test_command?'':current.test_command}))};
  function rememberTask(next){setTask(next);setSessions(current=>[next,...current.filter(item=>item.id!==next.id)]);localStorage.setItem('taskloom-active-session',next.id)}
  useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem('taskloom-theme',theme)},[theme]);
  useEffect(()=>{fetch(`${API}/api/defaults`).then(async r=>{if(!r.ok)throw Error('خواندن پیش‌فرض‌ها ناموفق بود');const defaults=await r.json();const loaded={...initial,project_path:defaults.project_path||'',guide_paths:(defaults.guide_paths||[]).join('\n'),test_command:defaults.test_command||''};setStartupDefaults(loaded);setForm(current=>({...current,project_path:current.project_path||loaded.project_path,guide_paths:current.guide_paths||loaded.guide_paths,test_command:current.test_command||loaded.test_command}))}).catch(e=>setNotice(e.message))},[]);
  useEffect(()=>{fetch(`${API}/api/profiles`).then(async r=>{if(!r.ok)throw Error('خواندن پروفایل‌ها ناموفق بود');setProfiles(await r.json())}).catch(e=>setNotice(e.message))},[]);
  useEffect(()=>{fetch(`${API}/api/tasks`).then(async r=>{if(!r.ok)throw Error('خواندن سشن‌ها ناموفق بود');const items=await r.json();setSessions(items);const active=items.find(item=>item.id===localStorage.getItem('taskloom-active-session'))||items[0];if(active)setTask(active)}).catch(e=>setNotice(e.message))},[]);
  useEffect(()=>{ if(!task || ['passed','failed'].includes(task.status)) return; const timer=setInterval(async()=>{const r=await fetch(`${API}/api/tasks/${task.id}`); if(r.ok)rememberTask(await r.json())},1400); return()=>clearInterval(timer)},[task?.id,task?.status]);
  async function start(e){e.preventDefault();setBusy(true);setNotice('');try{const body={...form,guide_paths:form.guide_paths.split('\n').map(x=>x.trim()).filter(Boolean),test_command:form.test_command||null};const r=await fetch(`${API}/api/tasks`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(apiError(d.detail,'شروع تسک ناموفق بود'));rememberTask(d)}catch(err){setNotice(err.message)}finally{setBusy(false)}}
  async function action(kind,body){setBusy(true);setNotice('');try{const r=await fetch(`${API}/api/tasks/${task.id}/${kind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(apiError(d.detail,'انجام عملیات ناموفق بود'));rememberTask(d.task);setNotice({commit:'تغییرات با موفقیت commit شدند.',push:'برنچ با موفقیت push شد.','merge-request':'درخواست ادغام با موفقیت ساخته شد.'}[kind])}catch(e){setNotice(e.message)}finally{setBusy(false)}}
  async function generateCommitMessage(){if(!task?.codex_thread_id)return;setBusy(true);setNotice('');try{const r=await fetch(`${API}/api/tasks/${task.id}/commit-message`,{method:'POST'});const d=await r.json();if(!r.ok)throw Error(apiError(d.detail,'ساخت پیام commit ناموفق بود'));setTask(current=>({...current,commit_message:d.message}));setNotice('پیام commit پیشنهادی Codex در فیلد قرار گرفت.')}catch(e){setNotice(e.message)}finally{setBusy(false)}}
  async function sendMessage(e){e.preventDefault();const message=chatMessage.trim();if(!message||!task?.codex_thread_id)return;setBusy(true);setNotice('');try{const r=await fetch(`${API}/api/tasks/${task.id}/messages`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});const d=await r.json();if(!r.ok)throw Error(apiError(d.detail,'ارسال پیام ناموفق بود'));rememberTask(d);setChatMessage('');setTab('summary')}catch(err){setNotice(err.message)}finally{setBusy(false)}}
  function submitChatOnEnter(e){if(e.key!=='Enter'||e.shiftKey||e.nativeEvent.isComposing)return;e.preventDefault();e.currentTarget.form?.requestSubmit()}
  async function chooseSession(id){if(!id){setTask(null);localStorage.removeItem('taskloom-active-session');return}setBusy(true);setNotice('');try{const r=await fetch(`${API}/api/tasks/${id}`);const d=await r.json();if(!r.ok)throw Error(apiError(d.detail,'خواندن سشن ناموفق بود'));rememberTask(d)}catch(err){setNotice(err.message)}finally{setBusy(false)}}
  function chooseProfile(name){setSelectedProfile(name);const profile=profiles.find(item=>item.name===name);if(profile)setForm(current=>({...current,project_path:profile.project_path,guide_paths:profile.guide_paths.join('\n'),test_command:profile.test_command||''}))}
  async function saveProfile(){const name=(selectedProfile||window.prompt('نام پروفایل پروژه را وارد کنید:')||'').trim();if(!name)return;setBusy(true);setNotice('');try{const profile={name,project_path:form.project_path,guide_paths:form.guide_paths.split('\n').map(x=>x.trim()).filter(Boolean),test_command:form.test_command||null};const r=await fetch(`${API}/api/profiles/${encodeURIComponent(name)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(profile)});const d=await r.json();if(!r.ok)throw Error(apiError(d.detail,'ذخیره پروفایل ناموفق بود'));setProfiles(current=>[...current.filter(item=>item.name!==name),d].sort((a,b)=>a.name.localeCompare(b.name)));setSelectedProfile(name);setNotice('پروفایل پروژه ذخیره شد.')}catch(e){setNotice(e.message)}finally{setBusy(false)}}
  async function removeProfile(){if(!selectedProfile)return;setBusy(true);setNotice('');try{const r=await fetch(`${API}/api/profiles/${encodeURIComponent(selectedProfile)}`,{method:'DELETE'});if(!r.ok){const d=await r.json();throw Error(apiError(d.detail,'حذف پروفایل ناموفق بود'))}setProfiles(current=>current.filter(item=>item.name!==selectedProfile));setSelectedProfile('');setNotice('پروفایل حذف شد.')}catch(e){setNotice(e.message)}finally{setBusy(false)}}
  const running=task&&!['passed','failed'].includes(task.status), passed=task?.status==='passed', codexTyping=task&&['queued','running'].includes(task.status);
  return <div className="app" dir="rtl">
    <header><div className="brand"><span className="logo"><Sparkles size={20}/></span><div><b>Taskloom</b><small>Codex delivery console</small></div></div><div className="header-status"><Clock/><button className="theme-toggle" type="button" onClick={()=>setTheme(nextTheme(theme))} aria-label={theme==='dark'?'فعال‌کردن تم روشن':'فعال‌کردن تم تاریک'} aria-pressed={theme==='dark'}>{theme==='dark'?<Sun size={16}/>:<Moon size={16}/>}<span>{theme==='dark'?'روشن':'دارک'}</span></button><div className="online"><i/> Codex محلی</div></div></header>
    <main>
      <section className="intro"><div><span className="eyebrow"><Bot size={15}/> دستیار توسعهٔ شما</span><p>کد و مستندات را آماده می‌کند؛ شما تأیید نهایی را انجام می‌دهید.</p></div><div className="orb"><Bot size={46}/></div></section>
      <div className="grid">
        <form className="card form" onSubmit={start}>
          <div className="card-title"><span>تعریف تسک</span><em>01</em></div>
          <div className="profile-picker"><select aria-label="پروفایل پروژه" value={selectedProfile} onChange={e=>chooseProfile(e.target.value)}><option value="">پروفایل پروژه…</option>{profiles.map(profile=><option key={profile.name} value={profile.name}>{profile.name}</option>)}</select><button type="button" onClick={saveProfile} disabled={busy||!form.project_path} title="ذخیره پروفایل"><Save size={16}/><span>{selectedProfile?'به‌روزرسانی':'ذخیره'}</span></button><button className="danger" type="button" onClick={removeProfile} disabled={busy||!selectedProfile} title="حذف پروفایل"><Trash2 size={16}/></button></div>
          <label>آدرس پروژه <small>پیش‌فرض Taskloom است؛ با تغییر مسیر، راهنما و تست پیش‌فرض آن پروژه پاک می‌شوند</small><input name="project_path" value={form.project_path} onChange={update} placeholder="C:\\work\\my-project" required/></label>
          <label>فایل‌ها یا پوشه‌های راهنما <small>هر مسیر در یک خط؛ پوشه‌ها تمام فایل‌های md را اضافه می‌کنند</small><textarea name="guide_paths" value={form.guide_paths} onChange={update} rows="2" placeholder={'AGENTS.md\nC:\\work\\docs'}/></label>
          <div className="row"><label>شماره تسک<input name="task_id" value={form.task_id} onChange={update} required/></label><label>دستور تست <small>اختیاری</small><input name="test_command" value={form.test_command} onChange={update} placeholder="pytest -q"/></label></div>
          <label>درخواست شما<textarea className="request" name="request" value={form.request} onChange={update} required placeholder="دقیقاً بگو چه چیزی باید ساخته یا اصلاح شود…"/></label>
          <button className="primary" disabled={busy||running}><Play size={17}/>{running?'در حال اجرا…':'شروع اجرای تسک'}</button>{notice&&<div className="notice">{notice}</div>}
        </form>
        <section className="card workspace"><div className="card-title"><span>وضعیت اجرا</span><em>02</em></div>
          {sessions.length>0&&<label className="session-picker">گفت‌وگوهای اخیر<select aria-label="گفت‌وگوهای اخیر" value={task?.id||''} onChange={e=>chooseSession(e.target.value)} disabled={busy}>{sessions.map(item=><option key={item.id} value={item.id}>{item.task_id} — {item.step}</option>)}</select></label>}
          {!task?<div className="empty"><div><GitBranch size={36}/></div><h3>هنوز اجرایی شروع نشده</h3><p>اطلاعات تسک را وارد کن تا روند ساخت اینجا نمایش داده شود.</p></div>:<>
            <div className="status"><span className={`status-icon ${task.status}`}>{passed?<CheckCircle2/>:task.status==='failed'?<XCircle/>:<span className="spinner"/>}</span><div><b>{task.step}</b><small><GitBranch size={13}/> {task.branch}</small></div><mark className={task.status}>{task.status}</mark></div>
            {task.error&&<div className="error">{task.error}</div>}
            <div className="tabs"><button type="button" className={tab==='changes'?'active':''} onClick={()=>setTab('changes')}><FileCode2 size={15}/> تغییرات <b>{task.changed_files.length}</b></button><button type="button" className={tab==='tests'?'active':''} onClick={()=>setTab('tests')}><Terminal size={15}/> تست‌ها</button><button type="button" className={tab==='summary'?'active':''} onClick={()=>setTab('summary')}><Bot size={15}/> خلاصه</button></div>
            <pre>{tab==='changes'?(task.diff||'در انتظار تغییرات…'):tab==='tests'?(task.test_output||'تست‌ها هنوز اجرا نشده‌اند…'):(task.summary||task.logs.join('\n')||'در حال تحلیل…')}</pre>
            <section className="chat" aria-label="Chat with Codex">
              <div className="chat-title"><MessageCircle size={16}/> گفت‌وگو با Codex <small>{task.messages.length} پیام</small></div>
              <div className="chat-history">{task.messages.map((message,index)=><article className={`chat-message ${message.role}`} key={index}><b>{message.role==='user'?'شما':'Codex'}</b><p>{message.content}</p></article>)}{codexTyping&&<div className="chat-typing" role="status" aria-live="polite"><b>Codex در حال پاسخ است</b><span className="typing-dots" aria-hidden="true"><i/><i/><i/></span></div>}</div>
              <form className="chat-composer" onSubmit={sendMessage}><textarea aria-label="پیام برای Codex" value={chatMessage} onChange={e=>setChatMessage(e.target.value)} onKeyDown={submitChatOnEnter} rows="3" placeholder="ادامه بده، بهبود بده یا سؤال بپرس…" disabled={!task.codex_thread_id||running||busy}/><button type="submit" disabled={!chatMessage.trim()||!task.codex_thread_id||running||busy}><Send size={16}/> ارسال</button></form>
              {!task.codex_thread_id&&<small className="chat-unavailable">پس از تکمیل اجرای اول، گفت‌وگو در همان سشن Codex فعال می‌شود.</small>}
            </section>
             <div className="delivery"><label>پیام commit<input value={task.commit_message||''} disabled={!passed||task.committed} onChange={e=>setTask({...task,commit_message:e.target.value})}/>{task.merge_request_url&&<a className="merge-request-link" href={task.merge_request_url} target="_blank" rel="noreferrer">مشاهده درخواست ادغام</a>}</label><div><button type="button" className="suggest-commit" aria-label="Generate commit message with Codex" disabled={!passed||task.committed||busy||!task.codex_thread_id} onClick={generateCommitMessage}><Sparkles size={14}/>AutoGenerate</button><button type="button" disabled={!passed||task.committed||busy} onClick={()=>action('commit',{message:task.commit_message})}><GitCommit size={16}/>commit</button><button type="button" className="push" disabled={!task.committed||task.pushed||busy} onClick={()=>action('push')}><Upload size={16}/>push</button><button type="button" className="merge-request" disabled={!task.pushed||!!task.merge_request_url||busy} onClick={()=>action('merge-request')}><GitPullRequest size={16}/>{task.merge_request_url?'MR ساخته شد':'Create MR'}</button></div></div>
          </>}
        </section>
      </div>
    </main>
  </div>
}
createRoot(document.getElementById('root')).render(<App/>);
